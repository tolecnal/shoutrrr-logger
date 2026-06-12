import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import UserPluginConfig


class UserPluginConfigRepository:
    async def get_by_id(
        self, session: AsyncSession, user_id: uuid.UUID, profile_id: uuid.UUID
    ) -> UserPluginConfig | None:
        stmt = select(UserPluginConfig).where(
            UserPluginConfig.id == profile_id, UserPluginConfig.user_id == user_id
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_plugin(
        self, session: AsyncSession, user_id: uuid.UUID, plugin_id: str
    ) -> list[UserPluginConfig]:
        """All of a user's profiles for one plugin, alphabetical (stable tab order)."""
        stmt = (
            select(UserPluginConfig)
            .where(UserPluginConfig.user_id == user_id, UserPluginConfig.plugin_id == plugin_id)
            .order_by(UserPluginConfig.name)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_plugin(
        self, session: AsyncSession, user_id: uuid.UUID, plugin_id: str
    ) -> int:
        stmt = select(func.count(UserPluginConfig.id)).where(
            UserPluginConfig.user_id == user_id, UserPluginConfig.plugin_id == plugin_id
        )
        result = await session.execute(stmt)
        return result.scalar_one()

    async def get_by_name(
        self, session: AsyncSession, user_id: uuid.UUID, plugin_id: str, name: str
    ) -> UserPluginConfig | None:
        stmt = select(UserPluginConfig).where(
            UserPluginConfig.user_id == user_id,
            UserPluginConfig.plugin_id == plugin_id,
            UserPluginConfig.name == name,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_user(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> list[UserPluginConfig]:
        stmt = select(UserPluginConfig).where(UserPluginConfig.user_id == user_id)
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def add(self, session: AsyncSession, config: UserPluginConfig) -> UserPluginConfig:
        session.add(config)
        await session.flush()
        return config

    async def delete(self, session: AsyncSession, config: UserPluginConfig) -> None:
        await session.delete(config)
        await session.flush()


user_plugin_config_repository = UserPluginConfigRepository()
