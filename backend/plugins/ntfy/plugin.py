import logging
from typing import Any

from plugins.base import BasePlugin
from utils.ssrf import create_ssrf_safe_async_client, validate_url_for_ssrf

logger = logging.getLogger(__name__)


class NtfyPlugin(BasePlugin):
    plugin_id = "ntfy"
    name = "ntfy"
    description = "Send push notifications using ntfy.sh or a self-hosted instance."

    default_config = {
        "server_url": "https://ntfy.sh",
        "topic": "",
        "priority": "default",
        "tags": "",
        "message_template": "{title}\n{message}",
        "access_token": "",
    }

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        server_url = config.get("server_url", "").strip()
        topic = config.get("topic", "").strip()

        if not server_url:
            return False, "server_url is required"
        if not topic:
            return False, "topic is required"

        try:
            validate_url_for_ssrf(server_url)
        except ValueError as e:
            return False, f"Invalid Server URL (SSRF Policy): {str(e)}"

        return True, ""

    async def on_notification(self, notification: dict[str, Any], config: dict[str, Any]) -> None:
        server_url = config.get("server_url", "https://ntfy.sh").strip()
        topic = config.get("topic", "").strip()

        if not server_url or not topic:
            logger.warning("ntfy plugin enabled but server_url or topic is not configured.")
            return

        try:
            validate_url_for_ssrf(server_url)
        except ValueError as e:
            msg = f"Security error: ntfy server URL blocked by SSRF policy: {e}"
            self.log(msg, "error")
            raise RuntimeError(msg)

        # Format message
        template = config.get("message_template") or self.default_config["message_template"]
        message_text = template
        for k, v in notification.items():
            message_text = message_text.replace(f"{{{k}}}", str(v))

        custom_fields = notification.get("custom_fields", {})
        for k, v in custom_fields.items():
            message_text = message_text.replace(f"{{custom_fields.{k}}}", str(v))

        headers = {}

        # Optional Access Token
        access_token = config.get("access_token", "").strip()
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"

        # Tags
        tags = config.get("tags", "").strip()
        if tags:
            headers["Tags"] = tags

        # Priority mapping
        # ntfy supports numbers 1-5 or strings max, high, default, low, min
        priority_map = {
            "min": "1",
            "low": "2",
            "default": "3",
            "high": "4",
            "max": "5",
        }
        priority_str = config.get("priority", "default").lower()
        priority_val = priority_map.get(priority_str, "3")
        headers["Priority"] = priority_val

        # Title
        # ntfy supports title in header
        # We also put it in the message body via template but we can set the header too.
        if "title" in notification:
            # Only use ascii for headers safely, or let httpx handle utf-8
            # ntfy supports Title header
            # httpx handles unicode headers if encoded, ntfy prefers utf-8 encoded headers via RFC 2047
            # or we can just send it as json payload instead of text payload to avoid header encoding issues.
            # Actually, ntfy supports JSON payload! It is safer for unicode.
            pass

        # Since we use message_text which already includes the title if the user wants it,
        # we will use the JSON payload method to safely transmit unicode titles and messages.

        payload = {
            "topic": topic,
            "message": message_text,
            "title": notification.get("title", ""),
            "priority": int(priority_val),
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
        }

        async with create_ssrf_safe_async_client(timeout=10.0) as client:
            resp = await client.post(server_url, json=payload, headers=headers)
            resp.raise_for_status()


plugin = NtfyPlugin()
