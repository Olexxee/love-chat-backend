import json
import logging
from datetime import datetime, timezone
from urllib.request import Request, urlopen

from fastapi import BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Notification, NotificationPreference, PushDevice, User

logger = logging.getLogger(__name__)
EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def _send_expo_push(tokens: list[str], title: str, body: str, data: dict) -> None:
    if not tokens:
        return
    messages = [
        {
            "to": token,
            "title": title,
            "body": body,
            "data": data,
            "sound": "default",
            "priority": "high",
            "channelId": "messages",
        }
        for token in tokens
    ]
    # Expo accepts batches. Keep each request comfortably below its limit.
    for offset in range(0, len(messages), 100):
        request = Request(
            EXPO_PUSH_URL,
            data=json.dumps(messages[offset : offset + 100]).encode("utf-8"),
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=4) as response:
                result = json.loads(response.read().decode("utf-8"))
            for ticket, message in zip(result.get("data", []), messages[offset : offset + 100]):
                if ticket.get("status") == "error":
                    details = ticket.get("details") or {}
                    if details.get("error") == "DeviceNotRegistered":
                        logger.info("Expo push token is no longer registered; it will be deactivated on next cleanup.")
        except Exception:
            # Push is best-effort; do not fail chat delivery if Expo is unavailable.
            logger.exception("Expo push request failed")


def create_notification(
    db: Session,
    *,
    user_id: int,
    actor_id: int | None,
    notification_type: str,
    title: str,
    body: str,
    data: dict | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> Notification:
    payload = data or {}
    notification = Notification(
        user_id=user_id,
        actor_id=actor_id,
        notification_type=notification_type,
        title=title,
        body=body,
        data=payload,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    preference = db.get(NotificationPreference, user_id)
    if preference is None:
        preference = NotificationPreference(user_id=user_id)
        db.add(preference)
        db.commit()
        db.refresh(preference)

    enabled_for_type = (
        preference.message_notifications
        if notification_type == "message"
        else preference.relationship_notifications
    )
    if preference.push_enabled and enabled_for_type:
        tokens = list(
            db.scalars(
                select(PushDevice.expo_push_token).where(
                    PushDevice.user_id == user_id,
                    PushDevice.is_active.is_(True),
                )
            ).all()
        )
        if background_tasks is not None:
            background_tasks.add_task(_send_expo_push, tokens, title, body, payload)
        else:
            _send_expo_push(tokens, title, body, payload)

    return notification


def serialize_notification(notification: Notification) -> dict:
    return {
        "id": notification.id,
        "actor_id": notification.actor_id,
        "type": notification.notification_type,
        "title": notification.title,
        "body": notification.body,
        "data": notification.data or {},
        "is_read": notification.read_at is not None,
        "read_at": notification.read_at.isoformat() if notification.read_at else None,
        "created_at": notification.created_at.isoformat(),
    }
