"""Database access for the ``notifications`` table."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from models import AccessToken, Notification
from repositories.cursor import decode_cursor, encode_cursor


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

    async def get_visible_by_id(
        self,
        session: AsyncSession,
        notification_id: uuid.UUID | str,
        *,
        user_id: uuid.UUID | None,
        is_admin: bool,
    ) -> Notification | None:
        """Return the notification if it exists and is visible to the caller.

        Admins see everything. Non-admins see notifications from global
        tokens, orphaned notifications (token deleted), and notifications
        from their own private tokens.
        """
        if isinstance(notification_id, str):
            try:
                notification_id = uuid.UUID(notification_id)
            except ValueError:
                return None

        stmt = select(Notification).where(Notification.id == notification_id)
        if not is_admin:
            stmt = stmt.outerjoin(AccessToken, Notification.token_id == AccessToken.id).where(
                or_(
                    Notification.token_id.is_(None),
                    AccessToken.is_global == True,  # noqa: E712
                    AccessToken.user_id == user_id,
                )
            )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def search_paginated(
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
    ) -> tuple[Sequence[Notification], int, str | None]:
        """Return ``(rows, total, next_cursor)`` for a search-and-paginate query, newest first.

        scope="all"    admin → everything; viewer → global + own private
        scope="global" → notifications from global tokens (or orphaned)
        scope="mine"   → notifications from the caller's own private tokens

        Pagination is keyset-based: ``cursor`` (if given) is the opaque
        ``(received_at, id)`` of the last row of the previous page, decoded
        and applied as a ``WHERE`` filter instead of an ``OFFSET`` so deep
        pagination stays an indexed range scan.
        """
        base_query = select(Notification)

        # Apply scope visibility filter before full-text / date filters
        if scope == "mine":
            # Inner join: only notifications that have a matching private token owned by this user
            base_query = base_query.join(
                AccessToken, Notification.token_id == AccessToken.id
            ).where(
                AccessToken.user_id == user_id,
                AccessToken.is_global == False,  # noqa: E712
            )
        elif scope == "global":
            base_query = base_query.outerjoin(
                AccessToken, Notification.token_id == AccessToken.id
            ).where(
                or_(
                    Notification.token_id.is_(None),
                    AccessToken.is_global == True,  # noqa: E712
                )
            )
        elif not is_admin:
            # scope="all" for a regular viewer: global + own private + orphaned
            base_query = base_query.outerjoin(
                AccessToken, Notification.token_id == AccessToken.id
            ).where(
                or_(
                    Notification.token_id.is_(None),
                    AccessToken.is_global == True,  # noqa: E712
                    and_(
                        AccessToken.user_id == user_id,
                        AccessToken.is_global == False,  # noqa: E712
                    ),
                )
            )
        # else: scope="all" for admin → no filter, sees everything

        if query:
            term = f"%{query}%"
            base_query = base_query.where(
                or_(
                    Notification.message.ilike(term),
                    Notification.title.ilike(term),
                    Notification.sender_name.ilike(term),
                )
            )

        if after:
            base_query = base_query.where(Notification.last_received_at >= after)
        if before:
            base_query = base_query.where(Notification.last_received_at <= before)

        count_query = select(func.count()).select_from(base_query.subquery())
        total: int = (await session.execute(count_query)).scalar_one()

        if cursor:
            cursor_ts, cursor_id = decode_cursor(cursor)
            base_query = base_query.where(
                or_(
                    Notification.last_received_at < cursor_ts,
                    and_(
                        Notification.last_received_at == cursor_ts,
                        Notification.id < cursor_id,
                    ),
                )
            )

        # Fetch one extra row to detect whether a next page exists, without
        # a second query.
        result = await session.execute(
            base_query.order_by(Notification.last_received_at.desc(), Notification.id.desc()).limit(
                page_size + 1
            )
        )
        rows = list(result.scalars().all())

        next_cursor: str | None = None
        if len(rows) > page_size:
            rows = rows[:page_size]
            last = rows[-1]
            next_cursor = encode_cursor(last.last_received_at, last.id)

        return rows, total, next_cursor

    async def add(self, session: AsyncSession, notification: Notification) -> Notification:
        session.add(notification)
        await session.flush()
        await session.refresh(notification)
        return notification

    async def find_recent_by_fingerprint(
        self, session: AsyncSession, fingerprint: str, since: datetime
    ) -> Notification | None:
        result = await session.execute(
            select(Notification)
            .where(
                Notification.fingerprint == fingerprint,
                Notification.last_received_at >= since,
            )
            .order_by(Notification.last_received_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def export_all(
        self,
        session: AsyncSession,
        *,
        query: str | None,
        after: datetime | None,
        before: datetime | None,
    ) -> Sequence[Notification]:
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
        if after:
            base_query = base_query.where(Notification.received_at >= after)
        if before:
            base_query = base_query.where(Notification.received_at <= before)
        result = await session.execute(base_query.order_by(Notification.received_at.desc()))
        return result.scalars().all()

    async def count_since(
        self, session: AsyncSession, *, token_id: uuid.UUID, since: datetime
    ) -> int:
        """Count notifications submitted via ``token_id`` at/after ``since``.

        Used by the rate limiter's sliding window; relies on the composite
        ``ix_notifications_token_last_received`` index for efficiency.

        Filters on ``last_received_at`` rather than ``received_at`` so that
        repeated deliveries of a deduplicated (fingerprint-matched)
        notification — which bump ``occurrences``/``last_received_at`` on the
        original row instead of inserting a new one — keep counting toward
        the limit even after the original ``received_at`` ages out of the
        window.
        """
        result = await session.execute(
            select(func.coalesce(func.sum(Notification.occurrences), 0)).where(
                Notification.token_id == token_id,
                Notification.last_received_at >= since,
            )
        )
        return result.scalar_one()

    async def delete_older_than(self, session: AsyncSession, cutoff: datetime) -> int:
        result = await session.execute(
            delete(Notification).where(Notification.received_at < cutoff)
        )
        return result.rowcount  # type: ignore[return-value]

    async def stats_summary(self, session: AsyncSession, *, days: int = 30) -> dict:
        now = datetime.now(UTC)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        since = today_start - timedelta(days=days - 1)

        total: int = (await session.execute(select(func.count(Notification.id)))).scalar_one()

        today_count: int = (
            await session.execute(
                select(func.count(Notification.id)).where(Notification.received_at >= today_start)
            )
        ).scalar_one()

        week_count: int = (
            await session.execute(
                select(func.count(Notification.id)).where(Notification.received_at >= week_start)
            )
        ).scalar_one()

        # Daily counts — group by truncated day (PostgreSQL date_trunc)
        daily_rows = (
            await session.execute(
                select(
                    func.date_trunc("day", Notification.received_at).label("day"),
                    func.count(Notification.id).label("count"),
                )
                .where(Notification.received_at >= since)
                .group_by("day")
                .order_by("day")
            )
        ).all()

        day_counts: dict[str, int] = {str(r.day.date()): r.count for r in daily_rows}
        by_day = [
            {
                "date": str((today_start - timedelta(days=i)).date()),
                "count": day_counts.get(str((today_start - timedelta(days=i)).date()), 0),
            }
            for i in range(days - 1, -1, -1)
        ]

        sender_rows = (
            await session.execute(
                select(
                    Notification.sender_name,
                    func.count(Notification.id).label("count"),
                )
                .where(Notification.received_at >= since)
                .group_by(Notification.sender_name)
                .order_by(func.count(Notification.id).desc())
                .limit(10)
            )
        ).all()

        top_senders = [{"sender": r.sender_name, "count": r.count} for r in sender_rows]

        return {
            "total": total,
            "today": today_count,
            "this_week": week_count,
            "by_day": by_day,
            "top_senders": top_senders,
        }

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
