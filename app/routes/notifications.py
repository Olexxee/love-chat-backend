from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import Notification, NotificationPreference, PushDevice, User
from app.services.notifications import serialize_notification

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


class RegisterDeviceRequest(BaseModel):
    expo_push_token: str = Field(min_length=20, max_length=255)
    platform: Literal["ios", "android", "web"]
    device_name: str | None = Field(default=None, max_length=120)


class PreferenceUpdate(BaseModel):
    push_enabled: bool | None = None
    message_notifications: bool | None = None
    relationship_notifications: bool | None = None


def _preferences(db: Session, user_id: int) -> NotificationPreference:
    preferences = db.get(NotificationPreference, user_id)
    if preferences is None:
        preferences = NotificationPreference(user_id=user_id)
        db.add(preferences)
        db.commit()
        db.refresh(preferences)
    return preferences


def _serialize_preferences(item: NotificationPreference) -> dict:
    return {
        "push_enabled": item.push_enabled,
        "message_notifications": item.message_notifications,
        "relationship_notifications": item.relationship_notifications,
    }


@router.get("")
def list_notifications(
    limit: int = Query(default=50, ge=1, le=100),
    before_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Notification).where(Notification.user_id == current_user.id)
    if before_id is not None:
        query = query.where(Notification.id < before_id)
    items = db.scalars(query.order_by(Notification.id.desc()).limit(limit)).all()
    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == current_user.id,
            Notification.read_at.is_(None),
        )
    ) or 0
    return {
        "items": [serialize_notification(item) for item in items],
        "unread_count": count,
        "has_unread": count > 0,
    }


@router.patch("/{notification_id}/read")
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.scalar(select(Notification).where(
        Notification.id == notification_id,
        Notification.user_id == current_user.id,
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Notification not found.")
    if item.read_at is None:
        item.read_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
    return serialize_notification(item)


@router.post("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == current_user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(timezone.utc))
    )
    db.commit()
    return {"updated": result.rowcount or 0}


@router.post("/devices", status_code=200)
def register_push_device(
    data: RegisterDeviceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = data.expo_push_token.strip()
    if not (token.startswith("ExponentPushToken[") or token.startswith("ExpoPushToken[")):
        raise HTTPException(status_code=422, detail="Invalid Expo push token.")
    item = db.scalar(select(PushDevice).where(PushDevice.expo_push_token == token))
    if item is None:
        item = PushDevice(
            user_id=current_user.id,
            expo_push_token=token,
            platform=data.platform,
            device_name=data.device_name,
            is_active=True,
        )
        db.add(item)
    else:
        item.user_id = current_user.id
        item.platform = data.platform
        item.device_name = data.device_name
        item.is_active = True
        item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "registered": True}


@router.delete("/devices/{device_id}")
def unregister_push_device(
    device_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.scalar(select(PushDevice).where(
        PushDevice.id == device_id,
        PushDevice.user_id == current_user.id,
    ))
    if item is None:
        raise HTTPException(status_code=404, detail="Device not found.")
    item.is_active = False
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"registered": False}


@router.get("/preferences")
def get_notification_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _serialize_preferences(_preferences(db, current_user.id))


@router.patch("/preferences")
def update_notification_preferences(
    data: PreferenceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = _preferences(db, current_user.id)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(item, key, value)
    item.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(item)
    return _serialize_preferences(item)
