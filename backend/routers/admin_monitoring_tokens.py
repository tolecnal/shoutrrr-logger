import hashlib
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from database import get_db
from models import MonitoringToken
from schemas import MonitoringTokenCreate, MonitoringTokenCreated, MonitoringTokenOut

router = APIRouter()


@router.get("", response_model=list[MonitoringTokenOut], summary="List all monitoring tokens")
async def list_monitoring_tokens(_admin=Depends(require_admin), db: AsyncSession = Depends(get_db)):
    stmt = select(MonitoringToken).order_by(MonitoringToken.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post(
    "",
    response_model=MonitoringTokenCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new monitoring token",
)
async def create_monitoring_token(
    payload: MonitoringTokenCreate,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    token = MonitoringToken(
        name=payload.name,
        token_hash=token_hash,
    )
    db.add(token)
    await db.commit()
    await db.refresh(token)

    return MonitoringTokenCreated(
        id=token.id,
        name=token.name,
        created_at=token.created_at,
        last_used_at=token.last_used_at,
        is_active=token.is_active,
        raw_token=raw_token,
    )


@router.patch("/{token_id}", response_model=MonitoringTokenOut, summary="Update a monitoring token")
async def update_monitoring_token(
    token_id: UUID,
    name: str | None = None,
    is_active: bool | None = None,
    _admin=Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    token = await db.get(MonitoringToken, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    if name is not None:
        token.name = name
    if is_active is not None:
        token.is_active = is_active

    await db.commit()
    await db.refresh(token)
    return token


@router.delete(
    "/{token_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a monitoring token"
)
async def delete_monitoring_token(
    token_id: UUID, _admin=Depends(require_admin), db: AsyncSession = Depends(get_db)
):
    token = await db.get(MonitoringToken, token_id)
    if not token:
        raise HTTPException(status_code=404, detail="Token not found")

    await db.delete(token)
    await db.commit()
