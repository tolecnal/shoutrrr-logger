"""Database access for the ``audit_logs`` table."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog
from repositories.cursor import decode_cursor, encode_cursor


class AuditLogRepository:
    async def add(self, session: AsyncSession, entry: AuditLog) -> AuditLog:
        session.add(entry)
        await session.flush()
        await session.refresh(entry)
        return entry

    async def search_paginated(
        self,
        session: AsyncSession,
        *,
        action: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        cursor: str | None = None,
        page_size: int,
    ) -> tuple[Sequence[AuditLog], int, str | None]:
        """Return ``(rows, total, next_cursor)``, newest first.

        Pagination is keyset-based: see
        ``repositories.notifications.NotificationRepository.search_paginated``.
        """
        base_query = select(AuditLog)

        if action:
            base_query = base_query.where(AuditLog.action == action)
        if actor_user_id:
            base_query = base_query.where(AuditLog.actor_user_id == actor_user_id)
        if after:
            base_query = base_query.where(AuditLog.created_at >= after)
        if before:
            base_query = base_query.where(AuditLog.created_at <= before)

        count_query = select(func.count()).select_from(base_query.subquery())
        total: int = (await session.execute(count_query)).scalar_one()

        if cursor:
            cursor_ts, cursor_id = decode_cursor(cursor)
            base_query = base_query.where(
                or_(
                    AuditLog.created_at < cursor_ts,
                    and_(
                        AuditLog.created_at == cursor_ts,
                        AuditLog.id < cursor_id,
                    ),
                )
            )

        result = await session.execute(
            base_query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(page_size + 1)
        )
        rows = list(result.scalars().all())

        next_cursor: str | None = None
        if len(rows) > page_size:
            rows = rows[:page_size]
            last = rows[-1]
            next_cursor = encode_cursor(last.created_at, last.id)

        return rows, total, next_cursor

    async def delete_older_than(self, session: AsyncSession, cutoff: datetime) -> int:
        result = await session.execute(delete(AuditLog).where(AuditLog.created_at < cutoff))
        return result.rowcount  # type: ignore[return-value]


audit_log_repository = AuditLogRepository()
