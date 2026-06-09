"""Database access for the ``app_settings`` table."""

from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from models import AppSetting


class SettingsRepository:
    async def get(self, session: AsyncSession, key: str) -> AppSetting | None:
        return await session.get(AppSetting, key)

    async def get_all(self, session: AsyncSession) -> Sequence[AppSetting]:
        result = await session.execute(select(AppSetting).order_by(AppSetting.key))
        return result.scalars().all()

    async def set(self, session: AsyncSession, key: str, value: object) -> AppSetting:
        """Upsert a setting value, returning the updated row."""
        stmt = (
            pg_insert(AppSetting)
            .values(key=key, value=value)
            .on_conflict_do_update(
                index_elements=["key"],
                set_={"value": value, "updated_at": func.now()},
            )
            .returning(AppSetting)
        )
        result = await session.execute(stmt)
        return result.scalar_one()


settings_repository = SettingsRepository()
