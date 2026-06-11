"""
/shoutrrr endpoint – receives incoming notifications from shoutrrr.

Authentication: ``Authorization: Bearer <token>`` header.
When using the shoutrrr generic service, inject the header via the URL:
    generic+https://host/api/shoutrrr?@Authorization=Bearer+YOUR_TOKEN

Body: JSON (application/json) or plain text (text/plain).
Watchtower sends plain text; curl / API clients typically send JSON.
"""

import json
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from auth import verify_bearer_access_token
from database import get_db
from models import AccessToken
from schemas import NotificationOut
from services.notifications import notification_service
from services.rate_limit import rate_limit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/shoutrrr", tags=["shoutrrr"])


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
    await rate_limit_service.enforce(db, token)

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
    _SHOUTRRR_INTERNAL = {
        "disabletls",
        "template",
        "title",
        "splitlines",
        "contenttype",
        "messagelength",
    }
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
    source_ip = request.headers.get(
        "X-Forwarded-For", request.client.host if request.client else None
    )

    # Extract advanced fields from extra
    severity = extra.pop("severity", None) or extra.pop("level", "info")
    tags_raw = extra.pop("tags", "")
    tags = [t.strip() for t in tags_raw.split(",")] if tags_raw else []
    fingerprint_group = extra.pop("group", None)

    notification = await notification_service.store_incoming(
        db,
        token=token,
        sender_name=sender_name,
        title=title,
        message=message,
        raw_payload=raw_payload,
        source_ip=source_ip,
        severity=severity,
        tags=tags,
        fingerprint_group=fingerprint_group,
    )
    out = NotificationOut.model_validate(notification)
    notification_dict = out.model_dump(mode="json")
    notification_dict["token_id"] = str(token.id)
    background_tasks.add_task(
        notification_service.dispatch_plugins,
        notification_dict,
        str(token.user_id) if token.user_id else None,
    )
    return out
