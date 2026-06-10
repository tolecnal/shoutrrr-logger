"""Rate limiting for the /shoutrrr ingestion endpoint.

Enforced via a DB-backed sliding window over the `notifications` table so the
limit is consistent across all gunicorn workers without extra infrastructure.
"""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models import AccessToken
from repositories.notifications import NotificationRepository, notification_repository
from services.settings import SettingsService, settings_service

WINDOW = timedelta(minutes=1)


class RateLimitService:
    def __init__(
        self,
        repo: NotificationRepository = notification_repository,
        settings: SettingsService = settings_service,
    ) -> None:
        self._repo = repo
        self._settings = settings

    async def enforce(self, session: AsyncSession, token: AccessToken) -> None:
        """Raise HTTP 429 if ``token`` has exceeded its notifications/minute limit.

        Resolution order: per-token override (None = inherit) falls back to the
        global "rate_limit_per_minute" setting. A limit of 0 means unlimited.
        """
        limit = token.rate_limit_override
        if limit is None:
            limit = await self._settings.get_int(session, "rate_limit_per_minute")
        if limit <= 0:
            return

        since = datetime.now(UTC) - WINDOW
        count = await self._repo.count_since(session, token_id=token.id, since=since)
        if count >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    f"Rate limit exceeded: max {limit} notification(s) per minute for this token."
                ),
                headers={"Retry-After": "60"},
            )


rate_limit_service = RateLimitService()
