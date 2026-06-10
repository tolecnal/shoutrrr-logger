"""Database access for the ``audit_logs`` table."""

import uuid
from collections.abc import Sequence
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog


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
        page: int,
        page_size: int,
    ) -> tuple[Sequence[AuditLog], int]:
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

        result = await session.execute(
            base_query.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return result.scalars().all(), total


audit_log_repository = AuditLogRepository()
