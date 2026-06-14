"""
/user-plugins endpoints – per-user plugin configuration profiles.

A user may have multiple named profiles per plugin, each with its own config
and routing rules; every enabled profile is dispatched independently. The
number of profiles per plugin is capped by the "user_plugin_profiles_max"
admin setting (admins are exempt).
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from database import get_db
from models import User
from schemas import (
    PluginProfileCreate,
    PluginProfileOut,
    PluginProfileUpdate,
    UserPluginOut,
)
from services.audit_logs import AuditAction, audit_log_service
from services.plugins import plugin_service

router = APIRouter(prefix="/user-plugins", tags=["User Plugins"])


@router.get("", response_model=list[UserPluginOut])
async def list_user_plugins(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    return await plugin_service.list_user_plugins(db, current_user)


@router.get("/stats/usage", response_model=list[dict])
async def get_user_plugin_usage_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
) -> list[dict]:
    from repositories.plugin_usage import plugin_usage_repo

    stats = await plugin_usage_repo.get_user_stats(db, current_user.id)
    return [
        {
            "date": s.date.isoformat(),
            "plugin_id": s.plugin_id,
            "profile_id": str(s.profile_id),
            "user_id": str(s.user_id) if s.user_id else None,
            "success_count": s.success_count,
            "error_count": s.error_count,
        }
        for s in stats
    ]


@router.get("/{plugin_id}", response_model=UserPluginOut)
async def get_user_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    return await plugin_service.get_user_plugin(db, current_user, plugin_id)


@router.post(
    "/{plugin_id}/profiles",
    response_model=PluginProfileOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_plugin_profile(
    plugin_id: str,
    body: PluginProfileCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    result = await plugin_service.create_user_profile(db, current_user, plugin_id, body)
    await audit_log_service.log(
        db,
        actor=current_user,
        action=AuditAction.PLUGIN_PROFILE_CREATE,
        target_type="user_plugin_profile",
        target_id=f"{plugin_id}:{result.id}",
        details={
            "name": result.name,
            "copied_from": str(body.copy_from) if body.copy_from else None,
        },
        request=request,
    )
    return result


@router.patch("/{plugin_id}/profiles/{profile_id}", response_model=PluginProfileOut)
async def update_user_plugin_profile(
    plugin_id: str,
    profile_id: uuid.UUID,
    body: PluginProfileUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    result = await plugin_service.update_user_profile(db, current_user, plugin_id, profile_id, body)
    await audit_log_service.log(
        db,
        actor=current_user,
        action=AuditAction.PLUGIN_PROFILE_UPDATE,
        target_type="user_plugin_profile",
        target_id=f"{plugin_id}:{profile_id}",
        details=body.model_dump(exclude_none=True, mode="json"),
        request=request,
    )
    return result


@router.delete("/{plugin_id}/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_plugin_profile(
    plugin_id: str,
    profile_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    deleted = await plugin_service.delete_user_profile(db, current_user, plugin_id, profile_id)
    await audit_log_service.log(
        db,
        actor=current_user,
        action=AuditAction.PLUGIN_PROFILE_DELETE,
        target_type="user_plugin_profile",
        target_id=f"{plugin_id}:{profile_id}",
        details={"name": deleted.name},
        request=request,
    )


@router.post("/{plugin_id}/profiles/{profile_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_user_plugin_profile(
    plugin_id: str,
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_viewer),
):
    """Fire a synthetic test notification through this profile's saved config."""
    await plugin_service.test_user_profile(db, current_user, plugin_id, profile_id)
    return {"detail": "Test notification sent"}
