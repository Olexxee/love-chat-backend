import cloudinary
import cloudinary.uploader

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import (
    CLOUDINARY_API_KEY,
    CLOUDINARY_API_SECRET,
    CLOUDINARY_CLOUD_NAME,
)
from app.db.models import (
    Conversation,
    MediaAsset,
    Message,
    MessageAttachment,
    Relationship,
    User,
    UserProfile,
)

MAX_IMAGE_SIZE = 5 * 1024 * 1024
ALLOWED_IMAGE_FORMATS = {"jpg", "jpeg", "png", "webp"}


def configure_cloudinary() -> None:
    if not all(
        [
            CLOUDINARY_CLOUD_NAME,
            CLOUDINARY_API_KEY,
            CLOUDINARY_API_SECRET,
        ]
    ):
        raise RuntimeError("Cloudinary credentials are not configured.")

    cloudinary.config(
        cloud_name=CLOUDINARY_CLOUD_NAME,
        api_key=CLOUDINARY_API_KEY,
        api_secret=CLOUDINARY_API_SECRET,
        secure=True,
    )


def upload_image(
    db: Session,
    current_user: User,
    file_bytes: bytes,
    filename: str,
    purpose: str,
) -> MediaAsset:
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    if len(file_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Images cannot exceed 5 MB.",
        )

    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if extension not in ALLOWED_IMAGE_FORMATS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JPG, PNG, and WebP images are supported.",
        )

    configure_cloudinary()

    folder = (
        f"lovechat/users/{current_user.id}/avatars"
        if purpose == "AVATAR"
        else f"lovechat/users/{current_user.id}/chat"
    )

    try:
        result = cloudinary.uploader.upload(
            file_bytes,
            folder=folder,
            resource_type="image",
            allowed_formats=["jpg", "jpeg", "png", "webp"],
            transformation=[
                {
                    "width": 1600,
                    "height": 1600,
                    "crop": "limit",
                    "quality": "auto",
                    "fetch_format": "auto",
                }
            ],
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Image upload failed.",
        ) from exc

    asset = MediaAsset(
        owner_id=current_user.id,
        provider="CLOUDINARY",
        purpose=purpose,
        resource_type="IMAGE",
        asset_id=result.get("asset_id"),
        public_id=result["public_id"],
        secure_url=result["secure_url"],
        format=result.get("format"),
        width=result.get("width"),
        height=result.get("height"),
        size_bytes=result.get("bytes"),
    )

    try:
        db.add(asset)
        db.flush()

        if purpose == "AVATAR":
            profile = db.scalar(
                select(UserProfile).where(UserProfile.user_id == current_user.id)
            )

            if profile is None:
                profile = UserProfile(user_id=current_user.id)
                db.add(profile)
                db.flush()

            profile.avatar_media_id = asset.id

        db.commit()
        db.refresh(asset)
        return asset

    except Exception:
        db.rollback()

        # Avoid leaving an orphaned Cloudinary asset.
        try:
            cloudinary.uploader.destroy(
                result["public_id"],
                resource_type="image",
            )
        except Exception:
            pass

        raise


def upload_chat_attachment(
    db: Session,
    current_user: User,
    conversation_id: int,
    file_bytes: bytes,
    filename: str,
) -> MediaAsset:
    conversation = db.scalar(
        select(Conversation)
        .join(
            Relationship,
            Conversation.relationship_id == Relationship.id,
        )
        .where(
            Conversation.id == conversation_id,
            (
                (Relationship.user_one_id == current_user.id)
                | (Relationship.user_two_id == current_user.id)
            ),
            Relationship.status == "ACTIVE",
        )
    )

    if conversation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found.",
        )

    return upload_image(
        db=db,
        current_user=current_user,
        file_bytes=file_bytes,
        filename=filename,
        purpose="CHAT_ATTACHMENT",
    )
