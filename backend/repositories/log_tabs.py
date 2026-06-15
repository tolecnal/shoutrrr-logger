import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import LogTab


class LogTabRepository:
    async def get_by_id(self, session: AsyncSession, tab_id: uuid.UUID) -> LogTab | None:
        stmt = select(LogTab).where(LogTab.id == tab_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, session: AsyncSession, user_id: uuid.UUID) -> list[LogTab]:
        stmt = (
            select(LogTab)
            .where(LogTab.user_id == user_id)
            .order_by(LogTab.position, LogTab.created_at)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_user(self, session: AsyncSession, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(LogTab).where(LogTab.user_id == user_id)
        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def max_position(self, session: AsyncSession, user_id: uuid.UUID) -> int | None:
        stmt = select(func.max(LogTab.position)).where(LogTab.user_id == user_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, session: AsyncSession, tab: LogTab) -> LogTab:
        session.add(tab)
        await session.flush()
        return tab

    async def delete(self, session: AsyncSession, tab: LogTab) -> None:
        await session.delete(tab)
        await session.flush()


log_tab_repository = LogTabRepository()
