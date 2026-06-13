import html
import logging
from typing import Any

from plugins.base import BasePlugin
from utils.ssrf import create_ssrf_safe_async_client

logger = logging.getLogger(__name__)


class TelegramPlugin(BasePlugin):
    plugin_id = "telegram"
    name = "Telegram"
    description = "Send notifications to a Telegram chat via Bot API."

    default_config = {
        "bot_token": "",
        "chat_id": "",
        "message_template": "<b>{title}</b>\n\n{message}",
        "included_fields": ["severity", "source_ip"],
    }

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not config.get("bot_token"):
            return False, "bot_token is required"
        if not config.get("chat_id"):
            return False, "chat_id is required"
        return True, ""

    async def on_notification(self, notification: dict[str, Any], config: dict[str, Any]) -> None:
        bot_token = config.get("bot_token", "").strip()
        chat_id = config.get("chat_id", "").strip()

        if not bot_token or not chat_id:
            logger.warning("Telegram plugin enabled but bot_token or chat_id is not configured.")
            return

        template = config.get("message_template") or self.default_config["message_template"]

        # We need to escape HTML in the variables before replacing
        escaped_notification = {}
        for k, v in notification.items():
            if isinstance(v, str):
                escaped_notification[k] = html.escape(v)
            else:
                escaped_notification[k] = html.escape(str(v))

        message_text = template
        for k, v in escaped_notification.items():
            message_text = message_text.replace(f"{{{k}}}", v)

        custom_fields = notification.get("custom_fields", {})
        escaped_custom_fields = {k: html.escape(str(v)) for k, v in custom_fields.items()}
        for k, v in escaped_custom_fields.items():
            message_text = message_text.replace(f"{{custom_fields.{k}}}", v)

        # Append included fields as a pre-formatted block
        included = config.get("included_fields", [])
        if included:
            fields_text = "\n\n<b>Details:</b>\n<pre>"
            has_fields = False
            for field in included:
                val = notification.get(field)
                if val is not None:
                    fields_text += f"{field}: {val}\n"
                    has_fields = True
                elif field.startswith("custom_fields."):
                    cf_key = field.replace("custom_fields.", "")
                    val = custom_fields.get(cf_key)
                    if val is not None:
                        fields_text += f"{field}: {val}\n"
                        has_fields = True
            fields_text += "</pre>"
            if has_fields:
                message_text += fields_text

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message_text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }

        async with create_ssrf_safe_async_client(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()


plugin = TelegramPlugin()
