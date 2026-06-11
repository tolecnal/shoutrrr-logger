import uuid
from typing import Annotated

import markdown
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user_from_session, require_admin
from database import get_db
from models import User, UserRole
from repositories.notifications import notification_repository
from schemas import (
    AlertRuleCreate,
    AlertRuleOut,
    AlertRuleUpdate,
    AlertTestRequest,
    AlertTestResult,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    UserAlertOut,
)
from services.alerts import alerts_service
from services.settings import settings_service
from services.trigger_engine import send_email_async
from utils.sanitize import sanitize_html
from utils.templates import safe_format

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

    rule_name = payload.name.replace("\r", "").replace("\n", "")
    subject = f"[Test Alert] {rule_name}"

    html_body = None
    if payload.notification_id:
        n = await notification_repository.get_visible_by_id(
            db,
            payload.notification_id,
            user_id=current_user.id,
            is_admin=(current_user.role == UserRole.admin),
        )
        if n:
            template_str = settings_dict.get(
                "email_alert_template",
                "Hello {username},\n\nThe following notification matched your alert rules ({rule_names}):\n\n**{title}**\n\n{message}\n\n[View details in Shoutrrr Logger]({base_url})",
            )
            from config import settings

            app_base_url = settings.app_base_url

            try:
                body = safe_format(
                    template_str,
                    username=current_user.username,
                    rule_names=payload.name,
                    title=n.title or "No title",
                    message=n.message,
                    base_url=app_base_url,
                )
            except Exception:
                body = f"Hello {current_user.username},\n\nThe following notification matched your alert rules ({payload.name}):\n\nTitle: {n.title or 'No title'}\nMessage: {n.message}\n\nView details in Shoutrrr Logger: {app_base_url}"

            html_body = sanitize_html(markdown.markdown(body))
        else:
            body = (
                f"This is a generic test email for your alert rule: '{payload.name}'.\n"
                f"Match Type: {payload.match_type}\n"
                f"Pattern: {payload.match_pattern}\n"
            )
    else:
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
            html_body=html_body,
            raise_errors=True,
        )
    except Exception as e:
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    return {"detail": "Test email queued for sending via SMTP"}


@router.post("/preview-template", response_model=TemplatePreviewResponse)
async def preview_template(
    payload: TemplatePreviewRequest,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    from config import settings

    app_base_url = settings.app_base_url

    mock_title = "Critical System Failure"
    mock_message = "The database cluster has lost quorum and is currently read-only. Please investigate immediately."
    mock_rule_names = "Database Alerts"

    if payload.notification_id:
        n = await notification_repository.get_visible_by_id(
            db, payload.notification_id, user_id=current_user.id, is_admin=True
        )
        if n:
            mock_title = n.title or mock_title
            mock_message = n.message or mock_message

    try:
        body = safe_format(
            payload.template,
            username=current_user.username,
            rule_names=mock_rule_names,
            title=mock_title,
            message=mock_message,
            base_url=app_base_url,
        )
    except Exception:
        body = f"Hello {current_user.username},\n\nThe following notification matched your alert rules ({mock_rule_names}):\n\nTitle: {mock_title}\nMessage: {mock_message}\n\nView details in Shoutrrr Logger: {app_base_url}"

    html_body = sanitize_html(markdown.markdown(body))

    return TemplatePreviewResponse(html=html_body)


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
