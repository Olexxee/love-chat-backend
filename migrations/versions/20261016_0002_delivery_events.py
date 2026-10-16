"""Add durable conversation delivery events.

This is additive and preserves existing users, conversations, and messages.
For a database with existing tables and no Alembic history, verify its schema
before stamping the initial baseline, then apply this revision.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20261016_0002"
down_revision: Union[str, Sequence[str], None] = "20261016_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "delivery_events",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["messages.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_delivery_events_conversation_id_id",
        "delivery_events",
        ["conversation_id", "id"],
    )
    op.create_index(
        "ix_delivery_events_message_id",
        "delivery_events",
        ["message_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_delivery_events_message_id", table_name="delivery_events")
    op.drop_index(
        "ix_delivery_events_conversation_id_id", table_name="delivery_events"
    )
    op.drop_table("delivery_events")
