"""Add saved_searches and log_tabs

Per-user notification-log views: saved_searches is a named, reusable search
library; log_tabs are the user's persistent open tabs. Both store the full
filter state as a JSONB blob and are owned by a user (CASCADE on delete).

Revision ID: b8c1e7f2a3d4
Revises: a7d2f4e91b53
Create Date: 2026-06-15 09:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "b8c1e7f2a3d4"
down_revision = "a7d2f4e91b53"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    # Defensive: init_db() builds fresh databases at head schema via create_all()
    # but stamps baseline, so these tables may already exist when this runs.
    if not _has_table("saved_searches"):
        op.create_table(
            "saved_searches",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column(
                "filters",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="{}",
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_saved_searches_user_id", "saved_searches", ["user_id"])
        op.create_index(
            "ix_saved_searches_user_name",
            "saved_searches",
            ["user_id", "name"],
            unique=True,
        )

    if not _has_table("log_tabs"):
        op.create_table(
            "log_tabs",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column(
                "filters",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default="{}",
            ),
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_log_tabs_user_id", "log_tabs", ["user_id"])
        op.create_index("ix_log_tabs_user_position", "log_tabs", ["user_id", "position"])


def downgrade() -> None:
    if _has_table("log_tabs"):
        op.drop_table("log_tabs")
    if _has_table("saved_searches"):
        op.drop_table("saved_searches")
