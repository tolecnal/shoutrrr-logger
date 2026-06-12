"""
shoutrrr-logger – FastAPI entry point.

Run locally:   uvicorn main:app --reload
Production:    gunicorn main:app -k uvicorn.workers.UvicornWorker -w 4
"""

import asyncio
import logging
import re
import secrets
import urllib.parse
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager, suppress

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession, async_sessionmaker

from auth import (
    create_session_jwt,
    exchange_code_for_tokens,
    get_current_user_from_session,
    get_oidc_config,
    get_userinfo,
    verify_oidc_jwt,
)
from config import settings
from database import get_db, init_db
from middleware.performance import PerformanceMiddleware
from models import User, UserRole
from plugins import registry as plugin_registry
from routers import (
    admin_monitoring_tokens,
    alerts,
    api_metrics,
    audit_logs,
    me,
    monitoring,
    notifications,
    plugins,
    routing_rules,
    shoutrrr,
    tokens,
    user_plugins,
    users,
)
from routers import (
    settings as settings_router,
)
from schemas import OIDCCallbackResponse, UserOut
from services.api_metrics import api_metric_service
from services.audit_logs import audit_log_service
from services.notifications import notification_service
from services.settings import settings_service
from services.users import user_service
from version import API_VERSION, APP_VERSION, BUILD_GIT_HASH, BUILD_TIME

logger = logging.getLogger(__name__)


# Arbitrary fixed key for the cross-worker "retention loop owner" advisory
# lock (see _acquire_retention_leadership below).
_RETENTION_LOCK_KEY = 0x73685F7274  # "sh_rt" packed into an int, just needs to be stable


async def _acquire_retention_leadership(engine: AsyncEngine) -> tuple[bool, AsyncConnection | None]:
    """Try to become the single process responsible for the hourly retention loop.

    With multiple gunicorn workers, every worker runs its own copy of the
    FastAPI app (and thus its own ``lifespan``). Without coordination, each
    worker would start its own ``_retention_loop``, all purging the same
    rows on overlapping schedules. A PostgreSQL session-level advisory lock
    lets exactly one worker "win": the returned connection (if any) must be
    kept open for the app's lifetime and closed on shutdown to release the
    lock — if that worker dies, the lock is released automatically and
    another worker can take over on its next restart.

    On non-PostgreSQL backends (SQLite in tests/dev) there is only ever one
    process, so this always succeeds with no connection to manage.

    Returns ``(is_leader, lock_connection)``.
    """
    if engine.dialect.name != "postgresql":
        return True, None
    conn = await engine.connect()
    result = await conn.execute(
        text("SELECT pg_try_advisory_lock(:key)"), {"key": _RETENTION_LOCK_KEY}
    )
    if result.scalar_one():
        return True, conn
    await conn.close()
    return False, None


async def _retention_loop() -> None:
    """Background task: purge old notifications, API metric logs, and audit logs
    once per hour using their respective DB retention settings."""
    from database import engine  # noqa: PLC0415

    while True:
        await asyncio.sleep(3600)
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                retention_days = await settings_service.get_int(session, "retention_days")
                if retention_days > 0:
                    count = await notification_service.purge_old(
                        session, retention_days=retention_days
                    )
                    if count:
                        await session.commit()
                        logger.info(
                            "Retention: purged %d notification(s) older than %d day(s)",
                            count,
                            retention_days,
                        )

                metrics_retention_days = await settings_service.get_int(
                    session, "api_metrics_retention_days"
                )
                if metrics_retention_days > 0:
                    count = await api_metric_service.purge_old(
                        session, retention_days=metrics_retention_days
                    )
                    if count:
                        await session.commit()
                        logger.info(
                            "Retention: purged %d API metric log(s) older than %d day(s)",
                            count,
                            metrics_retention_days,
                        )

                audit_retention_days = await settings_service.get_int(
                    session, "audit_log_retention_days"
                )
                if audit_retention_days > 0:
                    count = await audit_log_service.purge_old(
                        session, retention_days=audit_retention_days
                    )
                    if count:
                        await session.commit()
                        logger.info(
                            "Retention: purged %d audit log entry(ies) older than %d day(s)",
                            count,
                            audit_retention_days,
                        )
        except Exception:
            logger.exception("Retention loop encountered an error")


