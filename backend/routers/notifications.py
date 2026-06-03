"""
/notifications endpoints – read/search stored notifications.
Requires at minimum viewer role.
"""

import math

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from database import get_db
from models import Notification, User
from schemas import NotificationOut, PaginatedResponse

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
    base_query = select(Notification)

    if q:
        term = f"%{q}%"
        base_query = base_query.where(
            or_(
                Notification.message.ilike(term),
                Notification.title.ilike(term),
                Notification.sender_name.ilike(term),
            )
        )

    count_query = select(func.count()).select_from(base_query.subquery())
    total: int = (await db.execute(count_query)).scalar_one()

    rows = (
        await db.execute(
            base_query.order_by(Notification.received_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()

    return PaginatedResponse(
        items=[NotificationOut.model_validate(r) for r in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
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
    from fastapi import HTTPException, status  # noqa: PLC0415

    result = await db.execute(select(Notification).where(Notification.id == notification_id))
    notification = result.scalar_one_or_none()
    if notification is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return NotificationOut.model_validate(notification)
