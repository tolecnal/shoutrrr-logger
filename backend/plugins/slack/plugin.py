import logging
from typing import Any

import httpx

from plugins.base import BasePlugin
from utils.ssrf import validate_url_for_ssrf

logger = logging.getLogger(__name__)


class SlackPlugin(BasePlugin):
    plugin_id = "slack"
    name = "Slack"
    description = "Send notifications to a Slack channel via Incoming Webhook."

    default_config = {
        "webhook_url": "",
        "message_template": "*{title}*\n{message}",
        "included_fields": ["received_at", "source_ip", "severity"],
        "emoji": ":rotating_light:",
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
            logger.warning("Slack plugin enabled but webhook_url is not configured.")
            return

        try:
            validate_url_for_ssrf(webhook_url)
        except ValueError as e:
            msg = f"Security error: Slack Webhook URL blocked by SSRF policy: {e}"
            self.log(msg, "error")
            raise RuntimeError(msg)

        template = config.get("message_template") or self.default_config["message_template"]
        # Basic substitution
        message_text = template
        for k, v in notification.items():
            message_text = message_text.replace(f"{{{k}}}", str(v))

        # Also support {custom_fields.xyz}
        custom_fields = notification.get("custom_fields", {})
        for k, v in custom_fields.items():
            message_text = message_text.replace(f"{{custom_fields.{k}}}", str(v))

        payload = {"text": message_text}

        emoji = config.get("emoji")
        if emoji:
            payload["icon_emoji"] = emoji

        included = config.get("included_fields", [])
        if included:
            fields = []
            for field in included:
                val = notification.get(field)
                if val is not None:
                    fields.append({"title": field, "value": str(val), "short": True})
                elif field.startswith("custom_fields."):
                    cf_key = field.replace("custom_fields.", "")
                    val = custom_fields.get(cf_key)
                    if val is not None:
                        fields.append({"title": field, "value": str(val), "short": True})
            if fields:
                payload["attachments"] = [{"fields": fields}]

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()


plugin = SlackPlugin()
