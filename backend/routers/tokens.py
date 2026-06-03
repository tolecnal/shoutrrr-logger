"""
/tokens endpoints – admin management of access tokens.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from auth import generate_raw_token, hash_token, require_admin
from database import get_db
from models import AccessToken, User
from schemas import AccessTokenCreate, AccessTokenCreated, AccessTokenOut

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
    result = await db.execute(
        select(AccessToken)
        .options(selectinload(AccessToken.user))
        .order_by(AccessToken.created_at.desc())
    )
    return [_token_out(t) for t in result.scalars().all()]


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
    # Verify target user exists
    user = (await db.execute(select(User).where(User.id == body.user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    raw = generate_raw_token()
    tok = AccessToken(
        user_id=body.user_id,
        name=body.name,
        token_hash=hash_token(raw),
        expires_at=body.expires_at,
    )
    db.add(tok)
    await db.flush()
    await db.refresh(tok, attribute_names=["user"])

    out = AccessTokenCreated.model_validate(tok)
    return out.model_copy(update={"raw_token": raw, "owner_username": user.username})


@router.patch("/{token_id}", response_model=AccessTokenOut, summary="Update a token (rename or deactivate)")
async def update_token(
    token_id: uuid.UUID,
    name: str | None = None,
    is_active: bool | None = None,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AccessTokenOut:
    result = await db.execute(
        select(AccessToken).options(selectinload(AccessToken.user)).where(AccessToken.id == token_id)
    )
    tok = result.scalar_one_or_none()
    if tok is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    if name is not None:
        tok.name = name
    if is_active is not None:
        tok.is_active = is_active
    await db.flush()
    await db.refresh(tok, attribute_names=["user"])
    return _token_out(tok)


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete an access token")
async def delete_token(
    token_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    result = await db.execute(select(AccessToken).where(AccessToken.id == token_id))
    tok = result.scalar_one_or_none()
    if tok is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
    await db.delete(tok)
