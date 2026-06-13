"""Personal access token management for the current authenticated user."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from database import get_db
from models import AccessToken, User
from schemas import (
    AccessTokenCreated,
    AccessTokenOut,
    PersonalTokenCreate,
    PersonalTokenUpdate,
)
from services.settings import settings_service
from services.tokens import access_token_service

router = APIRouter(prefix="/me", tags=["personal-tokens"])


def _token_out(tok: AccessToken) -> AccessTokenOut:
    return AccessTokenOut.model_validate(tok)


@router.get("/tokens", response_model=list[AccessTokenOut], summary="List my private tokens")
async def list_my_tokens(
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[AccessTokenOut]:
    tokens = await access_token_service.list_personal_tokens(db, user.id)
    return [_token_out(t) for t in tokens]


@router.post(
    "/tokens",
    response_model=AccessTokenCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create a private token",
    description="Creates a private token for the current user. The raw value is shown **once**.",
)
async def create_my_token(
    body: PersonalTokenCreate,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> AccessTokenCreated:
    max_tokens = await settings_service.get_int(db, "max_private_tokens")
    token, raw = await access_token_service.create_personal_token(
        db,
        user.id,
        name=body.name,
        expires_at=body.expires_at,
        max_tokens=max_tokens,
        allow_plugin_dispatch=body.allow_plugin_dispatch,
        allow_email_alerts=body.allow_email_alerts,
    )
    out = AccessTokenCreated.model_validate(token)
    return out.model_copy(update={"raw_token": raw})


@router.patch(
    "/tokens/{token_id}",
    response_model=AccessTokenOut,
    summary="Update a private token",
)
async def update_my_token(
    token_id: uuid.UUID,
    body: PersonalTokenUpdate,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> AccessTokenOut:
    token = await access_token_service.update_personal_token(
        db,
        user.id,
        token_id,
        name=body.name,
        is_active=body.is_active,
        allow_plugin_dispatch=body.allow_plugin_dispatch,
        allow_email_alerts=body.allow_email_alerts,
    )
    return _token_out(token)


@router.delete(
    "/tokens/{token_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a private token",
)
async def delete_my_token(
    token_id: uuid.UUID,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> None:
    await access_token_service.delete_personal_token(db, user.id, token_id)