async def _email_loop() -> None:
    """Background task: periodically process and send pending alert email digests."""
    from services.email_digest import process_email_digests  # noqa: PLC0415

    while True:
        await asyncio.sleep(60)  # Run every 60 seconds
        try:
            await process_email_digests()
        except Exception:
            logger.exception("Email loop encountered an error")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    from database import engine  # noqa: PLC0415
    from services.sse import sse_service

    await init_db()
    plugin_registry.discover()
    await sse_service.start()

    is_retention_leader, retention_lock_conn = await _acquire_retention_leadership(engine)
    retention_task: asyncio.Task | None = None
    email_task: asyncio.Task | None = None
    if is_retention_leader:
        retention_task = asyncio.create_task(_retention_loop())
        email_task = asyncio.create_task(_email_loop())
        logger.info("Background loops (retention, email digest) started on this worker")
    else:
        logger.info("Background loops already owned by another worker; skipping on this worker")

    yield

    if retention_task is not None:
        retention_task.cancel()
        with suppress(asyncio.CancelledError):
            await retention_task
    if email_task is not None:
        email_task.cancel()
        with suppress(asyncio.CancelledError):
            await email_task
    if retention_lock_conn is not None:
        await retention_lock_conn.close()

    await sse_service.stop()


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
# Backward-compatibility redirect middleware
#
# Requests to the old unversioned /api/<path> are permanently redirected to
# /api/v1/<path> with a 308 (Permanent Redirect, preserves method + body).
# This keeps existing shoutrrr webhook URLs working after the versioning change.
# Excluded paths are those that will never be versioned.
# ---------------------------------------------------------------------------
_UNVERSIONED_PREFIXES = {
    "/api/docs",
    "/api/redoc",
    "/api/openapi.json",
    "/api/health",
    "/api/version",
    "/api/auth",
}

from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.responses import Response as StarletteResponse  # noqa: E402


class _VersionRedirectMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        path = request.url.path
        if path.startswith("/api/") and not path.startswith(f"/api/{API_VERSION}/"):
            # Skip permanently-unversioned paths
            if not any(path.startswith(p) for p in _UNVERSIONED_PREFIXES):
                new_path = f"/api/{API_VERSION}" + path[len("/api") :]
                qs = f"?{request.url.query}" if request.url.query else ""
                return StarletteResponse(
                    status_code=308,
                    headers={"Location": new_path + qs},
                )
        return await call_next(request)


app.add_middleware(_VersionRedirectMiddleware)
app.add_middleware(PerformanceMiddleware)

# ---------------------------------------------------------------------------
# Routers  (all versioned under /api/v1)
# ---------------------------------------------------------------------------
_V1 = f"/api/{API_VERSION}"
app.include_router(shoutrrr.router, prefix=_V1)
app.include_router(notifications.router, prefix=_V1)
app.include_router(users.router, prefix=f"{_V1}/admin")
app.include_router(tokens.router, prefix=f"{_V1}/admin")
app.include_router(audit_logs.router, prefix=f"{_V1}/admin")
app.include_router(plugins.router, prefix=_V1)
app.include_router(routing_rules.router, prefix=_V1)
app.include_router(user_plugins.router, prefix=_V1)
app.include_router(settings_router.public_router, prefix=_V1)
app.include_router(settings_router.admin_router, prefix=_V1)
app.include_router(me.router, prefix=_V1)
app.include_router(api_metrics.router, prefix=_V1)
app.include_router(alerts.router, prefix=_V1)

