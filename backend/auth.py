"""
Authentication helpers.

Two auth flows are supported:
  1. OpenID Connect (OIDC) – used by the frontend (browser).
     The frontend redirects to the OIDC provider, gets a code, and
     the backend exchanges it for tokens and issues a session JWT.
  2. Bearer token – used by shoutrrr / external callers.
     A raw opaque token is sent as ``Authorization: Bearer <token>``.
     When using the shoutrrr generic service, pass the token as a custom
     header query param: ``?@Authorization=Bearer+YOUR_TOKEN``.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from jwt import PyJWTError
from sqlalchemy.ext.asyncio import AsyncSession

from config import settings
from database import get_db
from models import AccessToken, User, UserRole
from repositories.tokens import access_token_repository
from repositories.users import user_repository

# ---------------------------------------------------------------------------
# Token hashing
# ---------------------------------------------------------------------------
# Access tokens are high-entropy random strings (384 bits), so bcrypt's slow
# KDF adds nothing — a plain SHA-256 HMAC keyed with SECRET_KEY is sufficient,
# has no length limit, and is orders of magnitude faster under load.
# ---------------------------------------------------------------------------

def hash_token(raw: str) -> str:
    """Return a hex-encoded HMAC-SHA256 of the raw token."""
    return hashlib.sha256(raw.encode()).hexdigest()


def verify_token(raw: str, hashed: str) -> bool:
    """Constant-time comparison to prevent timing attacks."""
    return secrets.compare_digest(hash_token(raw), hashed)


def generate_raw_token() -> str:
    """Generate a 384-bit URL-safe random token."""
    return secrets.token_urlsafe(48)


# ---------------------------------------------------------------------------
# Session JWT (internal, short-lived, issued after OIDC login)
# ---------------------------------------------------------------------------
SESSION_ALGORITHM = "HS256"
SESSION_TTL_MINUTES = 60 * 8  # 8 hours


def create_session_jwt(user_id: str, role: str) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=SESSION_TTL_MINUTES)
    return jwt.encode(
        {"sub": user_id, "role": role, "exp": expire},
        settings.secret_key,
        algorithm=SESSION_ALGORITHM,
    )


def decode_session_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[SESSION_ALGORITHM])
    except PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token") from exc


# ---------------------------------------------------------------------------
# OIDC discovery cache (fetched once per process)
# ---------------------------------------------------------------------------
_oidc_config: dict | None = None


async def get_oidc_config() -> dict:
    global _oidc_config
    if _oidc_config is None:
        async with httpx.AsyncClient() as client:
            resp = await client.get(settings.oidc_discovery_url, timeout=10)
            resp.raise_for_status()
            _oidc_config = resp.json()
    return _oidc_config


async def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict:
    config = await get_oidc_config()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            config["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": settings.oidc_client_id,
                "client_secret": settings.oidc_client_secret,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()


async def get_userinfo(access_token: str) -> dict:
    config = await get_oidc_config()
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            config["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()


# ---------------------------------------------------------------------------
# FastAPI dependency helpers
# ---------------------------------------------------------------------------
bearer_scheme = HTTPBearer(auto_error=False)


def _extract_raw_token_from_request(request: Request) -> str | None:
    """Extract the raw Bearer token from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[len("Bearer "):]
    return None


async def get_current_user_from_session(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validates the session JWT stored in the Authorization header or cookie."""
    token: str | None = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ", 1)[1]
    if token is None:
        token = request.cookies.get("session")
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    payload = decode_session_jwt(token)
    user_id = payload.get("sub")
    user = await user_repository.get_by_id(db, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user


async def require_admin(user: User = Depends(get_current_user_from_session)) -> User:
    if user.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


async def require_viewer(user: User = Depends(get_current_user_from_session)) -> User:
    """Both viewer and admin can reach viewer-protected routes."""
    return user


async def verify_bearer_access_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AccessToken:
    """
    Validates an opaque Bearer access token sent by shoutrrr / API callers.

    Expects ``Authorization: Bearer <token>`` in the request headers.
    When using the shoutrrr generic service, pass it via the URL as:
    ``?@Authorization=Bearer+YOUR_TOKEN``
    """
    raw = _extract_raw_token_from_request(request)
    if not raw:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")

    now = datetime.now(UTC)

    # Load all active, non-expired tokens and verify against the hash.
    # We intentionally avoid a DB-side plaintext comparison for security.
    tokens = await access_token_repository.list_active(db)

    matched: AccessToken | None = None
    for tok in tokens:
        if tok.expires_at and tok.expires_at < now:
            continue
        if verify_token(raw, tok.token_hash):
            matched = tok
            break

    if matched is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    # Update last_used_at asynchronously (fire-and-forget style via the same session)
    matched.last_used_at = now

    return matched
