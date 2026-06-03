"""
shoutrrr-logger – FastAPI entry point.

Run locally:   uvicorn main:app --reload
Production:    gunicorn main:app -k uvicorn.workers.UvicornWorker -w 4
"""

import urllib.parse
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from jose import jwt as jose_jwt

from auth import (
    create_session_jwt,
    exchange_code_for_tokens,
    get_current_user_from_session,
    get_oidc_config,
    get_userinfo,
)
from config import settings
from database import get_db, init_db
from models import User, UserRole
from plugins import registry as plugin_registry
from routers import notifications, plugins, shoutrrr, tokens, users
from schemas import OIDCCallbackResponse, UserOut
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    await init_db()
    plugin_registry.discover()
    yield


app = FastAPI(
    title="shoutrrr-logger",
    description=(
        "Receives notifications from shoutrrr services, stores them to PostgreSQL, "
        "and provides a web UI for viewing and managing them."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.app_base_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(shoutrrr.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(users.router, prefix="/api/admin")
app.include_router(tokens.router, prefix="/api/admin")
app.include_router(plugins.router, prefix="/api")


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@app.get("/api/auth/login", summary="Initiate OIDC login", tags=["auth"])
async def oidc_login(redirect_after: str = "/log") -> RedirectResponse:
    """Redirects the browser to the OIDC provider's authorization endpoint."""
    config = await get_oidc_config()
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": f"{settings.app_base_url}/api/auth/callback",
            "scope": settings.oidc_scopes,
            "state": redirect_after,
        }
    )
    return RedirectResponse(url=f"{config['authorization_endpoint']}?{params}")


def _resolve_claim_path(userinfo: dict, dotted_path: str) -> object:
    """Walk a dot-separated path through a nested dict and return the leaf value."""
    obj: object = userinfo
    for part in dotted_path.split("."):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(part)
    return obj


def _extract_role_from_claims(userinfo: dict) -> tuple[UserRole | None, str]:
    """
    Determine the user's role from the OIDC UserInfo claims.

    Resolution order:
    1. The explicit ``OIDC_ROLES_CLAIM`` dot-path (e.g. ``realm_access.roles``).
    2. Keycloak client-role fallback: ``resource_access.<client_id>.roles``.

    Returns a (role | None, diagnostic_message) tuple. When role is None the
    diagnostic message explains exactly what was checked and found, to aid
    configuration debugging.
    """
    checked: list[str] = []

    # Source 1 – configured claim path
    val = _resolve_claim_path(userinfo, settings.oidc_roles_claim)
    val1_found = isinstance(val, list)
    val1_roles: list[str] = [str(r) for r in val] if val1_found else []
    checked.append(
        f"'{settings.oidc_roles_claim}' → "
        + (f"found list {val1_roles}" if val1_found else f"not found (got {type(val).__name__}: {val!r})")
    )

    if val1_found:
        if settings.oidc_role_admin in val1_roles:
            return UserRole.admin, ""
        if settings.oidc_role_viewer in val1_roles:
            return UserRole.viewer, ""

    # Source 2 – Keycloak client-role fallback
    client_roles_path = f"resource_access.{settings.oidc_client_id}.roles"
    if client_roles_path != settings.oidc_roles_claim:
        val2 = _resolve_claim_path(userinfo, client_roles_path)
        val2_found = isinstance(val2, list)
        val2_roles: list[str] = [str(r) for r in val2] if val2_found else []
        checked.append(
            f"'{client_roles_path}' → "
            + (f"found list {val2_roles}" if val2_found else f"not found (got {type(val2).__name__}: {val2!r})")
        )

        if val2_found:
            if settings.oidc_role_admin in val2_roles:
                return UserRole.admin, ""
            if settings.oidc_role_viewer in val2_roles:
                return UserRole.viewer, ""

    top_level_keys = list(userinfo.keys())
    diagnostic = (
        f"No recognised role ('{settings.oidc_role_viewer}' or '{settings.oidc_role_admin}') found. "
        f"Checked: {'; '.join(checked)}. "
        f"Top-level UserInfo keys present: {top_level_keys}."
    )
    return None, diagnostic


@app.get(
    "/api/auth/callback",
    response_model=OIDCCallbackResponse,
    summary="OIDC authorization code callback",
    tags=["auth"],
)
async def oidc_callback(
    code: str,
    state: str = "/log",
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """
    Exchanges the authorization code for tokens, upserts the user, and sets a
    session cookie.

    Roles are always read from the SSO provider on every login via the claim
    configured in ``OIDC_ROLES_CLAIM`` (default: ``realm_access.roles`` for
    Keycloak).  If the user carries neither the viewer nor admin role they are
    refused with 403 — deactivate or remove roles in your SSO provider to
    revoke access.
    """
    redirect_uri = f"{settings.app_base_url}/api/auth/callback"
    token_response = await exchange_code_for_tokens(code, redirect_uri)
    access_token: str = token_response["access_token"]

    # Fetch profile claims from the UserInfo endpoint.
    userinfo = await get_userinfo(access_token)

    # Decode the access token payload WITHOUT signature verification.
    # We trust it was issued by the OIDC provider we just talked to; we only
    # need the role claims which Keycloak puts in the token body but does NOT
    # expose on the UserInfo endpoint unless a protocol mapper is configured.
    # Merging gives _extract_role_from_claims the full picture.
    try:
        token_claims: dict = jose_jwt.get_unverified_claims(access_token)
    except Exception:
        token_claims = {}

    # Merge: token_claims first so that UserInfo values (sub, email, etc.)
    # take precedence for profile fields, but role claims from the token body
    # are also available.
    merged_claims: dict = {**token_claims, **userinfo}

    sub: str = merged_claims["sub"]
    email: str = merged_claims.get("email", "")
    username: str = merged_claims.get("preferred_username", merged_claims.get("name", sub))
    full_name: str | None = merged_claims.get("name")

    role, diagnostic = _extract_role_from_claims(merged_claims)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=diagnostic,
        )

    result = await db.execute(select(User).where(User.sub == sub))
    user: User | None = result.scalar_one_or_none()

    if user is None:
        # Auto-provision: create the user record on first login.
        user = User(sub=sub, email=email, username=username, full_name=full_name, role=role)
        db.add(user)
        await db.flush()
        await db.refresh(user)
    else:
        if not user.is_active:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
        # Sync profile fields and role from SSO on every login.
        user.email = email
        user.username = username
        user.full_name = full_name
        user.role = role
        await db.flush()

    session_token = create_session_jwt(str(user.id), user.role.value)

    # Redirect to frontend with session cookie set
    destination = state if state.startswith("/") else "/log"
    response = RedirectResponse(url=destination, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="session",
        value=session_token,
        httponly=True,
        samesite="lax",
        secure=settings.app_base_url.startswith("https"),
        max_age=60 * 60 * 8,
    )
    return response


@app.api_route(
    "/api/auth/logout",
    methods=["GET", "POST"],
    tags=["auth"],
    summary="Clear session cookie and redirect to home",
)
async def logout() -> RedirectResponse:
    """Clears the session cookie. Accepts GET (browser link) and POST (fetch)."""
    response = RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("session")
    return response


@app.get("/api/auth/me", response_model=UserOut, tags=["auth"], summary="Current user info")
async def me(user: User = Depends(get_current_user_from_session)) -> UserOut:
    return UserOut.model_validate(user)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/api/health", tags=["health"], summary="Health check")
async def health() -> dict[str, str]:
    return {"status": "ok"}
