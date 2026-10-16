from datetime import datetime, timezone

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Conversation,
    DeliveryEvent,
    MediaAsset,
    Message,
    MessageAttachment,
    User,
)
from app.services.relationship import get_authorized_conversation


def _serialize_message(db: Session, message: Message) -> dict:
    is_deleted = message.deleted_at is not None

    attachment_rows = []

    if not is_deleted:
        attachment_rows = db.execute(
            select(MessageAttachment, MediaAsset)
            .join(MediaAsset, MessageAttachment.media_asset_id == MediaAsset.id)
            .where(MessageAttachment.message_id == message.id)
            .order_by(MessageAttachment.id.asc())
        ).all()

    reply_to = None

    if message.reply_to_message_id is not None:
        original = db.get(Message, message.reply_to_message_id)

        if original is not None:
            original_deleted = original.deleted_at is not None

            reply_to = {
                "id": original.id,
                "sender_id": original.sender_id,
                "content": (
                    "This message was deleted" if original_deleted else original.content
                ),
                "deleted_at": original.deleted_at,
                "has_attachments": (
                    False
                    if original_deleted
                    else db.scalar(
                        select(MessageAttachment.id)
                        .where(MessageAttachment.message_id == original.id)
                        .limit(1)
                    )
                    is not None
                ),
            }

    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "client_message_id": message.client_message_id,
        "content": "" if is_deleted else message.content,
        "created_at": message.created_at,
        "read_at": message.read_at,
        "deleted_at": message.deleted_at,
        "reply_to_message_id": message.reply_to_message_id,
        "reply_to": reply_to,
        "attachments": [
            {
                "id": attachment.id,
                "media_asset_id": asset.id,
                "secure_url": asset.secure_url,
                "format": asset.format,
                "width": asset.width,
                "height": asset.height,
            }
            for attachment, asset in attachment_rows
        ],
    }



def _record_delivery_event(
    db: Session,
    conversation_id: int,
    actor_id: int,
    event_type: str,
    payload: dict,
    message_id: int | None = None,
) -> int:
    # Serialize event ID allocation per conversation. On PostgreSQL, the row
    # lock makes committed event IDs a safe monotonically increasing cursor.
    db.scalar(
        select(Conversation)
        .where(Conversation.id == conversation_id)
        .with_for_update()
    )
    event = DeliveryEvent(
        conversation_id=conversation_id,
        actor_id=actor_id,
        message_id=message_id,
        event_type=event_type,
        payload=jsonable_encoder(payload),
    )
    db.add(event)
    db.flush()
    return event.id


def _event_id_for_message(
    db: Session,
    message_id: int,
    event_type: str,
) -> int | None:
    return db.scalar(
        select(DeliveryEvent.id)
        .where(
            DeliveryEvent.message_id == message_id,
            DeliveryEvent.event_type == event_type,
        )
        .order_by(DeliveryEvent.id.desc())
        .limit(1)
    )


def _find_by_client_message_id(
    db: Session,
    conversation_id: int,
    sender_id: int,
    client_message_id: str,
) -> Message | None:
    return db.scalar(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.sender_id == sender_id,
            Message.client_message_id == client_message_id,
        )
    )


