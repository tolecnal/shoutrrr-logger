import logging
from typing import Any
from urllib.parse import urljoin

from plugins.base import BasePlugin
from utils.ssrf import create_ssrf_safe_async_client, validate_url_for_ssrf

logger = logging.getLogger(__name__)


class GotifyPlugin(BasePlugin):
    plugin_id = "gotify"
    name = "Gotify"
    description = "Send push notifications to a Gotify server."

    default_config = {
        "server_url": "",
        "app_token": "",
        "priority": 5,
        "message_template": "**{title}**\n\n{message}",
        "use_markdown": True,
    }

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        server_url = config.get("server_url", "").strip()
        app_token = config.get("app_token", "").strip()

        if not server_url:
            return False, "server_url is required"
        if not app_token:
            return False, "app_token is required"

        try:
            validate_url_for_ssrf(server_url)
        except ValueError as e:
            return False, f"Invalid Server URL (SSRF Policy): {str(e)}"

        return True, ""

    async def on_notification(self, notification: dict[str, Any], config: dict[str, Any]) -> None:
        server_url = config.get("server_url", "").strip()
        app_token = config.get("app_token", "").strip()

        if not server_url or not app_token:
            logger.warning("Gotify plugin enabled but server_url or app_token is not configured.")
            return

        try:
            validate_url_for_ssrf(server_url)
        except ValueError as e:
            msg = f"Security error: Gotify server URL blocked by SSRF policy: {e}"
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

        payload: dict[str, Any] = {
            "title": notification.get("title", ""),
            "message": message_text,
            "priority": int(config.get("priority", 5)),
        }

        if config.get("use_markdown", True):
            payload["extras"] = {"client::display": {"contentType": "text/markdown"}}

        headers = {"X-Gotify-Key": app_token}

        endpoint = urljoin(server_url if server_url.endswith("/") else server_url + "/", "message")

        async with create_ssrf_safe_async_client(timeout=10.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            resp.raise_for_status()


plugin = GotifyPlugin()
