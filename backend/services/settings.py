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
    value_type: str = "int"


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
    SettingMeta(
        key="private_tokens_enabled",
        label="Allow private access tokens",
        description=(
            "Allow users to create their own private access tokens from "
            "Preferences → My Tokens. When disabled, users can no longer create "
            "new private tokens, and existing private tokens are rejected for "
            "notification ingestion (global tokens are unaffected)."
        ),
        default=1,
        min_value=0,
        max_value=1,
        unit="",
        value_type="bool",
    ),
    SettingMeta(
        key="max_private_tokens",
        label="Max private tokens per user",
        description="Maximum number of private access tokens each user may create. Set to 0 for unlimited.",
        default=3,
        min_value=0,
        max_value=50,
        unit="tokens",
    ),
    SettingMeta(
        key="rate_limit_per_minute",
        label="Notification rate limit",
        description=(
            "Maximum notifications a single access token may submit per minute. "
            "Set to 0 for unlimited. Admins can override this per-token."
        ),
        default=0,
        min_value=0,
        max_value=10000,
        unit="per minute",
    ),
    SettingMeta(
        key="api_metrics_retention_days",
        label="API metrics retention",
        description="Automatically delete API performance metric records older than this many days. Set to 0 to keep all records forever.",
        default=30,
        min_value=0,
        max_value=3650,
        unit="days",
    ),
    SettingMeta(
        key="audit_log_retention_days",
        label="Audit log retention",
        description="Automatically delete audit log entries older than this many days. Set to 0 to keep all entries forever.",
        default=365,
        min_value=0,
        max_value=3650,
        unit="days",
    ),
    SettingMeta(
        key="alert_states_enabled",
        label="Enable alert states (Ack/Resolve)",
        description="Enable tracking state (new, acknowledged, resolved) for notifications.",
        default=0,
        min_value=0,
        max_value=1,
        unit="",
        value_type="bool",
    ),
    SettingMeta(
        key="test_rule_limit",
        label="Test rule preview limit",
        description="Maximum number of matched notifications to display when testing a routing rule.",
        default=10,
        min_value=1,
        max_value=100,
        unit="notifications",
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
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Setting '{meta.key}' must be an integer",
            ) from exc
        if v < meta.min_value or v > meta.max_value:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    f"Setting '{meta.key}' must be between {meta.min_value} and {meta.max_value}"
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
                    "value_type": meta.value_type,
                }
            )
        return result

    async def get_int(self, session: AsyncSession, key: str, *, default: int | None = None) -> int:
        meta = _META_BY_KEY.get(key)
        fallback = default if default is not None else (meta.default if meta else 0)
        row = await self._repo.get(session, key)
        if row is None:
            return fallback
        try:
            return int(row.value)
        except (TypeError, ValueError):
            return fallback

    async def get_bool(
        self, session: AsyncSession, key: str, *, default: bool | None = None
    ) -> bool:
        int_default = None if default is None else int(default)
        return await self.get_int(session, key, default=int_default) != 0

    async def update(self, session: AsyncSession, updates: dict[str, Any]) -> list[dict]:
        coerced: dict[str, int] = {}
        for key, raw in updates.items():
            meta = _META_BY_KEY.get(key)
            if meta is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=f"Unknown setting '{key}'",
                )
            coerced[key] = self._coerce(meta, raw)

        merged: dict[str, int] = {}
        for meta in KNOWN_SETTINGS:
            if meta.key in coerced:
                merged[meta.key] = coerced[meta.key]
            else:
                merged[meta.key] = await self.get_int(session, meta.key)

        stats_window_days = merged.get("stats_window_days")
        retention_days = merged.get("retention_days")
        api_metrics_retention_days = merged.get("api_metrics_retention_days")
        if stats_window_days is not None:
            if retention_days and stats_window_days > retention_days:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Statistics window ({stats_window_days} days) cannot exceed "
                        f"Retention period ({retention_days} days). Lower the statistics "
                        "window or increase the retention period (or set it to 0 for "
                        "unlimited)."
                    ),
                )
            if api_metrics_retention_days and stats_window_days > api_metrics_retention_days:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail=(
                        f"Statistics window ({stats_window_days} days) cannot exceed "
                        f"API metrics retention ({api_metrics_retention_days} days). Lower "
                        "the statistics window or increase the API metrics retention "
                        "(or set it to 0 for unlimited)."
                    ),
                )

        for key, value in coerced.items():
            await self._repo.set(session, key, value)
        return await self.get_all(session)


settings_service = SettingsService()
