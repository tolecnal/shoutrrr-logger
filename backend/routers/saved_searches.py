"""Saved searches for the current authenticated user."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_viewer
from database import get_db
from models import User
from schemas import SavedSearchCreate, SavedSearchOut, SavedSearchUpdate
from services.saved_searches import saved_search_service

router = APIRouter(prefix="/me/saved-searches", tags=["saved-searches"])


@router.get("", response_model=list[SavedSearchOut], summary="List my saved searches")
async def list_saved_searches(
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> list[SavedSearchOut]:
    return await saved_search_service.list_searches(db, user.id)


@router.post(
    "",
    response_model=SavedSearchOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a saved search",
)
async def create_saved_search(
    body: SavedSearchCreate,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> SavedSearchOut:
    return await saved_search_service.create_search(db, body, user.id)


@router.patch(
    "/{search_id}",
    response_model=SavedSearchOut,
    summary="Update a saved search",
)
async def update_saved_search(
    search_id: uuid.UUID,
    body: SavedSearchUpdate,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> SavedSearchOut:
    return await saved_search_service.update_search(db, search_id, body, user.id)


@router.delete(
    "/{search_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a saved search",
)
async def delete_saved_search(
    search_id: uuid.UUID,
    user: User = Depends(require_viewer),
    db: AsyncSession = Depends(get_db),
) -> None:
    await saved_search_service.delete_search(db, search_id, user.id)
