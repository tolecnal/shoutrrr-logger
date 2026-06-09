"""
Settings endpoints.

GET  /settings         — viewer-accessible, returns all settings with metadata
GET  /admin/settings   — admin only (same data, kept for symmetry)
PATCH /admin/settings  — admin only, bulk update
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin, require_viewer
from database import get_db
from models import User
from schemas import SettingOut, SettingsUpdate
from services.settings import settings_service

public_router = APIRouter(prefix="/settings", tags=["settings"])
admin_router = APIRouter(prefix="/admin/settings", tags=["settings"])


@public_router.get("", response_model=list[SettingOut], summary="Get all application settings")
async def get_settings_public(
    _user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[SettingOut]:
    return [SettingOut.model_validate(s) for s in await settings_service.get_all(db)]


@admin_router.get("", response_model=list[SettingOut], summary="Get all application settings (admin)")
async def get_settings_admin(
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[SettingOut]:
    return [SettingOut.model_validate(s) for s in await settings_service.get_all(db)]


@admin_router.patch("", response_model=list[SettingOut], summary="Update application settings")
async def update_settings(
    body: SettingsUpdate,
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[SettingOut]:
    return [SettingOut.model_validate(s) for s in await settings_service.update(db, body.values)]
