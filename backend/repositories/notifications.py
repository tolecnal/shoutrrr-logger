"""Database access for the ``notifications`` table."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import Notification


class NotificationRepository:
    async def get_by_id(
        self, session: AsyncSession, notification_id: uuid.UUID | str
    ) -> Notification | None:
        if isinstance(notification_id, str):
            try:
                notification_id = uuid.UUID(notification_id)
            except ValueError:
                return None
        result = await session.execute(
            select(Notification).where(Notification.id == notification_id)
        )
        return result.scalar_one_or_none()

    async def search_paginated(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        page: int,
        page_size: int,
    ) -> tuple[Sequence[Notification], int]:
        """Return ``(rows, total)`` for a search-and-paginate query, newest first."""
        base_query = select(Notification)

        if query:
            term = f"%{query}%"
            base_query = base_query.where(
                or_(
                    Notification.message.ilike(term),
                    Notification.title.ilike(term),
                    Notification.sender_name.ilike(term),
                )
            )

        count_query = select(func.count()).select_from(base_query.subquery())
        total: int = (await session.execute(count_query)).scalar_one()

        result = await session.execute(
            base_query.order_by(Notification.received_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return result.scalars().all(), total

    async def add(self, session: AsyncSession, notification: Notification) -> Notification:
        session.add(notification)
        await session.flush()
        await session.refresh(notification)
        return notification

    async def distinct_custom_field_keys(self, session: AsyncSession, limit: int) -> list[str]:
        """
        Enumerate distinct keys seen in the JSON ``raw_payload`` column via
        PostgreSQL's ``jsonb_object_keys()``, skipping rows whose payload isn't
        a JSON object (NULL, plain text messages, arrays, etc.).
        """
        sql = text("""
            SELECT DISTINCT k
            FROM (
                SELECT jsonb_object_keys(raw_payload::jsonb) AS k
                FROM notifications
                WHERE raw_payload IS NOT NULL
                  AND raw_payload LIKE '{%'
                LIMIT :limit
            ) sub
            ORDER BY k
        """)
        result = await session.execute(sql, {"limit": limit})
        return [row[0] for row in result.fetchall()]


notification_repository = NotificationRepository()
