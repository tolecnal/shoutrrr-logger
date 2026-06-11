import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from models import (
    AccessToken,
    AlertRule,
    MonitoringToken,
    Notification,
    PluginConfig,
    User,
    UserAlert,
)

router = APIRouter()


async def verify_monitoring_token(request: Request, db: AsyncSession = Depends(get_db)):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    raw_token = auth_header.replace("Bearer ", "", 1).strip()
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    stmt = select(MonitoringToken).where(
        MonitoringToken.token_hash == token_hash,
        MonitoringToken.is_active == True,
    )
    result = await db.execute(stmt)
    token = result.scalar_one_or_none()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or inactive monitoring token",
        )

    # Update last_used_at
    token.last_used_at = datetime.now(UTC)
    await db.commit()
    return token


@router.get("/health", summary="Health check and system stats for external monitoring")
async def monitoring_health(
    request: Request,
    token: MonitoringToken = Depends(verify_monitoring_token),
    db: AsyncSession = Depends(get_db),
):
    # Determine DB connectivity (we reached here, so DB is somewhat connected, but let's do a simple query)
    try:
        await db.execute(select(1))
        db_connected = True
    except Exception:
        db_connected = False

    stats = {
        "db_connected": db_connected,
    }

    if db_connected:
        total_notifications = await db.scalar(select(func.count(Notification.id)))
        total_users = await db.scalar(select(func.count(User.id)))
        active_users = await db.scalar(select(func.count(User.id)).where(User.is_active))
        unread_alerts = await db.scalar(
            select(func.count(UserAlert.id)).where(not UserAlert.is_read)
        )

        email_alerts_pending = await db.scalar(
            select(func.count(UserAlert.id))
            .join(AlertRule, UserAlert.rule_id == AlertRule.id)
            .where(
                not UserAlert.email_sent,
                AlertRule.send_email,
            )
        )

        active_plugins = await db.scalar(
            select(func.count(PluginConfig.id)).where(PluginConfig.enabled)
        )
        active_ingest_tokens = await db.scalar(
            select(func.count(AccessToken.id)).where(AccessToken.is_active)
        )

        stats["notifications_total"] = total_notifications or 0
        stats["users_total"] = total_users or 0
        stats["users_active"] = active_users or 0
        stats["alerts_unread"] = unread_alerts or 0
        stats["alerts_email_pending"] = email_alerts_pending or 0
        stats["plugins_active"] = active_plugins or 0
        stats["ingest_tokens_active"] = active_ingest_tokens or 0

    return stats
