import asyncio
import logging
from collections import defaultdict

import markdown
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import database
from config import settings
from models import AlertRule, User, UserAlert
from services.settings import settings_service
from services.trigger_engine import send_email_async
from utils.sanitize import sanitize_html

logger = logging.getLogger(__name__)


async def process_email_digests() -> None:
    async with database.async_session_factory() as db:
        email_enabled = await settings_service.get_int(db, "email_alerts_enabled")
        if not email_enabled:
            return

        smtp_host = await settings_service.get_string(db, "smtp_host")
        if not smtp_host:
            return

        # Fetch unsent alerts joined with Rule, Notification, User
        stmt = (
            select(UserAlert)
            .join(AlertRule)
            .join(User)
            .options(
                selectinload(UserAlert.rule),
                selectinload(UserAlert.notification),
                selectinload(UserAlert.user),
            )
            .where(
                UserAlert.email_sent == False,
                AlertRule.send_email == True,
                User.is_active == True,
            )
        )
        result = await db.execute(stmt)
        alerts = result.scalars().all()

        if not alerts:
            return

        # Mark them as sent immediately to avoid double sending
        for alert in alerts:
            alert.email_sent = True
        await db.commit()

        # Group by user
        user_alerts = defaultdict(list)
        for alert in alerts:
            user_alerts[alert.user].append(alert)

        smtp_port = await settings_service.get_int(db, "smtp_port", default=587)
        smtp_user = await settings_service.get_string(db, "smtp_user")
        smtp_password = await settings_service.get_string(db, "smtp_password")
        smtp_from = await settings_service.get_string(
            db, "smtp_from", default="alerts@shoutrrr-logger.local"
        )

        # We use a digest template or fallback to individual alerts
        app_base_url = settings.app_base_url

        for user, u_alerts in user_alerts.items():
            if len(u_alerts) == 1:
                # Single alert format
                alert = u_alerts[0]
                rule_name = alert.rule.name
                title_text = alert.notification.title or "No title"
                message_text = alert.notification.message

                subject = f"[Alert] Notification matched rule: {rule_name}"
                body = (
                    f"Hello {user.username},\n\n"
                    f"The following notification matched your alert rule ({rule_name}):\n\n"
                    f"**{title_text}**\n\n{message_text}\n\n"
                    f"[View details in Shoutrrr Logger]({app_base_url})"
                )
            else:
                # Digest format
                subject = f"[Alert] {len(u_alerts)} notifications matched your rules"

                body_lines = [
                    f"Hello {user.username},\n\nWe have {len(u_alerts)} new alerts for you:\n"
                ]
                for a in u_alerts:
                    title = a.notification.title or "No title"
                    body_lines.append(f"- **{title}** (matched rule: {a.rule.name})")

                body_lines.append(
                    f"\n[View all alerts in Shoutrrr Logger]({app_base_url}/log?view=alerts)"
                )
                body = "\n".join(body_lines)

            html_body = sanitize_html(markdown.markdown(body))

            asyncio.create_task(
                send_email_async(
                    host=smtp_host,
                    port=smtp_port,
                    user=smtp_user,
                    password=smtp_password,
                    from_addr=smtp_from,
                    to_addr=user.email,
                    subject=subject,
                    body=body,
                    html_body=html_body,
                )
            )
