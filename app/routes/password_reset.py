from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.services.password_reset import request_password_reset, reset_password

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=8, max_length=100)


@router.post("/forgot-password")
def forgot_password(
    data: PasswordResetRequest,
    db: Session = Depends(get_db),
):
    return request_password_reset(db, str(data.email))


@router.post("/reset-password")
def confirm_password_reset(
    data: PasswordResetConfirm,
    db: Session = Depends(get_db),
):
    return reset_password(db, data.token, data.new_password)
