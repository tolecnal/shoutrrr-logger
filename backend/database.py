import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    echo=False,
    # Disable SSL for connections to a local/private postgres instance.
    # Override DATABASE_URL with ?ssl=require for managed cloud databases.
    connect_args={"ssl": False},
)

async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncSession:  # type: ignore[return]
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db(retries: int = 10, delay: float = 3.0) -> None:
    """
    Create all tables if they do not exist.

    Retries the connection up to *retries* times with *delay* seconds between
    attempts so that the app tolerates postgres still starting up when the
    container comes online.
    """
    import sqlalchemy  # noqa: PLC0415

    from models import Base  # noqa: PLC0415

    for attempt in range(1, retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.execute(sqlalchemy.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
                await conn.run_sync(Base.metadata.create_all)
                # Idempotent column migrations for databases created before this column existed.
                # Existing tokens default to is_global=TRUE (backward-compatible: all old tokens
                # were shared/system tokens, so they behave like global tokens for all users).
                await conn.execute(
                    sqlalchemy.text(
                        "ALTER TABLE IF EXISTS access_tokens "
                        "ADD COLUMN IF NOT EXISTS is_global BOOLEAN NOT NULL DEFAULT TRUE"
                    )
                )
            logger.info("Database initialised successfully.")
            return
        except Exception as exc:
            if attempt == retries:
                logger.error("Database init failed after %d attempts: %s", retries, exc)
                raise
            logger.warning(
                "Database not ready (attempt %d/%d): %s — retrying in %.0fs…",
                attempt,
                retries,
                exc,
                delay,
            )
            await asyncio.sleep(delay)
