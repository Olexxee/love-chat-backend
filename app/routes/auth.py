import jwt
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    ACCESS_TOKEN_COOKIE,
    REFRESH_TOKEN_COOKIE,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
)
from app.db.database import get_db
from app.db.models import MediaAsset, User, UserProfile
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    UserResponse,
)
from app.services.auth import login_user, register_user

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
)

ACCESS_TOKEN_MAX_AGE = 30 * 60
REFRESH_TOKEN_MAX_AGE = 7 * 24 * 60 * 60


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> None:
    cookie_options = {
        "httponly": True,
        "secure": True,
        "samesite": "none",
        "path": "/",
    }

    response.set_cookie(
        key=ACCESS_TOKEN_COOKIE,
        value=access_token,
        max_age=ACCESS_TOKEN_MAX_AGE,
        **cookie_options,
    )

    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE,
        value=refresh_token,
        max_age=REFRESH_TOKEN_MAX_AGE,
        **cookie_options,
    )


def serialize_user(
    db: Session,
    user: User,
) -> dict:
    avatar_url = db.scalar(
        select(MediaAsset.secure_url)
        .join(
            UserProfile,
            UserProfile.avatar_media_id == MediaAsset.id,
        )
        .where(
            UserProfile.user_id == user.id,
            MediaAsset.deleted_at.is_(None),
        )
    )

    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "avatar_url": avatar_url,
    }


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register(
    data: RegisterRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user = register_user(db, data)

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    set_auth_cookies(
        response,
        access_token,
        refresh_token,
    )

    return serialize_user(db, user)


@router.post(
    "/login",
    response_model=UserResponse,
)
def login(
    data: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    user, access_token, refresh_token = login_user(
        db,
        data,
    )

    set_auth_cookies(
        response,
        access_token,
        refresh_token,
    )

    return serialize_user(db, user)


@router.post("/refresh", response_model=UserResponse)
def refresh_session(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE),
    db: Session = Depends(get_db),
):
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is missing.",
        )

    try:
        payload = decode_token(refresh_token)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired.",
        ) from exc

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        )

    try:
        user_id = int(payload.get("sub", ""))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token.",
        ) from exc

    user = db.scalar(select(User).where(User.id == user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is unavailable or inactive.",
        )

    set_auth_cookies(
        response,
        create_access_token(user.id),
        create_refresh_token(user.id),
    )
    return serialize_user(db, user)


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return serialize_user(db, current_user)


@router.post("/logout")
def logout(response: Response):
    cookie_options = {
        "httponly": True,
        "secure": True,
        "samesite": "none",
        "path": "/",
    }

    response.delete_cookie(
        key=ACCESS_TOKEN_COOKIE,
        **cookie_options,
    )

    response.delete_cookie(
        key=REFRESH_TOKEN_COOKIE,
        **cookie_options,
    )

    return {
        "message": "Logged out successfully",
    }
