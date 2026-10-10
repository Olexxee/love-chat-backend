import jwt
from fastapi import WebSocket, WebSocketException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import JWT_ALGORITHM, JWT_SECRET_KEY
from app.core.security import ACCESS_TOKEN_COOKIE
from app.db.models import User


def authenticate_websocket(
    websocket: WebSocket,
    db: Session,
) -> User:
    # Read the access token from the cookie first — this matches how the
    # REST routes authenticate via `get_current_user`. Fall back to a
    # `?token=` query param so the endpoint can be tested with tools like
    # `wscat`, which don't carry cookies.
    token = (
        websocket.cookies.get(ACCESS_TOKEN_COOKIE)
        or websocket.query_params.get("token")
    )

    if not token:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Authentication required",
        )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.InvalidTokenError:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid or expired access token",
        )

    if payload.get("type") != "access":
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid access token",
        )

    user_id = payload.get("sub")

    if not user_id:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid access token",
        )

    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Invalid access token",
        )

    user = db.scalar(select(User).where(User.id == user_id))

    if not user:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="User no longer exists",
        )

    return user