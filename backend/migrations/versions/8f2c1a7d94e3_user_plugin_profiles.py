"""user plugin configuration profiles

Adds a `name` column to user_plugin_configs and relaxes the per-plugin
uniqueness to (user_id, plugin_id, name), turning each row into a named
configuration profile. Existing rows become the "Default" profile.

NOTE: defensive existence checks are required here. `init_db()` builds fresh
databases with `Base.metadata.create_all()` (which already produces this
revision's schema from models.py) but stamps them at the *baseline*
revision — so this migration may run against a schema where the column and
index already exist.

Revision ID: 8f2c1a7d94e3
Revises: 1ccc65108abc
Create Date: 2026-06-12 16:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8f2c1a7d94e3"
down_revision: str | Sequence[str] | None = "1ccc65108abc"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "user_plugin_configs"
_OLD_INDEX = "ix_user_plugin_configs_user_plugin"
_NEW_INDEX = "ix_user_plugin_configs_user_plugin_name"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_column(name: str) -> bool:
    return any(c["name"] == name for c in _inspector().get_columns(_TABLE))


def _has_index(name: str) -> bool:
    return any(i["name"] == name for i in _inspector().get_indexes(_TABLE))


def upgrade() -> None:
    """Upgrade schema."""
    if not _has_column("name"):
        op.add_column(
            _TABLE,
            sa.Column("name", sa.String(length=100), nullable=False, server_default="Default"),
        )
    if _has_index(_OLD_INDEX):
        op.drop_index(_OLD_INDEX, table_name=_TABLE)
    if not _has_index(_NEW_INDEX):
        op.create_index(
            _NEW_INDEX,
            _TABLE,
            ["user_id", "plugin_id", "name"],
            unique=True,
        )


def downgrade() -> None:
    """Downgrade schema.

    Destructive for multi-profile data: only the oldest profile per
    (user_id, plugin_id) survives, since the old schema allows one row per
    plugin per user.
    """
    op.execute(
        f"""
        DELETE FROM {_TABLE} a
        USING {_TABLE} b
        WHERE a.user_id = b.user_id
          AND a.plugin_id = b.plugin_id
          AND a.id <> b.id
          AND (b.updated_at < a.updated_at
               OR (b.updated_at = a.updated_at AND b.id < a.id))
        """
    )
    if _has_index(_NEW_INDEX):
        op.drop_index(_NEW_INDEX, table_name=_TABLE)
    if not _has_index(_OLD_INDEX):
        op.create_index(
            _OLD_INDEX,
            _TABLE,
            ["user_id", "plugin_id"],
            unique=True,
        )
    if _has_column("name"):
        op.drop_column(_TABLE, "name")
