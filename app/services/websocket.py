import logging

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[int, set[WebSocket]] = {}
        self.connection_conversations: dict[WebSocket, int] = {}

    async def connect(
        self,
        user_id: int,
        websocket: WebSocket,
        conversation_id: int,
    ) -> bool:
        was_online = self.is_online(user_id)

        await websocket.accept()

        self.active_connections.setdefault(user_id, set()).add(websocket)
        self.connection_conversations[websocket] = conversation_id

        return not was_online

    def disconnect(
        self,
        user_id: int,
        websocket: WebSocket,
    ) -> bool:
        connections = self.active_connections.get(user_id)

        self.connection_conversations.pop(websocket, None)

        if not connections:
            return True

        connections.discard(websocket)

        if not connections:
            self.active_connections.pop(user_id, None)
            return True

        return False

    async def send_to_user(
        self,
        user_id: int,
        data: dict,
        conversation_id: int | None = None,
    ) -> None:
        connections = self.active_connections.get(user_id, set())

        # Convert datetime objects and other supported values to JSON-safe data.
        payload = jsonable_encoder(data)

        for websocket in connections.copy():
            if (
                conversation_id is not None
                and self.connection_conversations.get(websocket) != conversation_id
            ):
                continue

            try:
                await websocket.send_json(payload)

            except Exception:
                logger.exception(
                    "WebSocket delivery failed for user_id=%s",
                    user_id,
                )
                self.disconnect(user_id, websocket)

    async def send_to_users(
        self,
        user_ids: list[int],
        data: dict,
        conversation_id: int | None = None,
    ) -> None:
        for user_id in set(user_ids):
            await self.send_to_user(
                user_id,
                data,
                conversation_id,
            )

    def is_online(self, user_id: int) -> bool:
        return bool(self.active_connections.get(user_id))


manager = ConnectionManager()
