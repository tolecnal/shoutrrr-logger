"""
/admin/audit-logs endpoints – read-only access to the admin audit trail.
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from database import get_db
from models import User
from schemas import AuditLogOut, PaginatedResponse
from services.audit_logs import audit_log_service

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get(
    "",
    response_model=PaginatedResponse[AuditLogOut],
    summary="List audit log entries",
    description="Returns paginated audit log entries, newest first. Admin only.",
)
async def list_audit_logs(
    action: str | None = Query(None, description="Filter by exact action, e.g. 'token.create'"),
    actor_user_id: uuid.UUID | None = Query(None, description="Filter by acting user"),
    after: datetime | None = Query(None, description="Only entries created at/after this time"),
    before: datetime | None = Query(None, description="Only entries created at/before this time"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[AuditLogOut]:
    return await audit_log_service.list_logs(
        db,
        action=action,
        actor_user_id=actor_user_id,
        after=after,
        before=before,
        page=page,
        page_size=page_size,
    )