def send_message(
    db: Session,
    current_user: User,
    conversation_id: int,
    content: str,
    attachment_ids: list[int] | None = None,
    client_message_id: str | None = None,
    reply_to_message_id: int | None = None,
) -> dict:
    conversation, _, _ = get_authorized_conversation(
        db,
        current_user,
        conversation_id,
    )

    content = content.strip()
    attachment_ids = attachment_ids or []

    if client_message_id is not None:
        client_message_id = client_message_id.strip()

        if not client_message_id or len(client_message_id) > 36:
            raise HTTPException(
                status_code=400,
                detail="client_message_id must contain between 1 and 36 characters.",
            )

        existing = _find_by_client_message_id(
            db,
            conversation.id,
            current_user.id,
            client_message_id,
        )

        if existing is not None:
            result = _serialize_message(db, existing)
            event_id = _event_id_for_message(db, existing.id, "message")
            if event_id is None:
                event_id = _record_delivery_event(
                    db,
                    conversation_id=conversation.id,
                    actor_id=current_user.id,
                    event_type="message",
                    message_id=existing.id,
                    payload={
                        "type": "message",
                        "message": result,
                        "client_message_id": result["client_message_id"],
                    },
                )
                db.commit()
            result["event_id"] = event_id
            return result

    if reply_to_message_id is not None:
        original = db.get(Message, reply_to_message_id)

        if (
            original is None
            or original.conversation_id != conversation.id
            or original.deleted_at is not None
        ):
            raise HTTPException(
                status_code=400,
                detail="The message you are replying to is unavailable.",
            )

    if len(attachment_ids) > 5:
        raise HTTPException(
            status_code=400,
            detail="A message can contain at most five attachments.",
        )

    if len(attachment_ids) != len(set(attachment_ids)):
        raise HTTPException(
            status_code=400,
            detail="Duplicate attachment IDs are not allowed.",
        )

    if not content and not attachment_ids:
        raise HTTPException(
            status_code=400,
            detail="A message must contain text or at least one attachment.",
        )

    try:
        if attachment_ids:
            assets = db.scalars(
                select(MediaAsset).where(
                    MediaAsset.id.in_(attachment_ids),
                    MediaAsset.owner_id == current_user.id,
                    MediaAsset.purpose == "CHAT_ATTACHMENT",
                    MediaAsset.resource_type == "IMAGE",
                    MediaAsset.deleted_at.is_(None),
                )
            ).all()

            assets_by_id = {asset.id: asset for asset in assets}

            if len(assets_by_id) != len(attachment_ids):
                raise HTTPException(
                    status_code=400,
                    detail="One or more attachments are invalid or unavailable.",
                )

        message = Message(
            conversation_id=conversation.id,
            sender_id=current_user.id,
            client_message_id=client_message_id,
            content=content,
            reply_to_message_id=reply_to_message_id,
        )

        db.add(message)
        db.flush()

        for asset_id in attachment_ids:
            db.add(
                MessageAttachment(
                    message_id=message.id,
                    media_asset_id=asset_id,
                )
            )

        db.flush()
        result = _serialize_message(db, message)
        event_id = _record_delivery_event(
            db,
            conversation_id=conversation.id,
            actor_id=current_user.id,
            event_type="message",
            message_id=message.id,
            payload={
                "type": "message",
                "message": result,
                "client_message_id": result["client_message_id"],
            },
        )
        db.commit()
        result["event_id"] = event_id
        return result

    except IntegrityError:
        db.rollback()

        if client_message_id is not None:
            existing = _find_by_client_message_id(
                db,
                conversation.id,
                current_user.id,
                client_message_id,
            )

            if existing is not None:
                result = _serialize_message(db, existing)
                event_id = _event_id_for_message(db, existing.id, "message")
                if event_id is None:
                    event_id = _record_delivery_event(
                        db,
                        conversation_id=conversation.id,
                        actor_id=current_user.id,
                        event_type="message",
                        message_id=existing.id,
                        payload={
                            "type": "message",
                            "message": result,
                            "client_message_id": result["client_message_id"],
                        },
                    )
                    db.commit()
                result["event_id"] = event_id
                return result

        raise

    except Exception:
        db.rollback()
        raise


def get_messages(
    db: Session,
    current_user: User,
    conversation_id: int,
    before_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    conversation, _, _ = get_authorized_conversation(
        db,
        current_user,
        conversation_id,
    )

    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100.")

    statement = select(Message).where(Message.conversation_id == conversation.id)
    if before_id is not None:
        if before_id <= 0:
            raise HTTPException(status_code=400, detail="before_id must be positive.")
        anchor = db.scalar(
            select(Message).where(
                Message.id == before_id,
                Message.conversation_id == conversation.id,
            )
        )
        if anchor is None:
            raise HTTPException(
                status_code=400,
                detail="before_id must identify a message in this conversation.",
            )
        statement = statement.where(
            or_(
                Message.created_at < anchor.created_at,
                and_(
                    Message.created_at == anchor.created_at,
                    Message.id < anchor.id,
                ),
            )
        )

    # Fetch newest first for bounded queries, then return the page chronologically.
    messages = db.scalars(
        statement.order_by(Message.created_at.desc(), Message.id.desc()).limit(limit)
    ).all()
    messages.reverse()

    return [_serialize_message(db, message) for message in messages]


def mark_message_as_read(
    db: Session,
    current_user: User,
    message_id: int,
) -> dict:
    message = db.get(Message, message_id)

    if message is None or message.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Message not found.")

    get_authorized_conversation(
        db,
        current_user,
        message.conversation_id,
    )

    if message.sender_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot mark your own messages as read.",
        )

    if message.read_at is None:
        message.read_at = datetime.now(timezone.utc)
        result = _serialize_message(db, message)
        event_id = _record_delivery_event(
            db,
            conversation_id=message.conversation_id,
            actor_id=current_user.id,
            event_type="message_read",
            message_id=message.id,
            payload={
                "type": "message_read",
                "message_id": message.id,
                "reader_id": current_user.id,
                "read_at": message.read_at.isoformat(),
                "conversation_id": message.conversation_id,
            },
        )
        db.commit()
        db.refresh(message)
        result = _serialize_message(db, message)
        result["event_id"] = event_id
        return result

    result = _serialize_message(db, message)
    result["event_id"] = _event_id_for_message(db, message.id, "message_read")
    return result


def delete_message(
    db: Session,
    current_user: User,
    message_id: int,
) -> dict:
    message = db.get(Message, message_id)

    if message is None or message.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Message not found.")

    get_authorized_conversation(
        db,
        current_user,
        message.conversation_id,
    )

    if message.sender_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can only delete your own messages.",
        )

    message.deleted_at = datetime.now(timezone.utc)
    result = _serialize_message(db, message)
    event_id = _record_delivery_event(
        db,
        conversation_id=message.conversation_id,
        actor_id=current_user.id,
        event_type="message_deleted",
        message_id=message.id,
        payload={
            "type": "message_deleted",
            "message_id": message.id,
            "conversation_id": message.conversation_id,
            "deleted_at": message.deleted_at.isoformat(),
        },
    )
    db.commit()
    db.refresh(message)
    result = _serialize_message(db, message)
    result["event_id"] = event_id
    return result
