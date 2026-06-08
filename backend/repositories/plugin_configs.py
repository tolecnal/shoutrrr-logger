"""Database access for the ``plugin_configs`` table."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import PluginConfig


class PluginConfigRepository:
    async def get_by_id(self, session: AsyncSession, plugin_id: str) -> PluginConfig | None:
        return await session.get(PluginConfig, plugin_id)

    async def list_enabled(self, session: AsyncSession) -> Sequence[PluginConfig]:
        result = await session.execute(
            select(PluginConfig).where(PluginConfig.enabled == True)  # noqa: E712
        )
        return result.scalars().all()

    async def add(self, session: AsyncSession, config: PluginConfig) -> PluginConfig:
        session.add(config)
        await session.flush()
        return config


plugin_config_repository = PluginConfigRepository()
