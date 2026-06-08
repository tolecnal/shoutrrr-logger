"""
/tokens endpoints – admin management of access tokens.
"""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from database import get_db
from models import AccessToken, User
from schemas import AccessTokenCreate, AccessTokenCreated, AccessTokenOut
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
    summary="Create an access token",
    description="Creates a new access token and returns the raw token value **once**. Store it securely.",
)
async def create_token(
    body: AccessTokenCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AccessTokenCreated:
    token, raw = await access_token_service.create_token(db, body)
    out = AccessTokenCreated.model_validate(token)
    return out.model_copy(
        update={"raw_token": raw, "owner_username": token.user.username if token.user else None}
    )


@router.patch(
    "/{token_id}", response_model=AccessTokenOut, summary="Update a token (rename or deactivate)"
)
async def update_token(
    token_id: uuid.UUID,
    name: str | None = None,
    is_active: bool | None = None,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AccessTokenOut:
    token = await access_token_service.update_token(db, token_id, name=name, is_active=is_active)
    return _token_out(token)


@router.delete(
    "/{token_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an access token"
)
async def delete_token(
    token_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    await access_token_service.delete_token(db, token_id)
