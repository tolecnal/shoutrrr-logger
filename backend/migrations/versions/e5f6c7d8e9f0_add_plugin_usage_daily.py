"""Add plugin_usage_daily

Revision ID: e5f6c7d8e9f0
Revises: d4e6b9c31f08
Create Date: 2026-06-14 00:15:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e5f6c7d8e9f0"
down_revision = "d4e6b9c31f08"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "plugin_usage_daily",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plugin_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_plugin_usage_daily_unique",
        "plugin_usage_daily",
        ["date", "plugin_id", "profile_id", "user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_plugin_usage_daily_unique", table_name="plugin_usage_daily")
    op.drop_table("plugin_usage_daily")
