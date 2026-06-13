"""
/tokens endpoints – admin management of access tokens.
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from database import get_db
from models import AccessToken, User
from schemas import AccessTokenCreate, AccessTokenCreated, AccessTokenOut, AccessTokenUpdate
from services.audit_logs import AuditAction, audit_log_service
from services.tokens import access_token_service

router = APIRouter(prefix="/tokens", tags=["access-tokens"])


def _token_out(tok: AccessToken) -> AccessTokenOut:
    out = AccessTokenOut.model_validate(tok)
    out.owner_username = tok.user.username if tok.user else None
    return out


@router.get("", response_model=list[AccessTokenOut], summary="List all access tokens")
async def list_tokens(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AccessTokenOut]:
    return [_token_out(t) for t in await access_token_service.list_tokens(db)]


@router.post(
    "",
    response_model=AccessTokenCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create a global access token",
    description="Creates a global access token and returns the raw value **once**. Store it securely.",
)
async def create_token(
    body: AccessTokenCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AccessTokenCreated:
    # Default owner to the creating admin when not explicitly specified
    effective = body if body.user_id is not None else body.model_copy(update={"user_id": admin.id})
    token, raw = await access_token_service.create_token(db, effective)
    await audit_log_service.log(
        db,
        actor=admin,
        action=AuditAction.TOKEN_CREATE,
        target_type="access_token",
        target_id=str(token.id),
        details={
            "name": effective.name,
            "is_global": effective.is_global,
            "user_id": str(effective.user_id) if effective.user_id else None,
            "rate_limit_override": effective.rate_limit_override,
            "allow_plugin_dispatch": effective.allow_plugin_dispatch,
            "allow_email_alerts": effective.allow_email_alerts,
        },
        request=request,
    )
    out = AccessTokenCreated.model_validate(token)
    return out.model_copy(
        update={"raw_token": raw, "owner_username": token.user.username if token.user else None}
    )


@router.patch(
    "/{token_id}", response_model=AccessTokenOut, summary="Update a token (rename or deactivate)"
)
async def update_token(
    token_id: uuid.UUID,
    body: AccessTokenUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AccessTokenOut:
    token = await access_token_service.update_token(
        db,
        token_id,
        name=body.name,
        is_active=body.is_active,
        rate_limit_override=body.rate_limit_override,
        clear_rate_limit_override=body.clear_rate_limit_override,
        allow_plugin_dispatch=body.allow_plugin_dispatch,
        allow_email_alerts=body.allow_email_alerts,
    )
    details: dict = {}
    if body.name is not None:
        details["name"] = body.name
    if body.is_active is not None:
        details["is_active"] = body.is_active
    if body.clear_rate_limit_override:
        details["rate_limit_override"] = None
    elif body.rate_limit_override is not None:
        details["rate_limit_override"] = body.rate_limit_override
    if body.allow_plugin_dispatch is not None:
        details["allow_plugin_dispatch"] = body.allow_plugin_dispatch
    if body.allow_email_alerts is not None:
        details["allow_email_alerts"] = body.allow_email_alerts
    await audit_log_service.log(
        db,
        actor=admin,
        action=AuditAction.TOKEN_UPDATE,
        target_type="access_token",
        target_id=str(token_id),
        details=details,
        request=request,
    )
    return _token_out(token)


@router.delete(
    "/{token_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an access token"
)
async def delete_token(
    token_id: uuid.UUID,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await access_token_service.delete_token(db, token_id)
    await audit_log_service.log(
        db,
        actor=admin,
        action=AuditAction.TOKEN_DELETE,
        target_type="access_token",
        target_id=str(token_id),
        details={"name": deleted.name, "is_global": deleted.is_global},
        request=request,
    )
