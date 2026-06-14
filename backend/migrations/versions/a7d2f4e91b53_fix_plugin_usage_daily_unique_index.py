"""Fix plugin_usage_daily unique index (drop user_id from the conflict key)

The original unique index on (date, plugin_id, profile_id, user_id) made the
daily upsert ineffective for global profiles: user_id is NULL for them, and in
PostgreSQL NULLs are distinct in a unique index, so ON CONFLICT never matched
and a new row was inserted on every dispatch. profile_id is a globally-unique
UUID, so (date, plugin_id, profile_id) is sufficient to identify a bucket.

Revision ID: a7d2f4e91b53
Revises: 8f91936d0285
Create Date: 2026-06-14 10:40:00.000000

"""

from alembic import op
from sqlalchemy import inspect

# revision identifiers, used by Alembic.
revision = "a7d2f4e91b53"
down_revision = "8f91936d0285"
branch_labels = None
depends_on = None


def _has_index(table: str, name: str) -> bool:
    bind = op.get_bind()
    if table not in inspect(bind).get_table_names():
        return False
    return any(ix["name"] == name for ix in inspect(bind).get_indexes(table))


def _index_columns(table: str, name: str) -> list[str]:
    bind = op.get_bind()
    for ix in inspect(bind).get_indexes(table):
        if ix["name"] == name:
            return list(ix["column_names"])
    return []


def upgrade() -> None:
    # Idempotent: a fresh database built by init_db()'s create_all() already has
    # the corrected 3-column index, so only act when the legacy 4-column index
    # is present.
    cols = _index_columns("plugin_usage_daily", "ix_plugin_usage_daily_unique")
    if "user_id" in cols:
        op.drop_index("ix_plugin_usage_daily_unique", table_name="plugin_usage_daily")
    if not _has_index("plugin_usage_daily", "ix_plugin_usage_daily_unique"):
        op.create_index(
            "ix_plugin_usage_daily_unique",
            "plugin_usage_daily",
            ["date", "plugin_id", "profile_id"],
            unique=True,
        )


def downgrade() -> None:
    if _has_index("plugin_usage_daily", "ix_plugin_usage_daily_unique"):
        op.drop_index("ix_plugin_usage_daily_unique", table_name="plugin_usage_daily")
    op.create_index(
        "ix_plugin_usage_daily_unique",
        "plugin_usage_daily",
        ["date", "plugin_id", "profile_id", "user_id"],
        unique=True,
    )
