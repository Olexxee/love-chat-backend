from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.database import get_db
from app.db.models import User
from app.schemas.media import MediaResponse
from app.services.media import (
    upload_chat_attachment,
    upload_image,
)

router = APIRouter(
    prefix="/api/media",
    tags=["Media"],
)


MAX_UPLOAD_BYTES = 5 * 1024 * 1024


async def read_upload(file: UploadFile) -> bytes:
    try:
        content = await file.read(MAX_UPLOAD_BYTES + 1)
        if len(content) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Images cannot exceed 5 MB.",
            )
        return content
    finally:
        await file.close()


@router.post(
    "/avatar",
    response_model=MediaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_avatar_route(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_bytes = await read_upload(file)

    return upload_image(
        db=db,
        current_user=current_user,
        file_bytes=file_bytes,
        filename=file.filename or "",
        purpose="AVATAR",
    )


@router.post(
    "/conversations/{conversation_id}/attachments",
    response_model=MediaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_chat_attachment_route(
    conversation_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    file_bytes = await read_upload(file)

    return upload_chat_attachment(
        db=db,
        current_user=current_user,
        conversation_id=conversation_id,
        file_bytes=file_bytes,
        filename=file.filename or "",
    )