app.include_router(monitoring.router, prefix=f"{_V1}/monitoring")
app.include_router(admin_monitoring_tokens.router, prefix=f"{_V1}/admin/monitoring-tokens")


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
# A safe same-origin redirect target: starts with a single "/" (not "//" or
# "/\\", which browsers may normalise to "//..." -> a protocol-relative
# URL), followed only by characters that aren't ASCII control characters.
# Control characters (tab, CR, LF, ...) are excluded because the WHATWG URL
# spec strips them during parsing, so a value such as "/\\t/evil.com" would
# otherwise be interpreted by the browser as "//evil.com".
_SAFE_REDIRECT_PATH_RE = re.compile(r"/(?![/\\])[^\x00-\x1f\x7f]*")

# Short-lived cookie used to carry the post-login redirect target across the
# OIDC round trip to the identity provider. The OIDC `state` param is left as
# an opaque CSRF nonce, decoupling it from user-controlled redirect input.
_REDIRECT_COOKIE_NAME = "oidc_redirect"
_REDIRECT_COOKIE_MAX_AGE = 600  # 10 minutes — generous for an OIDC login round trip


@app.get("/api/auth/login", summary="Initiate OIDC login", tags=["auth"])
async def oidc_login(redirect_after: str = "/log") -> RedirectResponse:
    """Redirects the browser to the OIDC provider's authorization endpoint."""
    if not _SAFE_REDIRECT_PATH_RE.fullmatch(redirect_after):
        redirect_after = "/log"
    config = await get_oidc_config()
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": settings.oidc_client_id,
            "redirect_uri": f"{settings.app_base_url}/api/auth/callback",
            "scope": settings.oidc_scopes,
            "state": secrets.token_urlsafe(24),
        }
    )
    response = RedirectResponse(url=f"{config['authorization_endpoint']}?{params}")
    response.set_cookie(
        key=_REDIRECT_COOKIE_NAME,
        value=redirect_after,
        httponly=True,
        samesite="lax",
        secure=settings.app_base_url.startswith("https"),
        max_age=_REDIRECT_COOKIE_MAX_AGE,
    )
    return response


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
        + (
            f"found list {val1_roles}"
            if val1_found
            else f"not found (got {type(val).__name__}: {val!r})"
        )
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
            + (
                f"found list {val2_roles}"
                if val2_found
                else f"not found (got {type(val2).__name__}: {val2!r})"
            )
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
    request: Request,
    code: str,
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

    # Decode the access token payload, verifying its signature, issuer, and
    # expiration against the provider's JWKS. We only need the role claims
    # which Keycloak puts in the token body but does NOT expose on the
    # UserInfo endpoint unless a protocol mapper is configured. Merging gives
    # _extract_role_from_claims the full picture.
    try:
        token_claims: dict = await verify_oidc_jwt(access_token)
    except Exception as exc:
        logger.warning(f"OIDC access token verification failed: {exc}")
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

    # Auto-provisions the user on first login, or syncs profile/role from SSO.
    user = await user_service.upsert_from_oidc(
        db, sub=sub, email=email, username=username, full_name=full_name, role=role
    )

    session_token = create_session_jwt(str(user.id), user.role.value)

    # Redirect to frontend with session cookie set
    redirect_after = request.cookies.get(_REDIRECT_COOKIE_NAME, "/log")
    if not _SAFE_REDIRECT_PATH_RE.fullmatch(redirect_after):
        redirect_after = "/log"
    response = RedirectResponse(url=redirect_after, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(_REDIRECT_COOKIE_NAME)
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


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
@app.get("/api/version", tags=["meta"], summary="Application version info")
async def version_info() -> dict[str, str]:
    return {
        "version": APP_VERSION,
        "api_version": API_VERSION,
        "git_hash": BUILD_GIT_HASH,
        "build_time": BUILD_TIME,
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
@app.get("/metrics", tags=["metrics"], summary="Prometheus metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
