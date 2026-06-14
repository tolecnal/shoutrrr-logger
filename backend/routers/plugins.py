"""
Admin routes for plugin management.

GET    /api/v1/admin/plugins                         — list plugins with their global profiles
GET    /api/v1/admin/plugins/{id}                    — get one plugin
PATCH  /api/v1/admin/plugins/{id}                    — update plugin-level settings (allow_user_configs)
POST   /api/v1/admin/plugins/{id}/profiles           — create a global configuration profile
PATCH  /api/v1/admin/plugins/{id}/profiles/{pid}     — update a profile (name/enabled/config/rules)
DELETE /api/v1/admin/plugins/{id}/profiles/{pid}     — delete a profile
POST   /api/v1/admin/plugins/{id}/profiles/{pid}/test — fire a test notification through a profile
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user_from_session
from database import get_db
from models import UserRole
from schemas import (
    PluginOut,
    PluginProfileCreate,
    PluginProfileOut,
    PluginProfileUpdate,
    PluginUpdate,
    PluginUsageStatOut,
)
from services.audit_logs import AuditAction, audit_log_service
from services.notifications import notification_service
from services.plugins import plugin_service

router = APIRouter(prefix="/admin/plugins", tags=["plugins"])


def _require_admin(user=Depends(get_current_user_from_session)):
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return user


@router.get("/custom-field-keys", response_model=list[str])
async def list_custom_field_keys(
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
    limit: int = 500,
) -> list[str]:
    """
    Return the distinct custom_fields keys seen across recent notifications.
    Used by plugin config UIs (e.g. Splunk field-mapping datalists).
    """
    return await notification_service.custom_field_keys(db, limit=limit)


@router.get("/stats/usage", response_model=list[PluginUsageStatOut])
async def get_admin_plugin_usage_stats(
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> list[PluginUsageStatOut]:
    from repositories.plugin_usage import plugin_usage_repo

    stats = await plugin_usage_repo.get_admin_stats(db)
    return [PluginUsageStatOut.model_validate(s) for s in stats]


@router.get("", response_model=list[PluginOut])
async def list_plugins(
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> list[PluginOut]:
    return await plugin_service.list_plugins(db)


@router.get("/{plugin_id}", response_model=PluginOut)
async def get_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> PluginOut:
    return await plugin_service.get_plugin(db, plugin_id)


@router.patch("/{plugin_id}", response_model=PluginOut)
async def update_plugin(
    plugin_id: str,
    body: PluginUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(_require_admin),
) -> PluginOut:
    result = await plugin_service.update_plugin(db, plugin_id, body)
    await audit_log_service.log(
        db,
        actor=user,
        action=AuditAction.PLUGIN_UPDATE,
        target_type="plugin",
        target_id=plugin_id,
        details=body.model_dump(exclude_none=True, mode="json"),
        request=request,
    )
    return result


@router.post(
    "/{plugin_id}/profiles",
    response_model=PluginProfileOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_plugin_profile(
    plugin_id: str,
    body: PluginProfileCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(_require_admin),
) -> PluginProfileOut:
    result = await plugin_service.create_plugin_profile(db, plugin_id, body)
    await audit_log_service.log(
        db,
        actor=user,
        action=AuditAction.PLUGIN_PROFILE_CREATE,
        target_type="plugin_profile",
        target_id=f"{plugin_id}:{result.id}",
        details={
            "name": result.name,
            "copied_from": str(body.copy_from) if body.copy_from else None,
        },
        request=request,
    )
    return result


@router.patch("/{plugin_id}/profiles/{profile_id}", response_model=PluginProfileOut)
async def update_plugin_profile(
    plugin_id: str,
    profile_id: uuid.UUID,
    body: PluginProfileUpdate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(_require_admin),
) -> PluginProfileOut:
    result = await plugin_service.update_plugin_profile(db, plugin_id, profile_id, body)
    await audit_log_service.log(
        db,
        actor=user,
        action=AuditAction.PLUGIN_PROFILE_UPDATE,
        target_type="plugin_profile",
        target_id=f"{plugin_id}:{profile_id}",
        details=body.model_dump(exclude_none=True, mode="json"),
        request=request,
    )
    return result


@router.delete("/{plugin_id}/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plugin_profile(
    plugin_id: str,
    profile_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user=Depends(_require_admin),
) -> None:
    deleted = await plugin_service.delete_plugin_profile(db, plugin_id, profile_id)
    await audit_log_service.log(
        db,
        actor=user,
        action=AuditAction.PLUGIN_PROFILE_DELETE,
        target_type="plugin_profile",
        target_id=f"{plugin_id}:{profile_id}",
        details={"name": deleted.name},
        request=request,
    )


@router.post("/{plugin_id}/profiles/{profile_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_plugin_profile(
    plugin_id: str,
    profile_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> dict[str, str]:
    """Fire a synthetic test notification through this profile's saved config."""
    await plugin_service.test_plugin_profile(db, plugin_id, profile_id)
    return {"detail": "Test notification sent"}
