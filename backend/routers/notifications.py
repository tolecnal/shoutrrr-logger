"""
/notifications endpoints – read/search stored notifications.
Requires at minimum viewer role.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from database import get_db
from models import User, UserRole
from schemas import (
    CursorPage,
    NotificationDeleteRequest,
    NotificationDeleteResult,
    NotificationOut,
    NotificationSearchFilters,
    NotificationStateUpdate,
    NotificationStats,
)
from services.audit_logs import AuditAction, audit_log_service
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
    q: str | None = Query(None, max_length=2000),
    after: datetime | None = Query(None),
    before: datetime | None = Query(None),
    scope: str = Query(
        "all",
        pattern="^(all|global|mine)$",
        description="all=visible to caller, global=global tokens only, mine=own private tokens only",
    ),
    format: str = Query("csv", pattern="^(csv|json)$", description="Export format: csv or json"),
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    if format == "json":
        data = await notification_service.export_json(
            db,
            query=q,
            after=after,
            before=before,
            scope=scope,
            user_id=user.id,
            is_admin=(user.role == UserRole.admin),
        )
        return StreamingResponse(
            iter([data]),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=notifications.json"},
        )
    csv_data = await notification_service.export_csv(
        db,
        query=q,
        after=after,
        before=before,
        scope=scope,
        user_id=user.id,
        is_admin=(user.role == UserRole.admin),
    )
    return StreamingResponse(
        iter([csv_data]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=notifications.csv"},
    )


@router.get(
    "/stream",
    summary="Real-time Server-Sent Events",
    description="Streams an event when a new notification is received or updated.",
    response_class=StreamingResponse,
)
async def stream_notifications(
    _user: User = Depends(require_viewer),
) -> StreamingResponse:
    from services.sse import sse_service

    return StreamingResponse(
        sse_service.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # We don't need buffering on proxies
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/search-filters",
    response_model=NotificationSearchFilters,
    summary="Get available search filters",
    description="Returns distinct values for senders, tags, and severities for auto-complete.",
)
async def get_search_filters(
    _user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> NotificationSearchFilters:
    data = await notification_service.get_search_filters(db)
    return NotificationSearchFilters.model_validate(data)


@router.get(
    "",
    response_model=CursorPage[NotificationOut],
    summary="List notifications",
    description="Returns cursor-paginated notifications, newest first. Supports full-text search via the `q` parameter.",
)
async def list_notifications(
    q: str | None = Query(
        None, max_length=2000, description="Search query – matches title and message"
    ),
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


@router.delete(
    "",
    summary="Bulk delete notifications",
    description="Deletes all notifications matching the provided search filters.",
)
async def bulk_delete_notifications(
    request: Request,
    q: str | None = Query(None, max_length=2000, description="Search query"),
    after: datetime | None = Query(None),
    before: datetime | None = Query(None),
    scope: str = Query(
        "all",
        pattern="^(all|global|mine)$",
    ),
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> dict:
    deleted_count = await notification_service.bulk_delete(
        db,
        query=q,
        after=after,
        before=before,
        scope=scope,
        user_id=user.id,
        is_admin=(user.role == UserRole.admin),
    )
    await audit_log_service.log(
        db,
        actor=user,
        action=AuditAction.NOTIFICATION_BULK_DELETE,
        target_type="notification",
        details={
            "query": q,
            "after": after.isoformat() if after else None,
            "before": before.isoformat() if before else None,
            "scope": scope,
            "deleted_count": deleted_count,
        },
        request=request,
    )
    await db.commit()
    return {"deleted": deleted_count}


@router.post(
    "/delete",
    response_model=NotificationDeleteResult,
    summary="Delete selected notifications",
    description=(
        "Deletes an explicit list of notification IDs (Gmail-style selection). "
        "IDs the caller is not permitted to delete are silently skipped; the "
        "response reports how many were actually deleted."
    ),
)
async def delete_selected_notifications(
    body: NotificationDeleteRequest,
    request: Request,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> NotificationDeleteResult:
    requested, deleted = await notification_service.delete_selected(
        db,
        body.ids,
        user_id=user.id,
        is_admin=(user.role == UserRole.admin),
    )
    await audit_log_service.log(
        db,
        actor=user,
        action=AuditAction.NOTIFICATION_BULK_DELETE,
        target_type="notification",
        details={"mode": "selected", "requested": requested, "deleted_count": deleted},
        request=request,
    )
    await db.commit()
    return NotificationDeleteResult(requested=requested, deleted=deleted)


@router.get(
    "/{notification_id}",
    response_model=NotificationOut,
    summary="Get a single notification",
)
async def get_notification(
    notification_id: str,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    return NotificationOut.model_validate(
        await notification_service.get_notification(
            db,
            notification_id,
            user_id=user.id,
            is_admin=(user.role == UserRole.admin),
        )
    )


@router.patch(
    "/{notification_id}/state",
    response_model=NotificationOut,
    summary="Update notification state",
)
async def update_notification_state(
    notification_id: str,
    update: NotificationStateUpdate,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    from services.settings import settings_service

    # Optional check if states are enabled, though we can just allow it
    enabled = await settings_service.get_bool(db, "alert_states_enabled")
    if not enabled:
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Alert states are disabled by the administrator.",
        )

    return NotificationOut.model_validate(
        await notification_service.update_state(
            db,
            notification_id,
            update.state,
            user_id=user.id,
            is_admin=(user.role == UserRole.admin),
        )
    )
