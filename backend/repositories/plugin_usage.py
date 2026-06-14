from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import PluginUsageDaily


class PluginUsageRepository:
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
