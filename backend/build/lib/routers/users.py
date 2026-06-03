"""
/users endpoints – admin CRUD for user management.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from database import get_db
from models import User
from schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut], summary="List all users")
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return [UserOut.model_validate(u) for u in result.scalars().all()]


@router.get("/{user_id}", response_model=UserOut, summary="Get a user")
async def get_user(
    user_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return UserOut.model_validate(user)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED, summary="Create a user manually")
async def create_user(
    body: UserCreate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    existing = (await db.execute(select(User).where(User.sub == body.sub))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this sub already exists")
    user = User(**body.model_dump())
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut, summary="Update a user")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(user, field, value)
    await db.flush()
    await db.refresh(user)
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a user")
async def delete_user(
    user_id: uuid.UUID,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    if str(user_id) == str(admin.id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    await db.delete(user)
