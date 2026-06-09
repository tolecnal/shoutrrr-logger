"""Database access for the ``access_tokens`` table."""

import uuid
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models import AccessToken


class AccessTokenRepository:
    async def get_by_id(
        self, session: AsyncSession, token_id: uuid.UUID, *, with_user: bool = False
    ) -> AccessToken | None:
        stmt = select(AccessToken).where(AccessToken.id == token_id)
        if with_user:
            stmt = stmt.options(selectinload(AccessToken.user))
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, session: AsyncSession) -> Sequence[AccessToken]:
        result = await session.execute(
            select(AccessToken)
            .options(selectinload(AccessToken.user))
            .order_by(AccessToken.created_at.desc())
        )
        return result.scalars().all()

    async def list_active(self, session: AsyncSession) -> Sequence[AccessToken]:
        result = await session.execute(
            select(AccessToken).where(AccessToken.is_active == True)  # noqa: E712
        )
        return result.scalars().all()

    async def add(self, session: AsyncSession, token: AccessToken) -> AccessToken:
        session.add(token)
        await session.flush()
        await session.refresh(token, attribute_names=["user"])
        return token

    async def delete(self, session: AsyncSession, token: AccessToken) -> None:
        await session.delete(token)

    async def list_by_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        is_global: bool = False,
    ) -> Sequence[AccessToken]:
        result = await session.execute(
            select(AccessToken)
            .where(
                AccessToken.user_id == user_id,
                AccessToken.is_global == is_global,  # noqa: E712
            )
            .order_by(AccessToken.created_at.desc())
        )
        return result.scalars().all()

    async def count_by_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        is_global: bool = False,
    ) -> int:
        result = await session.execute(
            select(func.count(AccessToken.id)).where(
                AccessToken.user_id == user_id,
                AccessToken.is_global == is_global,  # noqa: E712
            )
        )
        return result.scalar_one()


access_token_repository = AccessTokenRepository()
