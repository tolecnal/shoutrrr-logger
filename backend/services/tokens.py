"""Business logic for access token management and bearer-token verification."""

import uuid
from collections.abc import Sequence
from datetime import datetime

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
        """Create a global token (admin), returning ``(token, raw_value)``."""
        if body.user_id is not None:
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
            is_global=body.is_global,
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

    # ------------------------------------------------------------------
    # Personal (private) token operations — called from /me/tokens
    # ------------------------------------------------------------------

    async def list_personal_tokens(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> Sequence[AccessToken]:
        return await self._repo.list_by_user(session, user_id, is_global=False)

    async def create_personal_token(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        name: str,
        expires_at: datetime | None,
        max_tokens: int,
    ) -> tuple[AccessToken, str]:
        """Create a private token for a user, enforcing the per-user limit."""
        if max_tokens > 0:
            count = await self._repo.count_by_user(session, user_id, is_global=False)
            if count >= max_tokens:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"You have reached the maximum of {max_tokens} private token(s). "
                        "Delete an existing token to create a new one."
                    ),
                )
        raw = generate_raw_token()
        token = AccessToken(
            user_id=user_id,
            name=name,
            token_hash=hash_token(raw),
            expires_at=expires_at,
            is_global=False,
        )
        await self._repo.add(session, token)
        return token, raw

    async def update_personal_token(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        token_id: uuid.UUID,
        *,
        name: str | None,
        is_active: bool | None,
    ) -> AccessToken:
        token = await self._repo.get_by_id(session, token_id)
        if token is None or token.user_id != user_id or token.is_global:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
        if name is not None:
            token.name = name
        if is_active is not None:
            token.is_active = is_active
        await session.flush()
        return token

    async def delete_personal_token(
        self, session: AsyncSession, user_id: uuid.UUID, token_id: uuid.UUID
    ) -> None:
        token = await self._repo.get_by_id(session, token_id)
        if token is None or token.user_id != user_id or token.is_global:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
        await self._repo.delete(session, token)


access_token_service = AccessTokenService()
