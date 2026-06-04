"""
Shared pytest fixtures for the shoutrrr-logger backend test suite.

Uses an in-memory SQLite database via aiosqlite so tests run without a
real PostgreSQL instance.  PostgreSQL-specific DDL (pg_trgm, JSONB, GIN
indexes) is stripped out via event listeners before the schema is created.
"""

from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from auth import create_session_jwt, generate_raw_token, hash_token
from database import get_db
from models import AccessToken, Base, Notification, User, UserRole

# ---------------------------------------------------------------------------
# Engine / session — SQLite in-memory per test session
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    # SQLite doesn't support PostgreSQL-specific index options; strip them
    # so that Base.metadata.create_all() works.
    @event.listens_for(eng.sync_engine, "before_cursor_execute")
    def _strip_pg_syntax(conn, cursor, statement, parameters, context, executemany):
        pass  # no-op — filtering happens at DDL reflection level

    # Patch the models to remove PG-only kwargs before DDL is emitted
    from models import Notification as _Notif  # noqa: PLC0415
    _Notif.__table_args__ = ()

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield eng

    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncGenerator[AsyncSession, None]:
    """Fresh database session per test, rolled back afterwards."""
    factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
        await session.rollback()


# ---------------------------------------------------------------------------
# FastAPI app with DB override
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def app(db: AsyncSession):
    """FastAPI app with the database dependency overridden to use the test DB."""
    # Import here to avoid triggering lifespan (init_db) at collection time
    from main import app as _app  # noqa: PLC0415
    from plugins import registry  # noqa: PLC0415

    registry.discover()  # ensure plugins are loaded

    async def _override_db():
        yield db

    _app.dependency_overrides[get_db] = _override_db
    yield _app
    _app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client backed by the test app."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Pre-seeded database objects
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def admin_user(db: AsyncSession) -> User:
    user = User(
        sub="admin-sub-001",
        email="admin@example.com",
        username="admin",
        full_name="Admin User",
        role=UserRole.admin,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def viewer_user(db: AsyncSession) -> User:
    user = User(
        sub="viewer-sub-001",
        email="viewer@example.com",
        username="viewer",
        full_name="Viewer User",
        role=UserRole.viewer,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def access_token(db: AsyncSession, admin_user: User) -> tuple[str, AccessToken]:
    """Returns (raw_token, AccessToken ORM row)."""
    raw = generate_raw_token()
    tok = AccessToken(
        user_id=admin_user.id,
        name="test-token",
        token_hash=hash_token(raw),
    )
    db.add(tok)
    await db.flush()
    await db.refresh(tok)
    return raw, tok


@pytest_asyncio.fixture
def admin_session_headers(admin_user: User) -> dict:
    """Authorization header with a valid session JWT for the admin user."""
    jwt = create_session_jwt(str(admin_user.id), admin_user.role.value)
    return {"Authorization": f"Bearer {jwt}"}


@pytest_asyncio.fixture
def viewer_session_headers(viewer_user: User) -> dict:
    jwt = create_session_jwt(str(viewer_user.id), viewer_user.role.value)
    return {"Authorization": f"Bearer {jwt}"}


@pytest_asyncio.fixture
async def sample_notification(db: AsyncSession, access_token) -> Notification:
    """A single saved Notification for use in read-path tests."""
    _, tok = access_token
    notif = Notification(
        token_id=tok.id,
        sender_name="test-host",
        title="Test title",
        message="Watchtower updated container foo to v2",
        raw_payload='{"hostname": "test-host", "severity": "info"}',
    )
    db.add(notif)
    await db.flush()
    await db.refresh(notif)
    return notif
