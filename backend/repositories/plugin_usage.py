from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import PluginUsageDaily


class PluginUsageRepository:
    async def record_dispatch(
        self,
        session: AsyncSession,
        *,
        plugin_id: str,
        profile_id: UUID,
        user_id: UUID | None,
        is_success: bool,
        duration_ms: float,
        day: datetime | None = None,
    ) -> None:
        """Upsert today's aggregated counters for a (plugin, profile) dispatch.

        Uses an atomic ON CONFLICT DO UPDATE on the
        (date, plugin_id, profile_id) unique index so concurrent dispatches
        accumulate correctly. Dialect-aware so it works both on PostgreSQL
        (production) and SQLite (tests). Does not commit — the caller owns the
        transaction.
        """
        bucket = day or datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        success = 1 if is_success else 0
        error = 0 if is_success else 1

        dialect = session.get_bind().dialect.name
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        elif dialect == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:  # pragma: no cover - only postgres (prod) and sqlite (tests) are used
            raise RuntimeError(f"record_dispatch: unsupported dialect {dialect!r}")

        stmt = insert(PluginUsageDaily).values(
            date=bucket,
            plugin_id=plugin_id,
            profile_id=profile_id,
            user_id=user_id,
            success_count=success,
            error_count=error,
            total_duration_ms=duration_ms,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["date", "plugin_id", "profile_id"],
            set_={
                "success_count": PluginUsageDaily.success_count + success,
                "error_count": PluginUsageDaily.error_count + error,
                "total_duration_ms": PluginUsageDaily.total_duration_ms + duration_ms,
            },
        )
        await session.execute(stmt)

    async def get_admin_stats(
        self, session: AsyncSession, days: int = 30
    ) -> Sequence[PluginUsageDaily]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = (
            select(PluginUsageDaily)
            .where(PluginUsageDaily.date >= cutoff)
            .order_by(PluginUsageDaily.date.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_user_stats(
        self, session: AsyncSession, user_id: UUID, days: int = 30
    ) -> Sequence[PluginUsageDaily]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        stmt = (
            select(PluginUsageDaily)
            .where(PluginUsageDaily.date >= cutoff, PluginUsageDaily.user_id == user_id)
            .order_by(PluginUsageDaily.date.desc())
        )
        result = await session.execute(stmt)
        return result.scalars().all()


plugin_usage_repo = PluginUsageRepository()
