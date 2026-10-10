from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import MediaAsset, Message, MessageAttachment, User
from app.services.relationship import get_authorized_conversation


def _serialize_message(db: Session, message: Message) -> dict:
    attachment_rows = db.execute(
        select(MessageAttachment, MediaAsset)
        .join(MediaAsset, MessageAttachment.media_asset_id == MediaAsset.id)
        .where(MessageAttachment.message_id == message.id)
        .order_by(MessageAttachment.id.asc())
    ).all()

    return {
        "id": message.id,
        "conversation_id": message.conversation_id,
        "sender_id": message.sender_id,
        "client_message_id": message.client_message_id,
        "content": message.content,
        "created_at": message.created_at,
        "read_at": message.read_at,
        "deleted_at": message.deleted_at,
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
            return _serialize_message(db, existing)

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
        db.commit()
        return result

    except IntegrityError:
        db.rollback()

        # A concurrent retry may have inserted this same message first.
        if client_message_id is not None:
            existing = _find_by_client_message_id(
                db,
                conversation.id,
                current_user.id,
                client_message_id,
            )

            if existing is not None:
                return _serialize_message(db, existing)

        raise

    except Exception:
        db.rollback()
        raise


def get_messages(
    db: Session,
    current_user: User,
    conversation_id: int,
) -> list[dict]:
    conversation, _, _ = get_authorized_conversation(
        db,
        current_user,
        conversation_id,
    )

    messages = db.scalars(
        select(Message)
        .where(
            Message.conversation_id == conversation.id,
            Message.deleted_at.is_(None),
        )
        .order_by(Message.created_at.asc(), Message.id.asc())
    ).all()

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
        db.commit()
        db.refresh(message)

    return _serialize_message(db, message)


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
    db.commit()
    db.refresh(message)

    return _serialize_message(db, message)
