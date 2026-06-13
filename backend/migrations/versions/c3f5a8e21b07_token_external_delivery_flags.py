"""per-token external delivery flags

Adds allow_plugin_dispatch and allow_email_alerts to access_tokens, letting a
token's creator control whether notifications sent with it may leave the app
via plugins and/or email alerts. Both default to TRUE (existing behavior).

NOTE: defensive existence checks are required (see 8f2c1a7d94e3): init_db()
builds fresh databases at head schema via create_all() but stamps baseline,
so this migration may run against a schema where the columns already exist.

Revision ID: c3f5a8e21b07
Revises: 4b9e0d21c6aa
Create Date: 2026-06-13 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3f5a8e21b07"
down_revision: str | Sequence[str] | None = "4b9e0d21c6aa"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLE = "access_tokens"
_COLUMNS = ("allow_plugin_dispatch", "allow_email_alerts")


def _has_column(name: str) -> bool:
    return any(c["name"] == name for c in sa.inspect(op.get_bind()).get_columns(_TABLE))


def upgrade() -> None:
    """Upgrade schema."""
    for col in _COLUMNS:
        if not _has_column(col):
            op.add_column(
                _TABLE,
                sa.Column(col, sa.Boolean(), nullable=False, server_default=sa.true()),
            )


def downgrade() -> None:
    """Downgrade schema."""
    for col in _COLUMNS:
        if _has_column(col):
            op.drop_column(_TABLE, col)
