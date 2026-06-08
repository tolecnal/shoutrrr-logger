"""Database access for the ``access_tokens`` table."""

import uuid
from collections.abc import Sequence

from sqlalchemy import select
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


access_token_repository = AccessTokenRepository()
