"""Business logic for storing, searching, and dispatching notifications."""

import csv
import hashlib
import io
import json
import logging
import math
import uuid
from datetime import UTC, datetime, timedelta

import sqlalchemy
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from models import AccessToken, Notification
from repositories.notifications import NotificationRepository, notification_repository
from repositories.plugin_configs import PluginConfigRepository, plugin_config_repository
from schemas import CursorPage, NotificationOut, NotificationStats

logger = logging.getLogger(__name__)


def _csv_safe(value: str) -> str:
    """Neutralize spreadsheet formula injection in CSV exports.

    Notification content is attacker-controlled (it comes from the ingestion
    endpoint). Cells beginning with =, +, -, @, tab, or CR are interpreted as
    formulas by Excel/LibreOffice/Sheets, so prefix them with a single quote.
    """
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{value}"
    return value


class NotificationService:
    def __init__(
        self,
        repo: NotificationRepository = notification_repository,
        plugin_config_repo: PluginConfigRepository = plugin_config_repository,
    ) -> None:
        self._repo = repo
        self._plugin_config_repo = plugin_config_repo
        self._filter_cache: dict[str, list[str]] | None = None
        self._filter_cache_time: float = 0

    async def list_notifications(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        cursor: str | None,
        page_size: int,
        after: datetime | None = None,
        before: datetime | None = None,
        scope: str = "all",
        user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> CursorPage[NotificationOut]:
        try:
            rows, total, next_cursor = await self._repo.search_paginated(
                session,
                query=query,
                cursor=cursor,
                page_size=page_size,
                after=after,
                before=before,
                scope=scope,
                user_id=user_id,
                is_admin=is_admin,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        # Per-row delete permission for the Gmail-style selection UI. One bounded
        # query per page (admins short-circuit to "all deletable").
        deletable = await self._repo.deletable_ids_among(
            session, [r.id for r in rows], user_id=user_id, is_admin=is_admin
        )
        items = []
        for r in rows:
            out = NotificationOut.model_validate(r)
            out.can_delete = r.id in deletable
            items.append(out)
        return CursorPage(
            items=items,
            total=total,
            page_size=page_size,
            pages=math.ceil(total / page_size) if total > 0 else 0,
            next_cursor=next_cursor,
        )

    async def get_search_filters(self, session: AsyncSession) -> dict[str, list[str]]:
        import time

        now = time.time()
        if self._filter_cache is None or now - self._filter_cache_time > 300:
            senders, tags = await self._repo.get_recent_filters(session)
            self._filter_cache = {
                "senders": sorted(list(senders)),
                "tags": sorted(list(tags)),
                "severities": ["info", "warning", "error", "critical"],
            }
            self._filter_cache_time = now
        return self._filter_cache

    async def get_notification(
        self,
        session: AsyncSession,
        notification_id: uuid.UUID | str,
        *,
        user_id: uuid.UUID | None,
        is_admin: bool,
    ) -> Notification:
        notification = await self._repo.get_visible_by_id(
            session, notification_id, user_id=user_id, is_admin=is_admin
        )
        if notification is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found"
            )
        return notification

    async def update_state(
        self,
        session: AsyncSession,
        notification_id: uuid.UUID | str,
        state: str,
        *,
        user_id: uuid.UUID | None,
        is_admin: bool,
    ) -> Notification:
        notification = await self.get_notification(
            session, notification_id, user_id=user_id, is_admin=is_admin
        )
        notification.state = state
        await session.flush()
        await session.refresh(notification)
        try:
            await session.execute(
                sqlalchemy.text("SELECT pg_notify('shoutrrr_updates', :payload)"),
                {"payload": '{"event": "state_change"}'},
            )
        except sqlalchemy.exc.OperationalError:
            pass  # SQLite during tests
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
        severity: str = "info",
        tags: list[str] | None = None,
        fingerprint_group: str | None = None,
    ) -> Notification:
        tags = tags or []

        # Calculate fingerprint
        if fingerprint_group:
            fp_raw = fingerprint_group
        else:
            fp_raw = f"{title or ''}:{message}:{severity}"
        # Non-cryptographic dedup grouping key, not a security control.
        fingerprint = hashlib.md5(fp_raw.encode(), usedforsecurity=False).hexdigest()

        # Look for a recent duplicate (last 5 minutes)
        cutoff = datetime.now(UTC) - timedelta(minutes=5)
        existing = await self._repo.find_recent_by_fingerprint(session, fingerprint, cutoff)

        if existing:
            existing.occurrences += 1
            existing.last_received_at = datetime.now(UTC)
            await session.flush()
            await session.refresh(existing)
            try:
                await session.execute(
                    sqlalchemy.text("SELECT pg_notify('shoutrrr_updates', :payload)"),
                    {"payload": '{"event": "update"}'},
                )
            except sqlalchemy.exc.OperationalError:
                pass  # SQLite during tests
            return existing

        notification = Notification(
            token_id=token.id,
            sender_name=sender_name,
            title=title,
            message=message,
            raw_payload=raw_payload,
            source_ip=source_ip,
            severity=severity,
            tags=tags,
            fingerprint=fingerprint,
        )
        notification = await self._repo.add(session, notification)
        try:
            await session.execute(
                sqlalchemy.text("SELECT pg_notify('shoutrrr_updates', :payload)"),
                {"payload": '{"event": "new"}'},
            )
        except sqlalchemy.exc.OperationalError:
            pass  # SQLite during tests
        return notification

    async def get_stats(self, session: AsyncSession, *, days: int = 30) -> NotificationStats:
        raw = await self._repo.stats_summary(session, days=days)
        return NotificationStats.model_validate(raw)

    async def export_csv(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        after: datetime | None,
        before: datetime | None,
        scope: str = "all",
        user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> str:
        try:
            rows = await self._repo.export_all(
                session,
                query=query,
                after=after,
                before=before,
                scope=scope,
                user_id=user_id,
                is_admin=is_admin,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            ["id", "received_at", "sender_name", "title", "message", "source_ip", "custom_fields"]
        )
        for n in rows:
            custom = ""
            if n.raw_payload:
                try:
                    parsed = json.loads(n.raw_payload)
                    if isinstance(parsed, dict):
                        custom = "; ".join(f"{k}={v}" for k, v in parsed.items())
                except (json.JSONDecodeError, TypeError):
                    pass
            writer.writerow(
                [
                    str(n.id),
                    n.received_at.isoformat(),
                    _csv_safe(n.sender_name or ""),
                    _csv_safe(n.title or ""),
                    _csv_safe(n.message),
                    _csv_safe(n.source_ip or ""),
                    _csv_safe(custom),
                ]
            )
        return buf.getvalue()

    async def export_json(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        after: datetime | None,
        before: datetime | None,
        scope: str = "all",
        user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> str:
        try:
            rows = await self._repo.export_all(
                session,
                query=query,
                after=after,
                before=before,
                scope=scope,
                user_id=user_id,
                is_admin=is_admin,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        items = [NotificationOut.model_validate(r).model_dump(mode="json") for r in rows]
        return json.dumps(items, indent=2, default=str)

    async def purge_old(self, session: AsyncSession, *, retention_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        return await self._repo.delete_older_than(session, cutoff)

    async def bulk_delete(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        after: datetime | None,
        before: datetime | None,
        scope: str = "all",
        user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> int:
        try:
            return await self._repo.delete_bulk(
                session,
                query=query,
                after=after,
                before=before,
                scope=scope,
                user_id=user_id,
                is_admin=is_admin,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc

    async def delete_selected(
        self,
        session: AsyncSession,
        ids: list[uuid.UUID],
        *,
        user_id: uuid.UUID | None,
        is_admin: bool,
    ) -> tuple[int, int]:
        """Delete an explicit selection of notifications, enforcing per-row
        delete permission. Returns ``(requested, deleted)``; the difference is
        rows skipped because the caller may not delete them (or they're gone)."""
        deleted = await self._repo.delete_by_ids(session, ids, user_id=user_id, is_admin=is_admin)
        return len(ids), deleted

    async def dispatch_plugins(self, notification_dict: dict, user_id_str: str | None) -> None:
        """
        Run all enabled plugins against a saved notification.
        """
        from sqlalchemy import select

        from database import engine  # noqa: PLC0415
        from models import PluginProfile, UserPluginConfig
        from plugins import registry as plugin_registry  # noqa: PLC0415

        async_session = async_sessionmaker(engine, expire_on_commit=False)
        async with async_session() as session:
            # Load enabled global plugin profiles
            global_stmt = select(PluginProfile).where(PluginProfile.enabled.is_(True))
            global_configs = (await session.execute(global_stmt)).scalars().all()

            user_configs = []
            if user_id_str:
                import uuid

                try:
                    uid = uuid.UUID(user_id_str)
                    user_stmt = select(UserPluginConfig).where(
                        UserPluginConfig.enabled.is_(True), UserPluginConfig.user_id == uid
                    )
                    user_configs = (await session.execute(user_stmt)).scalars().all()
                except Exception as e:
                    logger.error(f"Error loading user configs: {e}")

        configs_to_run = list(global_configs) + list(user_configs)

        for row in configs_to_run:
            plugin_id = getattr(row, "plugin_id", getattr(row, "id", None))
            plugin = plugin_registry.get_plugin(plugin_id)
            if not plugin:
                continue

            if row.rules:
                from schemas import RoutingRuleCreate
                from services.routing_rules import routing_rule_service

                try:
                    # Instantiate rules dynamically from the JSON objects
                    rule_objs = [RoutingRuleCreate.model_validate(r) for r in row.rules]

                    matched_any = any(
                        routing_rule_service.rule_matches(rule, notification_dict)
                        for rule in rule_objs
                    )
                except Exception as exc:
                    logger.error(
                        "[plugin:%s] failed to evaluate routing rules: %s",
                        plugin_id,
                        exc,
                        exc_info=True,
                    )
                    continue
                if not matched_any:
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
