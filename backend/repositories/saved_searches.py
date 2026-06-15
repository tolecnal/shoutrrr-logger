import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import SavedSearch


class SavedSearchRepository:
    async def get_by_id(self, session: AsyncSession, search_id: uuid.UUID) -> SavedSearch | None:
        stmt = select(SavedSearch).where(SavedSearch.id == search_id)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(self, session: AsyncSession, user_id: uuid.UUID) -> list[SavedSearch]:
        stmt = select(SavedSearch).where(SavedSearch.user_id == user_id).order_by(SavedSearch.name)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count_for_user(self, session: AsyncSession, user_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(SavedSearch).where(SavedSearch.user_id == user_id)
        result = await session.execute(stmt)
        return int(result.scalar_one())

    async def get_by_name(
        self, session: AsyncSession, user_id: uuid.UUID, name: str
    ) -> SavedSearch | None:
        stmt = select(SavedSearch).where(SavedSearch.user_id == user_id, SavedSearch.name == name)
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def add(self, session: AsyncSession, search: SavedSearch) -> SavedSearch:
        session.add(search)
        await session.flush()
        return search

    async def delete(self, session: AsyncSession, search: SavedSearch) -> None:
        await session.delete(search)
        await session.flush()


saved_search_repository = SavedSearchRepository()
