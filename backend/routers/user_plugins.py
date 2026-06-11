from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from database import get_db
from models import User
from schemas import UserPluginOut, UserPluginUpdate
from services.audit_logs import AuditAction, audit_log_service
from services.plugins import plugin_service

router = APIRouter(prefix="/user-plugins", tags=["User Plugins"])


@router.get("", response_model=list[UserPluginOut])
async def list_user_plugins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    return await plugin_service.list_user_plugins(db, current_user.id)


@router.get("/{plugin_id}", response_model=UserPluginOut)
async def get_user_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    return await plugin_service.get_user_plugin(db, current_user.id, plugin_id)


@router.patch("/{plugin_id}", response_model=UserPluginOut)
async def update_user_plugin(
    plugin_id: str,
    body: UserPluginUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    result = await plugin_service.update_user_plugin(db, current_user.id, plugin_id, body)
    await audit_log_service.log(
        db,
        actor=current_user,
        action=AuditAction.PLUGIN_UPDATE,
        target_type="user_plugin",
        target_id=f"{current_user.id}:{plugin_id}",
        details=body.model_dump(exclude_none=True, mode="json"),
        request=request,
    )
    return result
