"""Initial schema baseline generated from the current SQLAlchemy models.

This revision is intended for a new, empty database. For an existing database,
verify the live schema against app.db.models before stamping this revision.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261016_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "media_assets",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("purpose", sa.String(length=30), nullable=False),
        sa.Column("resource_type", sa.String(length=20), nullable=False),
        sa.Column("asset_id", sa.String(length=255), nullable=True),
        sa.Column("public_id", sa.String(length=255), nullable=False),
        sa.Column("secure_url", sa.Text(), nullable=False),
        sa.Column("format", sa.String(length=20), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("asset_id"),
    )
    op.create_index("ix_media_assets_owner_id", "media_assets", ["owner_id"])
    op.create_index("ix_media_assets_public_id", "media_assets", ["public_id"])
    op.create_index(
        "ix_media_assets_owner_purpose", "media_assets", ["owner_id", "purpose"]
    )

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("avatar_media_id", sa.Integer(), nullable=True),
        sa.Column("bio", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["avatar_media_id"], ["media_assets.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "relationships",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_one_id", sa.Integer(), nullable=False),
        sa.Column("user_two_id", sa.Integer(), nullable=False),
        sa.Column("requested_by_id", sa.Integer(), nullable=False),
        sa.Column("relationship_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "user_one_id <> user_two_id",
            name="ck_relationship_users_different",
        ),
        sa.CheckConstraint(
            "requested_by_id IN (user_one_id, user_two_id)",
            name="ck_relationship_requester_is_member",
        ),
        sa.ForeignKeyConstraint(["user_one_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_two_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["requested_by_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint(
            "user_one_id", "user_two_id", name="uq_relationship_users"
        ),
    )
    op.create_index("ix_relationships_user_one_id", "relationships", ["user_one_id"])
    op.create_index("ix_relationships_user_two_id", "relationships", ["user_two_id"])
    op.create_index("ix_relationships_requested_by_id", "relationships", ["requested_by_id"])
    op.create_index("ix_relationships_status", "relationships", ["status"])
    op.create_index(
        "ix_relationship_user_one_status", "relationships", ["user_one_id", "status"]
    )
    op.create_index(
        "ix_relationship_user_two_status", "relationships", ["user_two_id", "status"]
    )
    op.create_index(
        "ix_relationship_requested_by_status",
        "relationships",
        ["requested_by_id", "status"],
    )

    op.create_table(
        "conversations",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("relationship_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["relationship_id"], ["relationships.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("relationship_id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("reply_to_message_id", sa.Integer(), nullable=True),
        sa.Column("client_message_id", sa.String(length=36), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["reply_to_message_id"], ["messages.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint(
            "conversation_id",
            "sender_id",
            "client_message_id",
            name="uq_messages_client_id_per_sender",
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_sender_id", "messages", ["sender_id"])
    op.create_index(
        "ix_messages_reply_to_message_id", "messages", ["reply_to_message_id"]
    )
    op.create_index("ix_messages_created_at", "messages", ["created_at"])
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "message_attachments",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("media_asset_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["media_asset_id"], ["media_assets.id"], ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("media_asset_id"),
    )
    op.create_index(
        "ix_message_attachments_message_id", "message_attachments", ["message_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_message_attachments_message_id", table_name="message_attachments")
    op.drop_table("message_attachments")

    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_index("ix_messages_created_at", table_name="messages")
    op.drop_index("ix_messages_reply_to_message_id", table_name="messages")
    op.drop_index("ix_messages_sender_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")

    op.drop_table("conversations")

    op.drop_index("ix_relationship_requested_by_status", table_name="relationships")
    op.drop_index("ix_relationship_user_two_status", table_name="relationships")
    op.drop_index("ix_relationship_user_one_status", table_name="relationships")
    op.drop_index("ix_relationships_status", table_name="relationships")
    op.drop_index("ix_relationships_requested_by_id", table_name="relationships")
    op.drop_index("ix_relationships_user_two_id", table_name="relationships")
    op.drop_index("ix_relationships_user_one_id", table_name="relationships")
    op.drop_table("relationships")

    op.drop_table("user_profiles")

    op.drop_index("ix_media_assets_owner_purpose", table_name="media_assets")
    op.drop_index("ix_media_assets_public_id", table_name="media_assets")
    op.drop_index("ix_media_assets_owner_id", table_name="media_assets")
    op.drop_table("media_assets")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
