
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.message import CreateMessageRequest, MessageResponse
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
    _, _, partner = get_authorized_conversation(
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
    )

    await manager.send_to_users(
        [current_user.id, partner.id],
        {
            "type": "message",
            "message": message,
        },
        conversation_id=conversation_id,
    )

    return message


@router.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=list[MessageResponse],
)
def get_messages_route(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_messages(db, current_user, conversation_id)


@router.patch(
    "/api/messages/{message_id}/read",
    response_model=MessageResponse,
)
def mark_message_as_read_route(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return mark_message_as_read(db, current_user, message_id)


@router.delete(
    "/api/messages/{message_id}",
    response_model=MessageResponse,
)
def delete_message_route(
    message_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return delete_message(db, current_user, message_id)
