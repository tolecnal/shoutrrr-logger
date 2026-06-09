"""Business logic for admin-configurable application settings."""

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from repositories.settings import SettingsRepository, settings_repository


@dataclass(frozen=True)
class SettingMeta:
    key: str
    label: str
    description: str
    default: int
    min_value: int
    max_value: int
    unit: str = ""


KNOWN_SETTINGS: list[SettingMeta] = [
    SettingMeta(
        key="retention_days",
        label="Retention period",
        description="Automatically delete notifications older than this many days. Set to 0 to keep all notifications forever.",
        default=0,
        min_value=0,
        max_value=3650,
        unit="days",
    ),
    SettingMeta(
        key="page_size",
        label="Items per page",
        description="Number of notifications displayed per page in the notification log.",
        default=20,
        min_value=5,
        max_value=200,
        unit="items",
    ),
    SettingMeta(
        key="auto_refresh_interval",
        label="Auto-refresh interval",
        description="How often the notification log automatically refreshes. Set to 0 to disable auto-refresh.",
        default=30,
        min_value=0,
        max_value=3600,
        unit="seconds",
    ),
    SettingMeta(
        key="stats_window_days",
        label="Statistics window",
        description="Number of days shown in the statistics activity chart.",
        default=30,
        min_value=7,
        max_value=365,
        unit="days",
    ),
]

_META_BY_KEY: dict[str, SettingMeta] = {s.key: s for s in KNOWN_SETTINGS}


class SettingsService:
    def __init__(self, repo: SettingsRepository = settings_repository) -> None:
        self._repo = repo

    def _coerce(self, meta: SettingMeta, raw: Any) -> int:
        try:
            v = int(raw)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Setting '{meta.key}' must be an integer",
            ) from exc
        if v < meta.min_value or v > meta.max_value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Setting '{meta.key}' must be between {meta.min_value} "
                    f"and {meta.max_value}"
                ),
            )
        return v

    async def get_all(self, session: AsyncSession) -> list[dict]:
        rows = await self._repo.get_all(session)
        stored = {r.key: r.value for r in rows}
        result = []
        for meta in KNOWN_SETTINGS:
            raw = stored.get(meta.key, meta.default)
            result.append(
                {
                    "key": meta.key,
                    "value": int(raw) if raw is not None else meta.default,
                    "label": meta.label,
                    "description": meta.description,
                    "default": meta.default,
                    "min_value": meta.min_value,
                    "max_value": meta.max_value,
                    "unit": meta.unit,
                }
            )
        return result

    async def get_int(
        self, session: AsyncSession, key: str, *, default: int | None = None
    ) -> int:
        meta = _META_BY_KEY.get(key)
        fallback = default if default is not None else (meta.default if meta else 0)
        row = await self._repo.get(session, key)
        if row is None:
            return fallback
        try:
            return int(row.value)
        except (TypeError, ValueError):
            return fallback

    async def update(self, session: AsyncSession, updates: dict[str, Any]) -> list[dict]:
        for key, raw in updates.items():
            meta = _META_BY_KEY.get(key)
            if meta is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Unknown setting '{key}'",
                )
            value = self._coerce(meta, raw)
            await self._repo.set(session, key, value)
        return await self.get_all(session)


settings_service = SettingsService()
