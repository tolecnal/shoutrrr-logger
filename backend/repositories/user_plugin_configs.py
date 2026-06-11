import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import UserPluginConfig


class UserPluginConfigRepository:
    async def get_by_plugin(
        self, session: AsyncSession, user_id: uuid.UUID, plugin_id: str
    ) -> UserPluginConfig | None:
        stmt = select(UserPluginConfig).where(
            UserPluginConfig.user_id == user_id, UserPluginConfig.plugin_id == plugin_id
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
