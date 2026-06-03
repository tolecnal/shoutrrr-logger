"""
/shoutrrr endpoint – receives incoming notifications from shoutrrr.

Authentication: opaque Bearer token (access token from DB).
"""

import json

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import verify_bearer_access_token
from database import get_db
from models import AccessToken, Notification
from schemas import NotificationOut, ShoutrrrPayload

router = APIRouter(prefix="/shoutrrr", tags=["shoutrrr"])


@router.post(
    "",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=NotificationOut,
    summary="Receive a shoutrrr notification",
    description=(
        "Accepts a notification payload from the shoutrrr service. "
        "Requires a valid Bearer access token in the Authorization header."
    ),
)
async def receive_notification(
    payload: ShoutrrrPayload,
    request: Request,
    token: AccessToken = Depends(verify_bearer_access_token),
    db: AsyncSession = Depends(get_db),
) -> NotificationOut:
    # Resolve sender name from the token's linked user
    await db.refresh(token, attribute_names=["user"])
    sender_name = token.name if token.name else (token.user.username if token.user else None)

    # Capture any extra fields as raw payload
    extra = payload.model_dump(exclude={"message", "title"}, exclude_none=True)
    raw = json.dumps(extra) if extra else None

    source_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)

    notification = Notification(
        token_id=token.id,
        sender_name=sender_name,
        title=payload.title,
        message=payload.message,
        raw_payload=raw,
        source_ip=source_ip,
    )
    db.add(notification)
    await db.flush()
    await db.refresh(notification)
    return NotificationOut.model_validate(notification)
