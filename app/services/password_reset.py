import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import resend
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import (
    PASSWORD_RESET_EXPIRE_MINUTES,
    PASSWORD_RESET_FROM_EMAIL,
    PASSWORD_RESET_REDIRECT_URL,
    RESEND_API_KEY,
)
from app.core.security import hash_password
from app.db.models import PasswordResetToken, User

GENERIC_MESSAGE = "If an account exists for that email, password reset instructions will be sent."


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(db: Session, email: str) -> dict:
    if not RESEND_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Password reset email is not configured yet.",
        )

    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))

    # Keep the response identical for known and unknown email addresses.
    if user is None or not user.is_active:
        return {"message": GENERIC_MESSAGE}

    now = datetime.now(timezone.utc)
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)

    raw_token = secrets.token_urlsafe(32)
    reset_record = PasswordResetToken(
        user_id=user.id,
        token_hash=_token_hash(raw_token),
        expires_at=now + timedelta(minutes=PASSWORD_RESET_EXPIRE_MINUTES),
    )
    db.add(reset_record)
    db.commit()

    reset_url = f"{PASSWORD_RESET_REDIRECT_URL}?token={raw_token}"
    resend.api_key = RESEND_API_KEY
    try:
        resend.Emails.send({
            "from": PASSWORD_RESET_FROM_EMAIL,
            "to": [user.email],
            "subject": "Reset your LoveChat password",
            "html": (
                "<div style='font-family:Arial,sans-serif;max-width:520px;margin:auto;color:#292326'>"
                "<h1 style='color:#873E52'>Reset your LoveChat password</h1>"
                "<p>We received a request to reset your LoveChat password.</p>"
                f"<p><a href='{reset_url}' style='display:inline-block;padding:14px 22px;"
                "background:#B85C70;color:#fff;text-decoration:none;border-radius:10px'>"
                "Choose a new password</a></p>"
                f"<p>This link expires in {PASSWORD_RESET_EXPIRE_MINUTES} minutes and can only be used once.</p>"
                "<p>If you did not request this, you can safely ignore this email.</p>"
                "</div>"
            ),
        })
    except Exception as exc:
        db.rollback()
        # Do not expose provider details or tokens to the API response.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Unable to send the reset email. Please try again.",
        ) from exc

    return {"message": GENERIC_MESSAGE}


def reset_password(db: Session, token: str, new_password: str) -> dict:
    now = datetime.now(timezone.utc)
    token_digest = _token_hash(token)
    reset_record = db.scalar(
        select(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == token_digest,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .with_for_update()
    )
    if reset_record is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Request a new one.",
        )

    user = db.scalar(select(User).where(User.id == reset_record.user_id))
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This reset link is invalid or has expired. Request a new one.",
        )

    user.password_hash = hash_password(new_password)
    reset_record.used_at = now
    db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id,
        PasswordResetToken.used_at.is_(None),
    ).update({"used_at": now}, synchronize_session=False)
    db.commit()
    return {"message": "Password updated successfully. You can now sign in."}
