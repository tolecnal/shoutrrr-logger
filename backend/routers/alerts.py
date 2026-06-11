import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user_from_session
from database import get_db
from models import User
from schemas import (
    AlertRuleCreate,
    AlertRuleOut,
    AlertRuleUpdate,
    AlertTestRequest,
    AlertTestResult,
    UserAlertOut,
)
from services.alerts import alerts_service
from services.settings import settings_service
from services.trigger_engine import send_email_async

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("/rules", response_model=list[AlertRuleOut])
async def list_alert_rules(
    current_user: Annotated[User, Depends(get_current_user_from_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await alerts_service.list_rules(db, current_user.id)


@router.post("/rules", response_model=AlertRuleOut, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    payload: AlertRuleCreate,
    current_user: Annotated[User, Depends(get_current_user_from_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await alerts_service.create_rule(db, current_user.id, payload)


@router.patch("/rules/{rule_id}", response_model=AlertRuleOut)
async def update_alert_rule(
    rule_id: uuid.UUID,
    payload: AlertRuleUpdate,
    current_user: Annotated[User, Depends(get_current_user_from_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    rule = await alerts_service.update_rule(db, current_user.id, rule_id, payload)
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.delete("/rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert_rule(
    rule_id: uuid.UUID,
    current_user: Annotated[User, Depends(get_current_user_from_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    deleted = await alerts_service.delete_rule(db, current_user.id, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return None


@router.post("/test", response_model=AlertTestResult)
async def test_alert_rule(
    payload: AlertTestRequest,
    current_user: Annotated[User, Depends(get_current_user_from_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    matched, total = await alerts_service.test_rule(db, current_user.id, payload)
    return AlertTestResult(matched_notifications=matched, total_matches=total)


@router.post("/test-email", status_code=status.HTTP_204_NO_CONTENT)
async def test_email_alert(
    payload: AlertTestRequest,
    current_user: Annotated[User, Depends(get_current_user_from_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if not payload.send_email:
        raise HTTPException(status_code=400, detail="Send email alert is not enabled on this rule")

    if not current_user.email:
        raise HTTPException(status_code=400, detail="Current user has no email address configured")

    app_settings = await settings_service.get_all(db)
    settings_dict = {s["key"]: s["value"] for s in app_settings}

    if not settings_dict.get("email_alerts_enabled"):
        raise HTTPException(
            status_code=400, detail="Email alerts are disabled globally in settings"
        )

    smtp_host = settings_dict.get("smtp_host")
    smtp_port = settings_dict.get("smtp_port")
    smtp_from = settings_dict.get("smtp_from")

    if not smtp_host or not smtp_port or not smtp_from:
        raise HTTPException(status_code=400, detail="SMTP is not properly configured")

    subject = f"[Test Alert] {payload.name}"
    body = (
        f"This is a test email for your alert rule: '{payload.name}'.\n"
        f"Match Type: {payload.match_type}\n"
        f"Pattern: {payload.match_pattern}\n"
    )

    try:
        await send_email_async(
            host=smtp_host,
            port=int(smtp_port),
            user=settings_dict.get("smtp_user", ""),
            password=settings_dict.get("smtp_password", ""),
            from_addr=smtp_from,
            to_addr=current_user.email,
            subject=subject,
            body=body,
            raise_errors=True,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send email: {e}")
    return None


@router.get("", response_model=list[UserAlertOut])
async def list_user_alerts(
    current_user: Annotated[User, Depends(get_current_user_from_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    is_read: bool | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return await alerts_service.list_alerts(db, current_user.id, is_read, limit, offset)


@router.patch("/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_alerts_read(
    current_user: Annotated[User, Depends(get_current_user_from_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    alert_ids: list[uuid.UUID] = Query(default=[]),
    all: bool = Query(default=False),
):
    await alerts_service.mark_read(db, current_user.id, alert_ids, mark_all=all)
    return None


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alerts(
    current_user: Annotated[User, Depends(get_current_user_from_session)],
    db: Annotated[AsyncSession, Depends(get_db)],
    alert_ids: list[uuid.UUID] = Query(default=[]),
    all: bool = Query(default=False),
):
    await alerts_service.delete_alerts(db, current_user.id, alert_ids, delete_all=all)
    return None
