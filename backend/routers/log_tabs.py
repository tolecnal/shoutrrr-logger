"""Notification-log tabs for the current authenticated user."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from database import get_db
from models import User
from schemas import LogTabCreate, LogTabOut, LogTabReorder, LogTabUpdate
from services.log_tabs import log_tab_service

router = APIRouter(prefix="/me/tabs", tags=["log-tabs"])


@router.get("", response_model=list[LogTabOut], summary="List my log tabs")
async def list_tabs(
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[LogTabOut]:
    return await log_tab_service.list_tabs(db, user.id)


@router.post(
    "",
    response_model=LogTabOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a log tab",
)
async def create_tab(
    body: LogTabCreate,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> LogTabOut:
    return await log_tab_service.create_tab(db, body, user.id)


@router.put(
    "/order",
    response_model=list[LogTabOut],
    summary="Reorder my log tabs",
)
async def reorder_tabs(
    body: LogTabReorder,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[LogTabOut]:
    return await log_tab_service.reorder_tabs(db, body.ids, user.id)


@router.patch(
    "/{tab_id}",
    response_model=LogTabOut,
    summary="Update a log tab",
)
async def update_tab(
    tab_id: uuid.UUID,
    body: LogTabUpdate,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> LogTabOut:
    return await log_tab_service.update_tab(db, tab_id, body, user.id)


@router.delete(
    "/{tab_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a log tab",
)
async def delete_tab(
    tab_id: uuid.UUID,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> None:
    await log_tab_service.delete_tab(db, tab_id, user.id)
