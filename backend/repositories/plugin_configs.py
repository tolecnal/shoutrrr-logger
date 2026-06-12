"""Database access for the ``plugin_configs`` and ``plugin_profiles`` tables."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import PluginConfig, PluginProfile


class PluginConfigRepository:
    async def get_by_id(self, session: AsyncSession, plugin_id: str) -> PluginConfig | None:
        return await session.get(PluginConfig, plugin_id)

    async def add(self, session: AsyncSession, config: PluginConfig) -> PluginConfig:
        session.add(config)
        await session.flush()
        return config

    # -- profiles -----------------------------------------------------------

    async def get_profile_by_id(
        self, session: AsyncSession, profile_id: uuid.UUID
    ) -> PluginProfile | None:
        return await session.get(PluginProfile, profile_id)

    async def list_profiles(self, session: AsyncSession, plugin_id: str) -> list[PluginProfile]:
        """All global profiles for one plugin, alphabetical (stable tab order)."""
        stmt = (
            select(PluginProfile)
            .where(PluginProfile.plugin_id == plugin_id)
            .order_by(PluginProfile.name)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def get_profile_by_name(
        self, session: AsyncSession, plugin_id: str, name: str
    ) -> PluginProfile | None:
        stmt = select(PluginProfile).where(
            PluginProfile.plugin_id == plugin_id, PluginProfile.name == name
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_enabled_profiles(self, session: AsyncSession) -> int:
        stmt = select(func.count(PluginProfile.id)).where(PluginProfile.enabled.is_(True))
        result = await session.execute(stmt)
        return result.scalar_one()

    async def add_profile(self, session: AsyncSession, profile: PluginProfile) -> PluginProfile:
        session.add(profile)
        await session.flush()
        return profile

    async def delete_profile(self, session: AsyncSession, profile: PluginProfile) -> None:
        await session.delete(profile)
        await session.flush()


plugin_config_repository = PluginConfigRepository()
