"""
Admin routes for plugin management.

GET  /api/admin/plugins          — list all registered plugins with their DB config
GET  /api/admin/plugins/{id}     — get one plugin
PATCH /api/admin/plugins/{id}    — update enabled flag and/or config dict
POST /api/admin/plugins/{id}/test — trigger a test notification through the plugin
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user_from_session
from database import get_db
from models import UserRole
from schemas import PluginOut, PluginUpdate
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
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> PluginOut:
    return await plugin_service.update_plugin(db, plugin_id, body)


@router.post("/{plugin_id}/test", status_code=status.HTTP_202_ACCEPTED)
async def test_plugin(
    plugin_id: str,
    db: AsyncSession = Depends(get_db),
    _user=Depends(_require_admin),
) -> dict:
    """Fire a synthetic test notification through the plugin."""
    await plugin_service.test_plugin(db, plugin_id)
