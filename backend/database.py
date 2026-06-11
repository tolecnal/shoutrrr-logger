import asyncio
import logging

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config import settings

logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
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
            try:
                await session.commit()
            except Exception as commit_exc:
                logger.error(f"Failed to commit session: {commit_exc}", exc_info=True)
                raise
        except HTTPException as e:
            # Roll back any uncommitted work either way, but only log 5xx
            # HTTPExceptions as errors. 4xx (401/403/404/422/...) are normal
            # client-facing control flow raised by route handlers or auth
            # dependencies, not failures worth an error-level traceback.
            await session.rollback()
            if e.status_code >= 500:
                logger.error(f"Rolling back session due to error: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"Rolling back session due to error: {e}", exc_info=True)
            await session.rollback()
            raise


# Revision ID of migrations/versions/1ccc65108abc_baseline_schema.py, which
# captures the schema produced by create_all() + the legacy ALTER statements
# below as of when Alembic was introduced. Used to stamp pre-Alembic
# databases so `alembic upgrade head` only applies migrations added after
# this point.
_ALEMBIC_BASELINE_REVISION = "1ccc65108abc"


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
                # NOTE: the ad-hoc "ALTER TABLE IF EXISTS" / "CREATE INDEX IF NOT
                # EXISTS" statements below are legacy, pre-Alembic migrations,
                # kept so older deployments that haven't run `alembic upgrade
                # head` yet still get a schema matching models.py. This block is
                # frozen — do NOT add new entries here. New schema changes go in
                # `backend/migrations/versions/` (see README "Database
                # migrations") and are applied via `alembic upgrade head`.
                #
                # Idempotent column migrations for databases created before this column existed.
                # Existing tokens default to is_global=TRUE (backward-compatible: all old tokens
                # were shared/system tokens, so they behave like global tokens for all users).
                await conn.execute(
                    sqlalchemy.text(
                        "ALTER TABLE IF EXISTS access_tokens "
                        "ADD COLUMN IF NOT EXISTS is_global BOOLEAN NOT NULL DEFAULT TRUE"
                    )
                )
                # Per-token override for the ingestion rate limit (NULL = inherit
                # the global "rate_limit_per_minute" setting).
                await conn.execute(
                    sqlalchemy.text(
                        "ALTER TABLE IF EXISTS access_tokens "
                        "ADD COLUMN IF NOT EXISTS rate_limit_override INTEGER"
                    )
                )
                # Composite index for the rate-limit sliding-window COUNT query.
                await conn.execute(
                    sqlalchemy.text(
                        "CREATE INDEX IF NOT EXISTS ix_notifications_token_received "
                        "ON notifications (token_id, received_at)"
                    )
                )
                # Composite index for the rate-limit sliding-window COUNT query,
                # which filters on last_received_at so deduplicated (repeated)
                # notifications keep counting toward the limit.
                await conn.execute(
                    sqlalchemy.text(
                        "CREATE INDEX IF NOT EXISTS ix_notifications_token_last_received "
                        "ON notifications (token_id, last_received_at)"
                    )
                )
                # users.sub previously had both a UniqueConstraint (uq_users_sub) and a
                # unique index (ix_users_sub) — drop the redundant constraint, keeping
                # the single unique index.
                await conn.execute(
                    sqlalchemy.text(
                        "ALTER TABLE IF EXISTS users DROP CONSTRAINT IF EXISTS uq_users_sub"
                    )
                )
                # token_hash is a deterministic hash, so bearer-token auth can look it
                # up directly instead of scanning every active token.
                await conn.execute(
                    sqlalchemy.text(
                        "CREATE UNIQUE INDEX IF NOT EXISTS ix_access_tokens_token_hash "
                        "ON access_tokens (token_hash)"
                    )
                )
                # Composite index for per-user token listing/limit checks.
                await conn.execute(
                    sqlalchemy.text(
                        "CREATE INDEX IF NOT EXISTS ix_access_tokens_user_global "
                        "ON access_tokens (user_id, is_global)"
                    )
                )
                # Trigram indexes so ILIKE search on title/sender_name (alongside
                # message) can use an index instead of a sequential scan.
                await conn.execute(
                    sqlalchemy.text(
                        "CREATE INDEX IF NOT EXISTS ix_notifications_title_gin "
                        "ON notifications USING gin (title gin_trgm_ops)"
                    )
                )
                await conn.execute(
                    sqlalchemy.text(
                        "CREATE INDEX IF NOT EXISTS ix_notifications_sender_name_gin "
                        "ON notifications USING gin (sender_name gin_trgm_ops)"
                    )
                )
                await conn.execute(
                    sqlalchemy.text(
                        "ALTER TABLE IF EXISTS user_alerts "
                        "ADD COLUMN IF NOT EXISTS email_sent BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )

                # Bring this database under Alembic's management. The schema
                # produced above already matches the baseline migration, so a
                # database seeing Alembic for the first time is stamped at
                # baseline (not "head") — this lets `alembic upgrade head`
                # correctly apply any migrations added after the baseline.
                await conn.execute(
                    sqlalchemy.text(
                        "CREATE TABLE IF NOT EXISTS alembic_version ("
                        "version_num VARCHAR(32) NOT NULL, "
                        "CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)"
                        ")"
                    )
                )
                await conn.execute(
                    sqlalchemy.text(
                        "INSERT INTO alembic_version (version_num) "
                        "SELECT :rev WHERE NOT EXISTS (SELECT 1 FROM alembic_version)"
                    ),
                    {"rev": _ALEMBIC_BASELINE_REVISION},
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
