import logging
from typing import Any

from plugins.base import BasePlugin
from utils.ssrf import create_ssrf_safe_async_client, validate_url_for_ssrf

logger = logging.getLogger(__name__)


class DiscordPlugin(BasePlugin):
    plugin_id = "discord"
    name = "Discord"
    description = "Send notifications to a Discord channel via Webhook."

    default_config = {
        "webhook_url": "",
        "bot_username": "Shoutrrr Logger",
        "included_fields": ["received_at", "source_ip", "severity"],
    }

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not config.get("webhook_url"):
            return False, "webhook_url is required"
        try:
            validate_url_for_ssrf(config.get("webhook_url"))
        except ValueError as e:
            return False, f"Invalid URL (SSRF Policy): {str(e)}"
        return True, ""

    async def on_notification(self, notification: dict[str, Any], config: dict[str, Any]) -> None:
        webhook_url = config.get("webhook_url", "").strip()
        if not webhook_url:
            logger.warning("Discord plugin enabled but webhook_url is not configured.")
            return

        try:
            validate_url_for_ssrf(webhook_url)
        except ValueError as e:
            msg = f"Security error: Discord Webhook URL blocked by SSRF policy: {e}"
            self.log(msg, "error")
            raise RuntimeError(msg)

        # Discord Embed Colors based on severity
        # info: blue (3447003), warn: yellow (16776960), error: red (16711680)
        severity = str(notification.get("severity", "info")).lower()
        color = 3447003
        if severity in ["warn", "warning"]:
            color = 16776960
        elif severity in ["error", "critical", "fatal"]:
            color = 16711680
        elif severity in ["success", "ok"]:
            color = 65280

        title = notification.get("title", "")
        message = notification.get("message", "")

        embed: dict[str, Any] = {
            "color": color,
        }
        if title:
            embed["title"] = title
        if message:
            embed["description"] = message

        custom_fields = notification.get("custom_fields", {})
        included = config.get("included_fields", [])

        if included:
            fields = []
            for field in included:
                val = notification.get(field)
                if val is not None:
                    fields.append({"name": field, "value": str(val), "inline": True})
                elif field.startswith("custom_fields."):
                    cf_key = field.replace("custom_fields.", "")
                    val = custom_fields.get(cf_key)
                    if val is not None:
                        fields.append({"name": field, "value": str(val), "inline": True})
            if fields:
                embed["fields"] = fields

        payload = {"username": config.get("bot_username", "Shoutrrr Logger"), "embeds": [embed]}

        async with create_ssrf_safe_async_client(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()


plugin = DiscordPlugin()
