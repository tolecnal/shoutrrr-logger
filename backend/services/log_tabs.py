import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models import LogTab
from repositories.log_tabs import log_tab_repository
from schemas import LogTabCreate, LogTabOut, LogTabUpdate
from services.settings import settings_service


class LogTabService:
    def __init__(self, repo=log_tab_repository):
        self._repo = repo

    def _to_out(self, tab: LogTab) -> LogTabOut:
        return LogTabOut.model_validate(tab)

    async def list_tabs(self, session: AsyncSession, user_id: uuid.UUID) -> list[LogTabOut]:
        tabs = await self._repo.list_by_user(session, user_id)
        return [self._to_out(t) for t in tabs]

    def _owned(self, tab: LogTab | None, user_id: uuid.UUID) -> LogTab:
        if not tab or tab.user_id != user_id:
            raise HTTPException(status_code=404, detail="Tab not found")
        return tab

    async def create_tab(
        self, session: AsyncSession, body: LogTabCreate, user_id: uuid.UUID
    ) -> LogTabOut:
        limit = await settings_service.get_int(session, "max_log_tabs_per_user")
        if limit and await self._repo.count_for_user(session, user_id) >= limit:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tab limit reached ({limit})",
            )
        # Append to the right of any existing tabs.
        max_pos = await self._repo.max_position(session, user_id)
        next_pos = 0 if max_pos is None else max_pos + 1
        tab = LogTab(
            user_id=user_id,
            name=body.name,
            filters=body.filters.model_dump(),
            position=next_pos,
        )
        tab = await self._repo.add(session, tab)
        return self._to_out(tab)

    async def update_tab(
        self,
        session: AsyncSession,
        tab_id: uuid.UUID,
        body: LogTabUpdate,
        user_id: uuid.UUID,
    ) -> LogTabOut:
        tab = self._owned(await self._repo.get_by_id(session, tab_id), user_id)
        if body.name is not None:
            tab.name = body.name
        if body.filters is not None:
            tab.filters = body.filters.model_dump()
        await session.flush()
        return self._to_out(tab)

    async def delete_tab(
        self, session: AsyncSession, tab_id: uuid.UUID, user_id: uuid.UUID
    ) -> None:
        tab = self._owned(await self._repo.get_by_id(session, tab_id), user_id)
        await self._repo.delete(session, tab)

    async def reorder_tabs(
        self, session: AsyncSession, ids: list[uuid.UUID], user_id: uuid.UUID
    ) -> list[LogTabOut]:
        """Set tab positions to match ``ids``. Only the caller's tabs are touched;
        ids that don't belong to the caller are ignored, and any of the caller's
        tabs missing from ``ids`` keep their relative order after the listed ones.
        """
        tabs = await self._repo.list_by_user(session, user_id)
        by_id = {t.id: t for t in tabs}
        pos = 0
        seen: set[uuid.UUID] = set()
        for tab_id in ids:
            tab = by_id.get(tab_id)
            if tab is None or tab_id in seen:
                continue
            tab.position = pos
            seen.add(tab_id)
            pos += 1
        # Preserve any tabs the client didn't mention, appended in prior order.
        for tab in tabs:
            if tab.id not in seen:
                tab.position = pos
                pos += 1
        await session.flush()
        return await self.list_tabs(session, user_id)


log_tab_service = LogTabService()
