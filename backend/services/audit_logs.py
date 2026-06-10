"""Business logic for recording and querying admin audit log entries."""

import math
import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from models import AuditLog, User
from repositories.audit_logs import AuditLogRepository, audit_log_repository
from schemas import AuditLogOut, CursorPage


class AuditAction:
    """Known audit action identifiers, in ``<resource>.<verb>`` form."""

    USER_CREATE = "user.create"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    TOKEN_CREATE = "token.create"
    TOKEN_UPDATE = "token.update"
    TOKEN_DELETE = "token.delete"
    SETTINGS_UPDATE = "settings.update"
    PLUGIN_UPDATE = "plugin.update"


# Keys matching this pattern are masked in stored `details` so secrets
# (plugin tokens, passwords, etc.) never end up in the audit log.
_SENSITIVE_KEY_RE = re.compile(r"(token|secret|password|passwd|key|hec|auth)", re.IGNORECASE)
_REDACTED = "***REDACTED***"


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: (
                _REDACTED
                if isinstance(k, str) and isinstance(v, str) and _SENSITIVE_KEY_RE.search(k)
                else _redact(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


class AuditLogService:
    def __init__(self, repo: AuditLogRepository = audit_log_repository) -> None:
        self._repo = repo

    async def log(
        self,
        session: AsyncSession,
        *,
        actor: User,
        action: str,
        target_type: str,
        target_id: str | None = None,
        details: dict[str, Any] | None = None,
        request: Request | None = None,
    ) -> AuditLog:
        ip_address: str | None = None
        if request is not None:
            ip_address = request.headers.get(
                "X-Forwarded-For", request.client.host if request.client else None
            )

        entry = AuditLog(
            actor_user_id=actor.id,
            actor_username=actor.username,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=_redact(details) if details else None,
            ip_address=ip_address,
        )
        return await self._repo.add(session, entry)

    async def list_logs(
        self,
        session: AsyncSession,
        *,
        action: str | None = None,
        actor_user_id: uuid.UUID | None = None,
        after: datetime | None = None,
        before: datetime | None = None,
        cursor: str | None = None,
        page_size: int,
    ) -> CursorPage[AuditLogOut]:
        rows, total, next_cursor = await self._repo.search_paginated(
            session,
            action=action,
            actor_user_id=actor_user_id,
            after=after,
            before=before,
            cursor=cursor,
            page_size=page_size,
        )
        return CursorPage(
            items=[AuditLogOut.model_validate(r) for r in rows],
            total=total,
            page_size=page_size,
            pages=max(1, math.ceil(total / page_size)),
            next_cursor=next_cursor,
        )

    async def purge_old(self, session: AsyncSession, *, retention_days: int) -> int:
        cutoff = datetime.now(UTC) - timedelta(days=retention_days)
        return await self._repo.delete_older_than(session, cutoff)


audit_log_service = AuditLogService()
