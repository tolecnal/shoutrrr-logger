"""Tests for the cross-worker retention-loop leadership election.

With multiple gunicorn workers, only one process should run
``_retention_loop``; ``_acquire_retention_leadership`` decides this via a
PostgreSQL session-level advisory lock (always "leader" on SQLite, since
tests/dev only ever run a single process).
"""

from unittest.mock import AsyncMock, MagicMock

from main import _acquire_retention_leadership


class TestRetentionLeadership:
    async def test_non_postgres_is_always_leader(self, engine):
        is_leader, conn = await _acquire_retention_leadership(engine)

        assert is_leader is True
        assert conn is None

    async def test_postgres_becomes_leader_when_lock_acquired(self):
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = True
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_engine.connect = AsyncMock(return_value=mock_conn)

        is_leader, conn = await _acquire_retention_leadership(mock_engine)

        assert is_leader is True
        assert conn is mock_conn
        mock_conn.close.assert_not_called()

    async def test_postgres_not_leader_when_lock_held_elsewhere(self):
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = False
        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_result

        mock_engine = MagicMock()
        mock_engine.dialect.name = "postgresql"
        mock_engine.connect = AsyncMock(return_value=mock_conn)

        is_leader, conn = await _acquire_retention_leadership(mock_engine)

        assert is_leader is False
        assert conn is None
        mock_conn.close.assert_awaited_once()
