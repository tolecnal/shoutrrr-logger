import logging
from typing import Any

from plugins.base import BasePlugin
from utils.ssrf import create_ssrf_safe_async_client

logger = logging.getLogger(__name__)


class PushoverPlugin(BasePlugin):
    plugin_id = "pushover"
    name = "Pushover"
    description = "Send push notifications using Pushover."

    default_config = {
        "user_key": "",
        "api_token": "",
        "message_template": "{message}",
        "title_template": "{title}",
        "priority": "0",
        "sound": "pushover",
        "device": "",
    }

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        user_key = config.get("user_key", "").strip()
        api_token = config.get("api_token", "").strip()

        if not user_key:
            return False, "user_key is required"
        if not api_token:
            return False, "api_token is required"

        return True, ""

    async def on_notification(self, notification: dict[str, Any], config: dict[str, Any]) -> None:
        user_key = config.get("user_key", "").strip()
        api_token = config.get("api_token", "").strip()

        if not user_key or not api_token:
            logger.warning("Pushover plugin enabled but user_key or api_token is not configured.")
            return

        # Format message
        msg_template = config.get("message_template") or self.default_config["message_template"]
        message_text = msg_template
        for k, v in notification.items():
            message_text = message_text.replace(f"{{{k}}}", str(v))

        # Format title
        title_template = config.get("title_template") or self.default_config["title_template"]
        title_text = title_template
        for k, v in notification.items():
            title_text = title_text.replace(f"{{{k}}}", str(v))

        custom_fields = notification.get("custom_fields", {})
        for k, v in custom_fields.items():
            message_text = message_text.replace(f"{{custom_fields.{k}}}", str(v))
            title_text = title_text.replace(f"{{custom_fields.{k}}}", str(v))

        payload: dict[str, Any] = {
            "token": api_token,
            "user": user_key,
            "message": message_text,
            "title": title_text,
        }

        priority = config.get("priority", "0")
        if priority:
            payload["priority"] = priority

        sound = config.get("sound", "").strip()
        if sound:
            payload["sound"] = sound

        device = config.get("device", "").strip()
        if device:
            payload["device"] = device

        url = "https://api.pushover.net/1/messages.json"

        async with create_ssrf_safe_async_client(timeout=10.0) as client:
            resp = await client.post(url, data=payload)
            resp.raise_for_status()


plugin = PushoverPlugin()
