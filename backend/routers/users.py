"""
/users endpoints – admin CRUD for user management.
"""

import uuid

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import require_admin
from database import get_db
from models import User
from schemas import UserCreate, UserOut, UserUpdate
from services.audit_logs import AuditAction, audit_log_service
from services.users import user_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut], summary="List all users")
async def list_users(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[UserOut]:
    return [UserOut.model_validate(u) for u in await user_service.list_users(db)]


@router.get("/{user_id}", response_model=UserOut, summary="Get a user")
async def get_user(
    user_id: uuid.UUID,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    return UserOut.model_validate(await user_service.get_user(db, user_id))


@router.post(
    "",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a user manually",
)
async def create_user(
    body: UserCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await user_service.create_user(db, body)
    await audit_log_service.log(
        db,
        actor=admin,
        action=AuditAction.USER_CREATE,
        target_type="user",
        target_id=str(user.id),
        details=body.model_dump(mode="json"),
        request=request,
    )
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut, summary="Update a user")
async def update_user(
    user_id: uuid.UUID,
    body: UserUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await user_service.update_user(db, user_id, body)
    await audit_log_service.log(
        db,
        actor=admin,
        action=AuditAction.USER_UPDATE,
        target_type="user",
        target_id=str(user_id),
        details=body.model_dump(exclude_none=True, mode="json"),
        request=request,
    )
    return UserOut.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a user")
async def delete_user(
    user_id: uuid.UUID,
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    deleted = await user_service.delete_user(db, user_id, admin)
    await audit_log_service.log(
        db,
        actor=admin,
        action=AuditAction.USER_DELETE,
        target_type="user",
        target_id=str(user_id),
        details={
            "username": deleted.username,
            "email": deleted.email,
            "role": deleted.role.value,
        },
        request=request,
    )
