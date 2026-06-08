"""Business logic for user management and OIDC user provisioning."""

import uuid
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from models import User, UserRole
from repositories.users import UserRepository, user_repository
from schemas import UserCreate, UserUpdate


class UserService:
    def __init__(self, repo: UserRepository = user_repository) -> None:
        self._repo = repo

    async def list_users(self, session: AsyncSession) -> Sequence[User]:
        return await self._repo.list_all(session)

    async def get_user(self, session: AsyncSession, user_id: uuid.UUID) -> User:
        user = await self._repo.get_by_id(session, user_id)
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    async def create_user(self, session: AsyncSession, body: UserCreate) -> User:
        existing = await self._repo.get_by_sub(session, body.sub)
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User with this sub already exists")
        return await self._repo.add(session, User(**body.model_dump()))

    async def update_user(self, session: AsyncSession, user_id: uuid.UUID, body: UserUpdate) -> User:
        user = await self.get_user(session, user_id)
        for field, value in body.model_dump(exclude_none=True).items():
            setattr(user, field, value)
        await session.flush()
        await session.refresh(user)
        return user

    async def delete_user(self, session: AsyncSession, user_id: uuid.UUID, current_user: User) -> None:
        if str(user_id) == str(current_user.id):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete your own account")
        user = await self.get_user(session, user_id)
        await self._repo.delete(session, user)

    async def upsert_from_oidc(
        self,
        session: AsyncSession,
        *,
        sub: str,
        email: str,
        username: str,
        full_name: str | None,
        role: UserRole,
    ) -> User:
        """Create the user on first login, or sync profile/role from the SSO provider."""
        user = await self._repo.get_by_sub(session, sub)
        if user is None:
            return await self._repo.add(
                session,
                User(sub=sub, email=email, username=username, full_name=full_name, role=role),
            )

        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")

        user.email = email
        user.username = username
        user.full_name = full_name
        user.role = role
        await session.flush()
        return user


user_service = UserService()
