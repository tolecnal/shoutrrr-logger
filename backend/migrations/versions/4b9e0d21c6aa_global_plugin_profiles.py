"""global plugin configuration profiles

Moves the per-configuration state (enabled/config/rules) of global plugins
out of plugin_configs into named plugin_profiles rows, mirroring the
user-side profiles. Existing configurations become the "Default" profile;
plugin_configs keeps only plugin-level settings (allow_user_configs).

NOTE: defensive existence checks are required (see 8f2c1a7d94e3): init_db()
builds fresh databases at head schema via create_all() but stamps baseline,
so this migration may run against a schema that is already in target shape.

Revision ID: 4b9e0d21c6aa
Revises: 8f2c1a7d94e3
Create Date: 2026-06-12 21:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4b9e0d21c6aa"
down_revision: str | Sequence[str] | None = "8f2c1a7d94e3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _inspector().has_table(name)


def _has_column(table: str, name: str) -> bool:
    return any(c["name"] == name for c in _inspector().get_columns(table))


def upgrade() -> None:
    """Upgrade schema."""
    if not _has_table("plugin_profiles"):
        op.create_table(
            "plugin_profiles",
            sa.Column("id", sa.UUID(), nullable=False),
            sa.Column("plugin_id", sa.String(length=64), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False, server_default="Default"),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("rules", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_plugin_profiles_plugin_id", "plugin_profiles", ["plugin_id"])
        op.create_index(
            "ix_plugin_profiles_plugin_name",
            "plugin_profiles",
            ["plugin_id", "name"],
            unique=True,
        )

    # Move existing per-plugin state into a "Default" profile. Only possible
    # (and only needed) while plugin_configs still carries the old columns.
    if _has_column("plugin_configs", "enabled"):
        op.execute(
            """
            INSERT INTO plugin_profiles (id, plugin_id, name, enabled, config, rules, updated_at)
            SELECT gen_random_uuid(), id, 'Default', enabled, config, rules, updated_at
            FROM plugin_configs
            """
        )
        op.drop_column("plugin_configs", "enabled")
    if _has_column("plugin_configs", "config"):
        op.drop_column("plugin_configs", "config")
    if _has_column("plugin_configs", "rules"):
        op.drop_column("plugin_configs", "rules")


def downgrade() -> None:
    """Downgrade schema.

    Destructive for multi-profile data: each plugin's "Default" profile (or,
    if renamed/deleted, its alphabetically first profile) is folded back into
    plugin_configs; other profiles are dropped with the table.
    """
    if not _has_column("plugin_configs", "enabled"):
        op.add_column(
            "plugin_configs",
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if not _has_column("plugin_configs", "config"):
        op.add_column(
            "plugin_configs",
            sa.Column(
                "config",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'{}'::jsonb"),
            ),
        )
    if not _has_column("plugin_configs", "rules"):
        op.add_column(
            "plugin_configs",
            sa.Column(
                "rules",
                postgresql.JSONB(astext_type=sa.Text()),
                nullable=False,
                server_default=sa.text("'[]'::jsonb"),
            ),
        )

    if _has_table("plugin_profiles"):
        op.execute(
            """
            UPDATE plugin_configs pc
            SET enabled = pp.enabled, config = pp.config, rules = pp.rules
            FROM (
                SELECT DISTINCT ON (plugin_id) plugin_id, enabled, config, rules
                FROM plugin_profiles
                ORDER BY plugin_id, (name = 'Default') DESC, name
            ) pp
            WHERE pp.plugin_id = pc.id
            """
        )
        op.drop_index("ix_plugin_profiles_plugin_name", table_name="plugin_profiles")
        op.drop_index("ix_plugin_profiles_plugin_id", table_name="plugin_profiles")
        op.drop_table("plugin_profiles")
