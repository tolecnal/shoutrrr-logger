"""Business logic for storing, searching, and dispatching notifications."""

import logging
import math
import uuid

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models import AccessToken, Notification
from repositories.notifications import NotificationRepository, notification_repository
from repositories.plugin_configs import PluginConfigRepository, plugin_config_repository
from schemas import NotificationOut, PaginatedResponse

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        repo: NotificationRepository = notification_repository,
        plugin_config_repo: PluginConfigRepository = plugin_config_repository,
    ) -> None:
        self._repo = repo
        self._plugin_config_repo = plugin_config_repo

    async def list_notifications(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        page: int,
        page_size: int,
    ) -> PaginatedResponse[NotificationOut]:
        rows, total = await self._repo.search_paginated(
            session, query=query, page=page, page_size=page_size
        )
        return PaginatedResponse(
            items=[NotificationOut.model_validate(r) for r in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
        )

    async def get_notification(
        self, session: AsyncSession, notification_id: uuid.UUID | str
    ) -> Notification:
        notification = await self._repo.get_by_id(session, notification_id)
        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
            )
        return notification

    async def custom_field_keys(self, session: AsyncSession, *, limit: int) -> list[str]:
        return await self._repo.distinct_custom_field_keys(session, limit)

    async def store_incoming(
        self,
        session: AsyncSession,
        *,
        token: AccessToken,
        sender_name: str | None,
        title: str | None,
        message: str,
        raw_payload: str | None,
        source_ip: str | None,
    ) -> Notification:
        notification = Notification(
            token_id=token.id,
            sender_name=sender_name,
            title=title,
            message=message,
            raw_payload=raw_payload,
            source_ip=source_ip,
        )
        return await self._repo.add(session, notification)

    async def dispatch_plugins(self, notification_dict: dict) -> None:
        """
        Run all enabled plugins against a saved notification.

        Each plugin gets its own try/except so one failure doesn't block
        others. Intended to run as a FastAPI BackgroundTask — obtains its own
        session since the request-scoped session will already be closed.
        """
        from database import engine  # noqa: PLC0415
        from plugins import registry as plugin_registry  # noqa: PLC0415

        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            rows = await self._plugin_config_repo.list_enabled(session)

        plugin_configs = {row.id: row for row in rows}

        for plugin in plugin_registry.all_plugins():
            row = plugin_configs.get(plugin.plugin_id)
            if not row or not row.enabled:
                continue
            merged_config = {**plugin.default_config, **row.config}
            try:
                await plugin.on_notification(notification_dict, merged_config)
            except Exception as exc:
                logger.error(
                    "[plugin:%s] on_notification raised: %s",
                    plugin.plugin_id,
                    exc,
                    exc_info=True,
                )


notification_service = NotificationService()
