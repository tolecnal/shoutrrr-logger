import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models import SavedSearch
from repositories.saved_searches import saved_search_repository
from schemas import SavedSearchCreate, SavedSearchOut, SavedSearchUpdate
from services.settings import settings_service


class SavedSearchService:
    def __init__(self, repo=saved_search_repository):
        self._repo = repo

    def _to_out(self, search: SavedSearch) -> SavedSearchOut:
        return SavedSearchOut.model_validate(search)

    async def list_searches(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[SavedSearchOut]:
        searches = await self._repo.list_by_user(session, user_id)
        return [self._to_out(s) for s in searches]

    def _owned(self, search: SavedSearch | None, user_id: uuid.UUID) -> SavedSearch:
        if not search or search.user_id != user_id:
            raise HTTPException(status_code=404, detail="Saved search not found")
        return search

    async def create_search(
        self, session: AsyncSession, body: SavedSearchCreate, user_id: uuid.UUID
    ) -> SavedSearchOut:
        limit = await settings_service.get_int(session, "max_saved_searches_per_user")
        if limit and await self._repo.count_for_user(session, user_id) >= limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Saved-search limit reached ({limit})",
            )
        if await self._repo.get_by_name(session, user_id, body.name):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A saved search with that name already exists",
            )
        search = SavedSearch(
            user_id=user_id,
            name=body.name,
            filters=body.filters.model_dump(),
        )
        search = await self._repo.add(session, search)
        return self._to_out(search)

    async def update_search(
        self,
        session: AsyncSession,
        search_id: uuid.UUID,
        body: SavedSearchUpdate,
        user_id: uuid.UUID,
    ) -> SavedSearchOut:
        search = self._owned(await self._repo.get_by_id(session, search_id), user_id)

        if body.name is not None and body.name != search.name:
            existing = await self._repo.get_by_name(session, user_id, body.name)
            if existing and existing.id != search.id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="A saved search with that name already exists",
                )
            search.name = body.name
        if body.filters is not None:
            search.filters = body.filters.model_dump()

        await session.flush()
        return self._to_out(search)

    async def delete_search(
        self, session: AsyncSession, search_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        search = self._owned(await self._repo.get_by_id(session, search_id), user_id)
        await self._repo.delete(session, search)


saved_search_service = SavedSearchService()
