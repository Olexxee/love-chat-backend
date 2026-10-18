"""Add in-app notifications, Expo devices, and preferences.

Revision ID: 20261018_0004
Revises: 20261018_0003
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20261018_0004"
down_revision: Union[str, Sequence[str], None] = "20261018_0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("notification_type", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.String(length=300), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_notifications_user_created", "notifications", ["user_id", "created_at"])
    op.create_index("ix_notifications_user_read", "notifications", ["user_id", "read_at"])

    op.create_table(
        "push_devices",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expo_push_token", sa.String(length=255), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("device_name", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("expo_push_token"),
    )
    op.create_index("ix_push_devices_user_active", "push_devices", ["user_id", "is_active"])

    op.create_table(
        "notification_preferences",
        sa.Column("user_id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("message_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("relationship_notifications", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )


def downgrade() -> None:
    op.drop_table("notification_preferences")
    op.drop_index("ix_push_devices_user_active", table_name="push_devices")
    op.drop_table("push_devices")
    op.drop_index("ix_notifications_user_read", table_name="notifications")
    op.drop_index("ix_notifications_user_created", table_name="notifications")
    op.drop_table("notifications")
