"""
/notifications endpoints – read/search stored notifications.
Requires at minimum viewer role.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from database import get_db
from models import User
from schemas import NotificationOut, PaginatedResponse
from services.notifications import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])

PAGE_SIZE = 20


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
    _user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[NotificationOut]:
    return await notification_service.list_notifications(db, query=q, page=page, page_size=page_size)


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
    return NotificationOut.model_validate(await notification_service.get_notification(db, notification_id))
