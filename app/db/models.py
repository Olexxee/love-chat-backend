from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.db.enums import (
    MediaPurpose,
    MediaProvider,
    MediaResourceType,
    RelationshipStatus,
    RelationshipType,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    provider: Mapped[str] = mapped_column(
        String(30),
        default=MediaProvider.CLOUDINARY.value,
        nullable=False,
    )

    purpose: Mapped[str] = mapped_column(
        String(30),
        default=MediaPurpose.OTHER.value,
        nullable=False,
    )

    resource_type: Mapped[str] = mapped_column(
        String(20),
        default=MediaResourceType.IMAGE.value,
        nullable=False,
    )

    asset_id: Mapped[str | None] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
    )

    public_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    secure_url: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    format: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )

    width: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    height: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_media_assets_owner_purpose",
            "owner_id",
            "purpose",
        ),
    )


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    avatar_media_id: Mapped[int | None] = mapped_column(
        ForeignKey("media_assets.id", ondelete="SET NULL"),
        nullable=True,
    )

    bio: Mapped[str | None] = mapped_column(
        String(300),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Relationship(Base):
    __tablename__ = "relationships"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    user_one_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    user_two_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    requested_by_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    relationship_type: Mapped[str] = mapped_column(
        String(20),
        default=RelationshipType.ROMANTIC.value,
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(20),
        default=RelationshipStatus.PENDING.value,
        nullable=False,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    declined_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_one_id",
            "user_two_id",
            name="uq_relationship_users",
        ),
        CheckConstraint(
            "user_one_id <> user_two_id",
            name="ck_relationship_users_different",
        ),
        CheckConstraint(
            "requested_by_id IN (user_one_id, user_two_id)",
            name="ck_relationship_requester_is_member",
        ),
        Index(
            "ix_relationship_user_one_status",
            "user_one_id",
            "status",
        ),
        Index(
            "ix_relationship_user_two_status",
            "user_two_id",
            "status",
        ),
        Index(
            "ix_relationship_requested_by_status",
            "requested_by_id",
            "status",
        ),
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    relationship_id: Mapped[int] = mapped_column(
        ForeignKey("relationships.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    reply_to_message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Generated by the client and reused when retrying a send.
    # Nullable to preserve compatibility with existing messages.
    client_message_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )

    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    __table_args__ = (
        Index(
            "ix_messages_conversation_created",
            "conversation_id",
            "created_at",
        ),
        UniqueConstraint(
            "conversation_id",
            "sender_id",
            "client_message_id",
            name="uq_messages_client_id_per_sender",
        ),
    )


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
    )

    message_id: Mapped[int] = mapped_column(
        ForeignKey("messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    media_asset_id: Mapped[int] = mapped_column(
        ForeignKey("media_assets.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )



class DeliveryEvent(Base):
    """Durable, ordered conversation events used to recover after disconnects."""

    __tablename__ = "delivery_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    message_id: Mapped[int | None] = mapped_column(
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_delivery_events_conversation_id_id", "conversation_id", "id"),
        Index("ix_delivery_events_message_id", "message_id"),
    )


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_password_reset_tokens_user_used", "user_id", "used_at"),
    )
