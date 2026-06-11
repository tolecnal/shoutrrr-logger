import asyncio
import logging
import re
import smtplib
import uuid
from email.message import EmailMessage

from sqlalchemy import select

import database
from models import AccessToken, AlertRule, Notification, User, UserAlert

logger = logging.getLogger(__name__)


async def run_trigger_engine(
    notification_id: str, token_id: str, message_text: str, title_text: str | None
) -> None:
    async with database.async_session_factory() as db:
        try:
            n_uuid = uuid.UUID(notification_id)
            t_uuid = uuid.UUID(token_id)
        except ValueError:
            return

        # 1. Fetch Notification and Token info
        notification = await db.get(Notification, n_uuid)
        if not notification:
            return
        token = await db.get(AccessToken, t_uuid)
        if not token:
            return

        combined_texts = []
        if title_text:
            combined_texts.append(title_text)
        if message_text:
            combined_texts.append(message_text)

        # 2. Query active AlertRules
        stmt = select(AlertRule).join(User, AlertRule.user_id == User.id).where(User.is_active)
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

            # Emails are now sent periodically via a background worker (email_digest.py)
            pass


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
    html_body: str | None = None,
):
    def _send():
        msg = EmailMessage()
        msg.set_content(body)
        if html_body:
            msg.add_alternative(html_body, subtype="html")
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
            if html_body:
                msg.add_alternative(html_body, subtype="html")
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
