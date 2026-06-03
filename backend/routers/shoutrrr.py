"""
/shoutrrr endpoint – receives incoming notifications from shoutrrr.

Authentication: ``Authorization: Bearer <token>`` header.
When using the shoutrrr generic service, inject the header via the URL:
    generic+https://host/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN

Body: JSON (application/json) or plain text (text/plain).
Watchtower sends plain text; curl / API clients typically send JSON.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import verify_bearer_access_token
from database import get_db
from models import AccessToken, Notification, PluginConfig
from plugins import registry as plugin_registry
from schemas import NotificationOut

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shoutrrr", tags=["shoutrrr"])


async def _dispatch_plugins(notification_dict: dict, db_url: str) -> None:
    """
    Run all enabled plugins against the saved notification.
    Each plugin gets its own try/except so one failure doesn't block others.
    Runs as a FastAPI BackgroundTask — DB session obtained fresh here.
    """
    from database import engine  # noqa: PLC0415
    from sqlalchemy.ext.asyncio import async_sessionmaker  # noqa: PLC0415

    async_session = async_sessionmaker(engine, expire_on_commit=False)
    async with async_session() as db:
        result = await db.execute(select(PluginConfig).where(PluginConfig.enabled == True))  # noqa: E712
        rows: list[PluginConfig] = list(result.scalars().all())

    plugin_configs = {row.id: row for row in rows}

    for plugin in plugin_registry.all_plugins():
        row = plugin_configs.get(plugin.plugin_id)
        if not row or not row.enabled:
            continue
        merged_config = {**plugin.default_config, **row.config}
        try:
            await plugin.on_notification(notification_dict, merged_config)
        except Exception as exc:
            logger.error(
                "[plugin:%s] on_notification raised: %s",
                plugin.plugin_id,
                exc,
                exc_info=True,
            )


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=NotificationOut,
    summary="Receive a shoutrrr notification",
    description=(
        "Accepts a notification from shoutrrr. Supports JSON and plain-text bodies. "
        "Requires a valid Bearer or Basic (empty username) access token."
    ),
)
async def receive_notification(
    request: Request,
    background_tasks: BackgroundTasks,
    token: AccessToken = Depends(verify_bearer_access_token),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    content_type = request.headers.get("content-type", "")
    raw_body = await request.body()

    title: str | None = None
    message: str = ""
    extra: dict = {}

    # ---------------------------------------------------------------------------
    # Custom fields from query parameters
    #
    # shoutrrr generic service passes custom fields as URL query parameters
    # with a "$" prefix, e.g. ?$hostname=vm-runner01&$severity=info
    # We also collect any non-shoutrrr-internal params (those that don't start
    # with "@", which are shoutrrr options like @Authorization, disabletls etc.)
    # Internal shoutrrr params to skip (not custom fields):
    _SHOUTRRR_INTERNAL = {"disabletls", "template", "title", "splitlines",
                          "contenttype", "messagelength"}
    for key, value in request.query_params.items():
        if key.startswith("@"):
            # shoutrrr header injection — skip
            continue
        if key.startswith("$"):
            # Custom field — strip the $ prefix for storage
            extra[key[1:]] = value
        elif key not in _SHOUTRRR_INTERNAL:
            # Unknown query param — store as-is
            extra[key] = value
    # ---------------------------------------------------------------------------

    if "application/json" in content_type:
        try:
            data = json.loads(raw_body)
        except json.JSONDecodeError:
            data = {}
        message = str(data.pop("message", raw_body.decode(errors="replace")))
        title = data.pop("title", None) or title
        # Body extra fields take precedence over query param fields
        extra = {**extra, **data}
    else:
        # Plain text — Watchtower generic service sends the report as raw text
        message = raw_body.decode(errors="replace").strip()

    if not message:
        return JSONResponse(status_code=400, content={"detail": "Empty message body"})

    # Resolve sender name from the token's linked user
    await db.refresh(token, attribute_names=["user"])
    sender_name = token.name if token.name else (token.user.username if token.user else None)

    raw_payload = json.dumps(extra) if extra else None
    source_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)

    notification = Notification(
        token_id=token.id,
        sender_name=sender_name,
        title=title,
        message=message,
        raw_payload=raw_payload,
        source_ip=source_ip,
    )
    db.add(notification)
    await db.flush()
    await db.refresh(notification)
    out = NotificationOut.model_validate(notification)
    # Dispatch enabled plugins as a background task (non-blocking)
    from config import settings as _settings  # noqa: PLC0415
    background_tasks.add_task(_dispatch_plugins, out.model_dump(mode="json"), _settings.database_url)
    return out
