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
from models import User
from schemas import NotificationOut, NotificationStats, PaginatedResponse
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
    summary="Export notifications as CSV",
    response_class=StreamingResponse,
)
async def export_notifications(
    q: str | None = Query(None),
    after: datetime | None = Query(None),
    before: datetime | None = Query(None),
    _user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    csv_data = await notification_service.export_csv(db, query=q, after=after, before=before)
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=notifications.csv"},
    )


@router.get(
    "",
    response_model=PaginatedResponse[NotificationOut],
    summary="List notifications",
    description="Returns paginated notifications, newest first. Supports full-text search via the `q` parameter.",
)
async def list_notifications(
    q: str | None = Query(None, description="Search query – matches title and message"),
    page: int = Query(1, ge=1),
    page_size: int = Query(PAGE_SIZE, ge=1, le=100),
    after: datetime | None = Query(
        None, description="Only return notifications received after this datetime (ISO 8601)"
    ),
    before: datetime | None = Query(
        None, description="Only return notifications received before this datetime (ISO 8601)"
    ),
    _user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NotificationOut]:
    return await notification_service.list_notifications(
        db, query=q, page=page, page_size=page_size, after=after, before=before
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
