from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.schemas.auth import LoginRequest, RegisterRequest


def register_user(
    db: Session,
    data: RegisterRequest,
) -> User:
    email = data.email.lower().strip()

    existing_user = db.scalar(
        select(User).where(User.email == email)
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email is already registered",
        )

    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_password(data.password),
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def login_user(
    db: Session,
    data: LoginRequest,
) -> tuple[User, str, str]:
    email = data.email.lower().strip()

    user = db.scalar(
        select(User).where(User.email == email)
    )

    if not user or not verify_password(
        data.password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    access_token = create_access_token(user.id)
    refresh_token = create_refresh_token(user.id)

    return user, access_token, refresh_token

