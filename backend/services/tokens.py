"""Business logic for access token management and bearer-token verification."""

import uuid
from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import generate_raw_token, hash_token
from models import AccessToken
from repositories.tokens import AccessTokenRepository, access_token_repository
from repositories.users import UserRepository, user_repository
from schemas import AccessTokenCreate


class AccessTokenService:
    def __init__(
        self,
        repo: AccessTokenRepository = access_token_repository,
        user_repo: UserRepository = user_repository,
    ) -> None:
        self._repo = repo
        self._user_repo = user_repo

    async def list_tokens(self, session: AsyncSession) -> Sequence[AccessToken]:
        return await self._repo.list_all(session)

    async def create_token(
        self, session: AsyncSession, body: AccessTokenCreate
    ) -> tuple[AccessToken, str]:
        """Create a token, returning ``(token, raw_value)``. The raw value is shown once."""
        user = await self._user_repo.get_by_id(session, body.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found"
            )

        raw = generate_raw_token()
        token = AccessToken(
            user_id=body.user_id,
            name=body.name,
            token_hash=hash_token(raw),
            expires_at=body.expires_at,
        )
        await self._repo.add(session, token)
        return token, raw

    async def update_token(
        self,
        session: AsyncSession,
        token_id: uuid.UUID,
        *,
        name: str | None,
        is_active: bool | None,
    ) -> AccessToken:
        token = await self._repo.get_by_id(session, token_id, with_user=True)
        if token is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
        if name is not None:
            token.name = name
        if is_active is not None:
            token.is_active = is_active
        await session.flush()
        await session.refresh(token, attribute_names=["user"])
        return token

    async def delete_token(self, session: AsyncSession, token_id: uuid.UUID) -> None:
        token = await self._repo.get_by_id(session, token_id)
        if token is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
        await self._repo.delete(session, token)


access_token_service = AccessTokenService()
