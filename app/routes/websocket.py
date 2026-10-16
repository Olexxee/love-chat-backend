from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.core.websocket import authenticate_websocket
from app.db.database import SessionLocal
from app.db.models import User
from app.services.message import (
    delete_message,
    mark_message_as_read,
    send_message,
)
from app.services.relationship import get_authorized_conversation
from app.services.websocket import manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/api/ws/chat")
async def chat_websocket(
    websocket: WebSocket,
    conversation_id: int,
):
    db = SessionLocal()
    user: User | None = None
    partner: User | None = None
    connected = False

    try:
        user = await run_in_threadpool(
            authenticate_websocket,
            websocket,
            db,
        )

        conversation, _, partner = await run_in_threadpool(
            get_authorized_conversation,
            db,
            user,
            conversation_id,
        )

        became_online = await manager.connect(
            user.id,
            websocket,
            conversation.id,
        )
        connected = True

        await websocket.send_json(
            {
                "type": "presence",
                "user_id": partner.id,
                "online": manager.is_online(partner.id),
            }
        )

        if became_online:
            await manager.send_to_user(
                partner.id,
                {
                    "type": "presence",
                    "user_id": user.id,
                    "online": True,
                },
            )

        await websocket.send_json(
            {
                "type": "connected",
                "conversation_id": conversation.id,
                "message": "Connected to LoveChat",
            }
        )

        while True:
            data = await websocket.receive_json()
            message_type = data.get("type")

            if message_type == "message":
                content = data.get("content", "")
                attachment_ids = data.get("attachment_ids", [])
                client_message_id = data.get("client_message_id")
                reply_to_message_id = data.get("reply_to_message_id")

                if not isinstance(content, str):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "content must be a string",
                        }
                    )
                    continue

                if not isinstance(attachment_ids, list) or any(
                    type(item) is not int or item <= 0 for item in attachment_ids
                ):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "attachment_ids must be a list " "of positive integers"
                            ),
                        }
                    )
                    continue

                if client_message_id is not None and (
                    not isinstance(client_message_id, str)
                    or not client_message_id.strip()
                    or len(client_message_id) > 36
                ):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "client_message_id must be a string "
                                "containing 1 to 36 characters"
                            ),
                        }
                    )
                    continue

                if reply_to_message_id is not None and (
                    type(reply_to_message_id) is not int or reply_to_message_id <= 0
                ):
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": (
                                "reply_to_message_id must be " "a positive integer"
                            ),
                        }
                    )
                    continue

                message = await run_in_threadpool(
                    send_message,
                    db,
                    user,
                    conversation.id,
                    content,
                    attachment_ids,
                    client_message_id,
                    reply_to_message_id,
                )

                await manager.send_to_users(
                    [user.id, partner.id],
                    {
                        "type": "message",
                        "message": message,
                        "client_message_id": message["client_message_id"],
                    },
                    conversation_id=conversation.id,
                )

            elif message_type == "delete":
                message_id = data.get("message_id")

                if type(message_id) is not int or message_id <= 0:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "message_id must be a positive integer",
                        }
                    )
                    continue

                deleted_message = await run_in_threadpool(
                    delete_message,
                    db,
                    user,
                    message_id,
                )

                await manager.send_to_users(
                    [user.id, partner.id],
                    {
                        "type": "message_deleted",
                        "message_id": deleted_message["id"],
                        "conversation_id": conversation.id,
                        "deleted_at": deleted_message["deleted_at"],
                    },
                    conversation_id=conversation.id,
                )

            elif message_type in ("typing_start", "typing_stop"):
                await manager.send_to_user(
                    partner.id,
                    {
                        "type": "typing",
                        "user_id": user.id,
                        "is_typing": message_type == "typing_start",
                        "conversation_id": conversation.id,
                    },
                    conversation_id=conversation.id,
                )

            elif message_type == "read":
                message_id = data.get("message_id")

                if type(message_id) is not int or message_id <= 0:
                    await websocket.send_json(
                        {
                            "type": "error",
                            "message": "message_id must be a positive integer",
                        }
                    )
                    continue

                message = await run_in_threadpool(
                    mark_message_as_read,
                    db,
                    user,
                    message_id,
                )

                await manager.send_to_users(
                    [user.id, partner.id],
                    {
                        "type": "message_read",
                        "message_id": message["id"],
                        "reader_id": user.id,
                        "read_at": (
                            message["read_at"].isoformat()
                            if message["read_at"]
                            else None
                        ),
                        "conversation_id": conversation.id,
                    },
                    conversation_id=conversation.id,
                )

            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Unsupported message type",
                    }
                )

    except WebSocketDisconnect:
        pass

    except HTTPException as exc:
        if not connected:
            await websocket.close(
                code=4404 if exc.status_code == 404 else 4403,
                reason="Conversation unavailable or access denied",
            )
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": exc.detail,
                }
            )

    finally:
        if connected and user:
            became_offline = manager.disconnect(
                user.id,
                websocket,
            )

            if became_offline and partner:
                await manager.send_to_user(
                    partner.id,
                    {
                        "type": "presence",
                        "user_id": user.id,
                        "online": False,
                    },
                )

        db.close()
