import asyncio
import logging
import re
import smtplib
from email.message import EmailMessage

from sqlalchemy import select

from database import async_session_factory
from models import AccessToken, AlertRule, Notification, User, UserAlert
from services.settings import settings_service

logger = logging.getLogger(__name__)


async def run_trigger_engine(
    notification_id: str, token_id: str, message_text: str, title_text: str | None
) -> None:
    async with async_session_factory() as db:
        # 1. Fetch Notification and Token info
        notification = await db.get(Notification, notification_id)
        if not notification:
            return
        token = await db.get(AccessToken, token_id)
        if not token:
            return

        combined_texts = []
        if title_text:
            combined_texts.append(title_text)
        if message_text:
            combined_texts.append(message_text)
        combined = " ".join(combined_texts)

        # 2. Query active AlertRules
        stmt = (
            select(AlertRule).join(User, AlertRule.user_id == User.id).where(User.is_active == True)
        )
        result = await db.execute(stmt)
        rules = result.scalars().all()

        alerts_to_create = []
        users_to_email = {}

        for rule in rules:
            if token.is_global:
                if rule.notification_scope == "personal_only":
                    continue
            else:
                if rule.notification_scope == "global_only":
                    continue
                if rule.user_id != token.user_id:
                    continue

            texts_to_search = []
            if rule.match_target in ("title", "all") and title_text:
                texts_to_search.append(title_text)
            if rule.match_target in ("message", "all") and message_text:
                texts_to_search.append(message_text)

            target_str = " ".join(texts_to_search)

            is_match = False
            if rule.match_type == "exact":
                is_match = rule.match_pattern == target_str
            elif rule.match_type == "contains":
                is_match = rule.match_pattern.lower() in target_str.lower()
            elif rule.match_type == "regex":
                try:
                    pattern = re.compile(rule.match_pattern, re.IGNORECASE)
                    is_match = bool(pattern.search(target_str))
                except re.error:
                    is_match = False

            if is_match:
                alerts_to_create.append(
                    UserAlert(
                        user_id=rule.user_id,
                        notification_id=notification.id,
                        rule_id=rule.id,
                    )
                )
                if rule.send_email:
                    users_to_email.setdefault(rule.user_id, set()).add(rule.name)

        if alerts_to_create:
            db.add_all(alerts_to_create)
            await db.commit()

            email_enabled = await settings_service.get_int(db, "email_alerts_enabled")
            if email_enabled:
                users_query = await db.execute(
                    select(User).where(User.id.in_(list(users_to_email.keys())))
                )
                matched_users = users_query.scalars().all()

                smtp_host = await settings_service.get_string(db, "smtp_host")
                smtp_port = await settings_service.get_int(db, "smtp_port", default=587)
                smtp_user = await settings_service.get_string(db, "smtp_user")
                smtp_password = await settings_service.get_string(db, "smtp_password")
                smtp_from = await settings_service.get_string(
                    db, "smtp_from", default="alerts@shoutrrr-logger.local"
                )

                if smtp_host:
                    for user in matched_users:
                        rule_names = ", ".join(users_to_email[user.id])
                        subject = f"[Alert] Notification matched rules: {rule_names}"
                        body = f"Hello {user.username},\n\nThe following notification matched your alert rules ({rule_names}):\n\n"
                        if title_text:
                            body += f"Title: {title_text}\n"
                        body += f"Message: {message_text}\n\nView details in Shoutrrr Logger."

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
                            )
                        )


async def send_email_async(
    host: str,
    port: int,
    user: str,
    password: str,
    from_addr: str,
    to_addr: str,
    subject: str,
    body: str,
    raise_errors: bool = False,
):
    def _send():
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = to_addr

        try:
            with smtplib.SMTP(host, port, timeout=10) as server:
                if port == 587 or port == 25:
                    try:
                        server.starttls()
                    except smtplib.SMTPException:
                        pass
                if user and password:
                    server.login(user, password)
                server.send_message(msg)
            logger.info(f"Email sent successfully to {to_addr}")
        except Exception as e:
            logger.error(f"Failed to send email to {to_addr}: {e}")
            if raise_errors:
                raise

    if port == 465:

        def _send_ssl():
            msg = EmailMessage()
            msg.set_content(body)
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to_addr
            try:
                with smtplib.SMTP_SSL(host, port, timeout=10) as server:
                    if user and password:
                        server.login(user, password)
                    server.send_message(msg)
                logger.info(f"Email sent successfully to {to_addr}")
            except Exception as e:
                logger.error(f"Failed to send email to {to_addr}: {e}")
                if raise_errors:
                    raise

        await asyncio.to_thread(_send_ssl)
    else:
        await asyncio.to_thread(_send)
