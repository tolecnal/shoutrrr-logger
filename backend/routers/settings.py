"""
Settings endpoints.

GET  /settings         — viewer-accessible, returns all settings with metadata
GET  /admin/settings   — admin only (same data, kept for symmetry)
PATCH /admin/settings  — admin only, bulk update
"""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin, require_viewer
from database import get_db
from models import User
from schemas import SettingOut, SettingsUpdate, SmtpTestRequest
from services.audit_logs import AuditAction, audit_log_service
from services.settings import settings_service
from services.trigger_engine import send_email_async

public_router = APIRouter(prefix="/settings", tags=["settings"])
admin_router = APIRouter(prefix="/admin/settings", tags=["settings"])


@public_router.get("", response_model=list[SettingOut], summary="Get all application settings")
async def get_settings_public(
    _user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[SettingOut]:
    return [SettingOut.model_validate(s) for s in await settings_service.get_all(db)]


@admin_router.get(
    "", response_model=list[SettingOut], summary="Get all application settings (admin)"
)
async def get_settings_admin(
    _user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[SettingOut]:
    return [SettingOut.model_validate(s) for s in await settings_service.get_all(db)]


@admin_router.patch("", response_model=list[SettingOut], summary="Update application settings")
async def update_settings(
    body: SettingsUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[SettingOut]:
    before = {s["key"]: s["value"] for s in await settings_service.get_all(db)}
    result = await settings_service.update(db, body.values)
    after = {s["key"]: s["value"] for s in result}

    changes = {
        key: {"old": before.get(key), "new": after[key]}
        for key in body.values
        if before.get(key) != after.get(key)
    }
    if changes:
        await audit_log_service.log(
            db,
            actor=admin,
            action=AuditAction.SETTINGS_UPDATE,
            target_type="setting",
            details=changes,
            request=request,
        )
    return [SettingOut.model_validate(s) for s in result]


@admin_router.post(
    "/test-smtp", status_code=status.HTTP_204_NO_CONTENT, summary="Test SMTP configuration"
)
async def test_smtp_configuration(
    body: SmtpTestRequest,
    admin: User = Depends(require_admin),
):
    if not admin.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admin user has no email address configured",
        )

    try:
        await send_email_async(
            host=body.smtp_host,
            port=body.smtp_port,
            user=body.smtp_user,
            password=body.smtp_password,
            from_addr=body.smtp_from_address,
            to_addr=admin.email,
            subject="Test Email from Shoutrrr Logger",
            body="This is a test email to verify your SMTP settings.",
            raise_errors=True,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
