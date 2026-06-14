"""Add enabled column to plugin_configs

Revision ID: d4e6b9c31f08
Revises: c3f5a8e21b07
Create Date: 2026-06-13 23:35:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4e6b9c31f08"
down_revision = "c3f5a8e21b07"
branch_labels = None
depends_on = None


def _has_column(table: str, name: str) -> bool:
    return any(c["name"] == name for c in sa.inspect(op.get_bind()).get_columns(table))


def upgrade() -> None:
    # Defensive: init_db() builds fresh databases at head schema via create_all()
    # but stamps baseline, so this may run against a plugin_configs that already
    # has the column.
    if not _has_column("plugin_configs", "enabled"):
        # Add the column with a default of True for existing rows
        op.add_column(
            "plugin_configs",
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        )


def downgrade() -> None:
    if _has_column("plugin_configs", "enabled"):
        op.drop_column("plugin_configs", "enabled")
