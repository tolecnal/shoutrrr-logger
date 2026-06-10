"""
/notifications endpoints – read/search stored notifications.
Requires at minimum viewer role.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from database import get_db
from models import User, UserRole
from schemas import CursorPage, NotificationOut, NotificationStats
from services.notifications import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])

PAGE_SIZE = 20


@router.get(
    "/stats",
    response_model=NotificationStats,
    summary="Notification statistics",
)
async def get_stats(
    days: int = Query(30, ge=1, le=365, description="Number of days for the daily breakdown"),
    _user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> NotificationStats:
    return await notification_service.get_stats(db, days=days)


@router.get(
    "/export",
    summary="Export notifications as CSV or JSON",
    response_class=StreamingResponse,
)
async def export_notifications(
    q: str | None = Query(None),
    after: datetime | None = Query(None),
    before: datetime | None = Query(None),
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format: csv or json"),
    _user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if format == "json":
        data = await notification_service.export_json(db, query=q, after=after, before=before)
        return StreamingResponse(
            iter([data]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=notifications.json"},
        )
    csv_data = await notification_service.export_csv(db, query=q, after=after, before=before)
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=notifications.csv"},
    )


@router.get(
    "",
    response_model=CursorPage[NotificationOut],
    summary="List notifications",
    description="Returns cursor-paginated notifications, newest first. Supports full-text search via the `q` parameter.",
)
async def list_notifications(
    q: str | None = Query(None, description="Search query – matches title and message"),
    cursor: str | None = Query(
        None, description="Opaque cursor from a previous response's `next_cursor`"
    ),
    page_size: int = Query(PAGE_SIZE, ge=1, le=100),
    after: datetime | None = Query(
        None, description="Only return notifications received after this datetime (ISO 8601)"
    ),
    before: datetime | None = Query(
        None, description="Only return notifications received before this datetime (ISO 8601)"
    ),
    scope: str = Query(
        "all",
        pattern="^(all|global|mine)$",
        description="all=visible to caller, global=global tokens only, mine=own private tokens only",
    ),
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> CursorPage[NotificationOut]:
    return await notification_service.list_notifications(
        db,
        query=q,
        cursor=cursor,
        page_size=page_size,
        after=after,
        before=before,
        scope=scope,
        user_id=user.id,
        is_admin=(user.role == UserRole.admin),
    )


@router.get(
    "/{notification_id}",
    response_model=NotificationOut,
    summary="Get a single notification",
)
async def get_notification(
    notification_id: str,
    _user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    return NotificationOut.model_validate(
        await notification_service.get_notification(db, notification_id)
    )
