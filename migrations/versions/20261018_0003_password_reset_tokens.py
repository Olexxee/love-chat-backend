"""Add hashed, single-use password reset tokens.

Revision ID: 20261018_0003
Revises: 20261016_0002
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "20261018_0003"
down_revision: Union[str, Sequence[str], None] = "20261016_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_user_used", "password_reset_tokens", ["user_id", "used_at"])

def downgrade() -> None:
    op.drop_index("ix_password_reset_tokens_user_used", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
