"""add total_duration_ms to plugin_usage_daily

Revision ID: 8f91936d0285
Revises: e5f6c7d8e9f0
Create Date: 2026-06-14 02:28:35.229161

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f91936d0285"
down_revision: str | Sequence[str] | None = "e5f6c7d8e9f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _has_column(table: str, name: str) -> bool:
    return any(c["name"] == name for c in sa.inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    """Upgrade schema."""
    # Defensive: init_db() builds fresh databases at head schema via create_all()
    # but stamps baseline, so the column may already exist when this runs.
    if not _has_column("plugin_usage_daily", "total_duration_ms"):
        op.add_column(
            "plugin_usage_daily",
            sa.Column("total_duration_ms", sa.Float(), nullable=False, server_default="0.0"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    if _has_column("plugin_usage_daily", "total_duration_ms"):
        op.drop_column("plugin_usage_daily", "total_duration_ms")
