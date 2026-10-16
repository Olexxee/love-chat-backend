from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import DeliveryEvent, Message, User
from app.schemas.message import (
    CreateMessageRequest,
    DeliveryEventResponse,
    MessageResponse,
)
from sqlalchemy import select

from app.services.message import (
    delete_message,
    get_messages,
    mark_message_as_read,
    send_message,
)
from app.services.relationship import get_authorized_conversation
from app.services.websocket import manager

router = APIRouter(tags=["Messages"])


@router.post(
    "/api/conversations/{conversation_id}/messages",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
)
async def send_message_route(
    conversation_id: int,
    data: CreateMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation, _, partner = get_authorized_conversation(
        db,
        current_user,
        conversation_id,
    )

    message = send_message(
        db,
        current_user,
        conversation_id,
        data.content,
        data.attachment_ids,
        data.client_message_id,
        data.reply_to_message_id,
    )

    await manager.send_to_users(
        [current_user.id, partner.id],
        {
            "type": "message",
            "event_id": message.get("event_id"),
            "message": {key: value for key, value in message.items() if key != "event_id"},
            "client_message_id": message["client_message_id"],
        },
        conversation_id=conversation.id,
    )

    return message


@router.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def get_messages_route(
    conversation_id: int,
    before_id: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_messages(
        db,
        current_user,
        conversation_id,
        before_id=before_id,
        limit=limit,
    )


@router.get(
    "/api/conversations/{conversation_id}/events",
    response_model=list[DeliveryEventResponse],
)
def get_delivery_events_route(
    conversation_id: int,
    after_id: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conversation, _, _ = get_authorized_conversation(
        db, current_user, conversation_id
    )
    return db.scalars(
        select(DeliveryEvent)
        .where(
            DeliveryEvent.conversation_id == conversation.id,
            DeliveryEvent.id > after_id,
        )
        .order_by(DeliveryEvent.id.asc())
        .limit(limit)
    ).all()


@router.patch(
    "/api/messages/{message_id}/read",
    response_model=MessageResponse,
)


def mark_message_as_read_route(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")

    conversation, _, partner = get_authorized_conversation(
        db, current_user, message.conversation_id
    )
    result = mark_message_as_read(db, current_user, message_id)
    if result.get("event_id") is not None:
        await manager.send_to_users(
            [current_user.id, partner.id],
            {
                "type": "message_read",
                "event_id": result["event_id"],
                "message_id": result["id"],
                "reader_id": current_user.id,
                "read_at": result["read_at"],
                "conversation_id": conversation.id,
            },
            conversation_id=conversation.id,
        )
    return result


@router.delete(
    "/api/messages/{message_id}",
    response_model=MessageResponse,
)
async def delete_message_route(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = db.get(Message, message_id)

    if existing is None:
        raise HTTPException(
            status_code=404,
            detail="Message not found.",
        )

    conversation, _, partner = get_authorized_conversation(
        db,
        current_user,
        existing.conversation_id,
    )

    message = delete_message(
        db,
        current_user,
        message_id,
    )

    await manager.send_to_users(
        [current_user.id, partner.id],
        {
            "type": "message_deleted",
            "event_id": message.get("event_id"),
            "message_id": message["id"],
            "conversation_id": conversation.id,
            "deleted_at": message["deleted_at"],
        },
        conversation_id=conversation.id,
    )

    return message
