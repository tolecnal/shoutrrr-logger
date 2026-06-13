"""Database access for the ``notifications`` table."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import String, and_, delete, func, not_, or_, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from models import AccessToken, Notification
from repositories.cursor import decode_cursor, encode_cursor
from utils.search_parser import AndNode, ASTNode, NotNode, OrNode, TermNode, parse_query

# Reject absurdly long user-supplied regex patterns (e.g. message:/.../) before
# they ever reach PostgreSQL — both as a sanity check and to keep the compiled
# automaton small.
MAX_REGEX_LENGTH = 200


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

    async def _apply_search_timeout(self, session: AsyncSession) -> None:
        """Bound how long a single search/export/bulk-delete query may run.

        Only takes effect on PostgreSQL — ``SET LOCAL`` isn't valid on the
        SQLite backend used by the test suite, and is reset automatically
        when the surrounding transaction ends.
        """
        if session.get_bind().dialect.name == "postgresql":
            timeout_ms = int(settings.search_statement_timeout_ms)
            await session.execute(text(f"SET LOCAL statement_timeout = {timeout_ms}"))

    def _parse_time_string(self, val: str) -> datetime | None:
        try:
            val = val.lower().strip()
            if val.endswith("m") and val[:-1].isdigit():
                return datetime.now(UTC) - timedelta(minutes=int(val[:-1]))
            if val.endswith("h") and val[:-1].isdigit():
                return datetime.now(UTC) - timedelta(hours=int(val[:-1]))
            if val.endswith("d") and val[:-1].isdigit():
                return datetime.now(UTC) - timedelta(days=int(val[:-1]))
            # Try absolute ISO
            return datetime.fromisoformat(val).astimezone(UTC)
        except ValueError:
            return None

    def _build_search_query(
        self,
        base_query,
        *,
        query: str | None,
        after: datetime | None,
        before: datetime | None,
        scope: str,
        user_id: uuid.UUID | None,
        is_admin: bool,
    ):
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
            ast = parse_query(query)
            if ast:

                def compile_ast(node: ASTNode) -> Any:
                    if isinstance(node, AndNode):
                        return and_(compile_ast(node.left), compile_ast(node.right))
                    elif isinstance(node, OrNode):
                        return or_(compile_ast(node.left), compile_ast(node.right))
                    elif isinstance(node, NotNode):
                        return not_(compile_ast(node.expr))
                    elif isinstance(node, TermNode):
                        key = node.field
                        value = node.value
                        is_regex = node.is_regex
                        exact = node.exact

                        if is_regex:
                            if len(value) > MAX_REGEX_LENGTH:
                                raise ValueError(
                                    f"Regex pattern too long (max {MAX_REGEX_LENGTH} characters)"
                                )
                            import re

                            try:
                                re.compile(value)
                            except re.error as exc:
                                raise ValueError(f"Invalid regex pattern '{value}': {exc}") from exc

                        def _substring_pattern(val: str) -> str:
                            # Unquoted term: escape the LIKE metacharacters so user
                            # input can't inject wildcards, then translate * and ?
                            # into SQL wildcards.
                            escaped = (
                                val.replace("\\", "\\\\")
                                .replace("%", "\\%")
                                .replace("_", "\\_")
                                .replace("*", "%")
                                .replace("?", "_")
                            )
                            return f"%{escaped}%"

                        def build_condition(col, val, regex_mode, exact_mode=False):
                            if regex_mode:
                                return col.regexp_match(val, flags="i")
                            if exact_mode:
                                # Quoted term: match the whole field exactly,
                                # case-insensitively (no wildcards, no substring).
                                return func.lower(col) == val.lower()
                            return col.ilike(_substring_pattern(val), escape="\\")

                        if key == "title":
                            return build_condition(Notification.title, value, is_regex, exact)
                        elif key == "message":
                            return build_condition(Notification.message, value, is_regex, exact)
                        elif key == "sender":
                            return build_condition(Notification.sender_name, value, is_regex, exact)
                        elif key == "severity":
                            return build_condition(Notification.severity, value, is_regex, exact)
                        elif key == "tag":
                            if is_regex:
                                return Notification.tags.cast(String).regexp_match(value, flags="i")
                            if exact:
                                # Match one tag element exactly (case-insensitive)
                                # by anchoring on the JSON array element quotes.
                                esc = (
                                    value.replace("\\", "\\\\")
                                    .replace("%", "\\%")
                                    .replace("_", "\\_")
                                )
                                return Notification.tags.cast(String).ilike(
                                    f'%"{esc}"%', escape="\\"
                                )
                            return Notification.tags.cast(String).ilike(
                                _substring_pattern(value), escape="\\"
                            )
                        elif key == "after":
                            dt = self._parse_time_string(value)
                            if dt:
                                return Notification.last_received_at >= dt
                            return text("1=1")  # Skip if invalid date
                        elif key == "before":
                            dt = self._parse_time_string(value)
                            if dt:
                                return Notification.last_received_at <= dt
                            return text("1=1")  # Skip if invalid date
                        else:
                            # Free-text
                            return or_(
                                build_condition(Notification.message, value, is_regex, exact),
                                build_condition(Notification.title, value, is_regex, exact),
                                build_condition(Notification.sender_name, value, is_regex, exact),
                            )

                    return text("1=1")

                compiled_filter = compile_ast(ast)
                base_query = base_query.where(compiled_filter)

        if after:
            base_query = base_query.where(Notification.last_received_at >= after)
        if before:
            base_query = base_query.where(Notification.last_received_at <= before)

        return base_query

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
        """Return ``(rows, total, next_cursor)`` for a search-and-paginate query, newest first."""
        base_query = select(Notification)
        base_query = self._build_search_query(
            base_query,
            query=query,
            after=after,
            before=before,
            scope=scope,
            user_id=user_id,
            is_admin=is_admin,
        )

        if query:
            await self._apply_search_timeout(session)

        try:
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
                base_query.order_by(
                    Notification.last_received_at.desc(), Notification.id.desc()
                ).limit(page_size + 1)
            )
        except OperationalError as exc:
            raise ValueError("Search query timed out — try a more specific search.") from exc
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
        scope: str = "all",
        user_id: uuid.UUID | None = None,
        is_admin: bool = False,
    ) -> Sequence[Notification]:
        base_query = select(Notification)
        base_query = self._build_search_query(
            base_query,
            query=query,
            after=after,
            before=before,
            scope=scope,
            user_id=user_id,
            is_admin=is_admin,
        )
        base_query = base_query.order_by(Notification.last_received_at.desc())

        if query:
            await self._apply_search_timeout(session)

        try:
            result = await session.execute(base_query)
        except OperationalError as exc:
            raise ValueError("Search query timed out — try a more specific search.") from exc
        return result.scalars().all()

    def _deletable_token_subquery(self, user_id: uuid.UUID | None):
        """Subquery of access-token IDs a non-admin caller may delete from:
        their own, non-global tokens. Used to gate all delete operations so a
        viewer can never delete global or other users' notifications, even
        though they can *see* global ones."""
        return select(AccessToken.id).where(
            AccessToken.user_id == user_id,
            AccessToken.is_global == False,  # noqa: E712
        )

    def _apply_deletable_filter(self, stmt, *, user_id: uuid.UUID | None, is_admin: bool):
        """Restrict a Notification statement to rows the caller may delete.

        Admins may delete anything. Non-admins may only delete notifications
        originating from their own non-global tokens (not global, not orphaned,
        not other users')."""
        if is_admin:
            return stmt
        return stmt.where(Notification.token_id.in_(self._deletable_token_subquery(user_id)))

    async def deletable_ids_among(
        self,
        session: AsyncSession,
        ids: Sequence[uuid.UUID],
        *,
        user_id: uuid.UUID | None,
        is_admin: bool,
    ) -> set[uuid.UUID]:
        """Of ``ids``, return those the caller is permitted to delete.

        Used by the list endpoint to populate ``can_delete`` per row without an
        N+1 (one query per page)."""
        if not ids:
            return set()
        if is_admin:
            # Admins can delete anything they can see; the page already only
            # contains visible rows, so every id qualifies.
            return set(ids)
        stmt = self._apply_deletable_filter(
            select(Notification.id).where(Notification.id.in_(ids)),
            user_id=user_id,
            is_admin=is_admin,
        )
        result = await session.execute(stmt)
        return set(result.scalars().all())

    async def delete_by_ids(
        self,
        session: AsyncSession,
        ids: Sequence[uuid.UUID],
        *,
        user_id: uuid.UUID | None,
        is_admin: bool,
    ) -> int:
        """Delete the given notifications the caller is permitted to delete.

        IDs the caller may not delete (or that don't exist) are silently
        skipped; the returned count reflects rows actually deleted."""
        if not ids:
            return 0
        id_filter = select(Notification.id).where(Notification.id.in_(ids))
        id_filter = self._apply_deletable_filter(id_filter, user_id=user_id, is_admin=is_admin)
        result = await session.execute(delete(Notification).where(Notification.id.in_(id_filter)))
        return result.rowcount

    async def delete_bulk(
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
        base_query = select(Notification.id)
        base_query = self._build_search_query(
            base_query,
            query=query,
            after=after,
            before=before,
            scope=scope,
            user_id=user_id,
            is_admin=is_admin,
        )
        # Beyond view-scoping, a non-admin may only delete from their own
        # non-global tokens — they can see global notifications but not delete
        # them. (No-op for admins.)
        base_query = self._apply_deletable_filter(base_query, user_id=user_id, is_admin=is_admin)
        delete_stmt = delete(Notification).where(Notification.id.in_(base_query))

        if query:
            await self._apply_search_timeout(session)

        try:
            result = await session.execute(delete_stmt)
        except OperationalError as exc:
            raise ValueError("Search query timed out — try a more specific search.") from exc
        return result.rowcount

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

    async def get_recent_filters(
        self, session: AsyncSession, limit: int = 1000
    ) -> tuple[set[str], set[str]]:
        """Fetch the most recent notifications and extract distinct senders and tags."""
        stmt = (
            select(Notification.sender_name, Notification.tags)
            .order_by(Notification.id.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)

        senders = set()
        tags = set()
        for sender, tag_list in result:
            if sender:
                senders.add(sender)
            if tag_list:
                for t in tag_list:
                    tags.add(t)
        return senders, tags


notification_repository = NotificationRepository()
