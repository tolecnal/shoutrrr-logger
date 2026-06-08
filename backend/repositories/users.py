"""Database access for the ``users`` table."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import User


class UserRepository:
    async def get_by_id(self, session: AsyncSession, user_id: uuid.UUID | str) -> User | None:
        if isinstance(user_id, str):
            try:
                user_id = uuid.UUID(user_id)
            except ValueError:
                return None
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_sub(self, session: AsyncSession, sub: str) -> User | None:
        result = await session.execute(select(User).where(User.sub == sub))
        return result.scalar_one_or_none()

    async def list_all(self, session: AsyncSession) -> Sequence[User]:
        result = await session.execute(select(User).order_by(User.created_at.desc()))
        return result.scalars().all()

    async def add(self, session: AsyncSession, user: User) -> User:
        session.add(user)
        await session.flush()
        await session.refresh(user)
        return user

    async def delete(self, session: AsyncSession, user: User) -> None:
        await session.delete(user)


user_repository = UserRepository()
