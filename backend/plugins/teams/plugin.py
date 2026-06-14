import logging
from typing import Any

from plugins.base import BasePlugin
from utils.ssrf import create_ssrf_safe_async_client

logger = logging.getLogger(__name__)


class TeamsPlugin(BasePlugin):
    @property
    def plugin_id(self) -> str:
        return "teams"

    @property
    def name(self) -> str:
        return "Microsoft Teams"

    @property
    def description(self) -> str:
        return "Send notifications to Microsoft Teams via Incoming Webhook."

    @property
    def default_config(self) -> dict[str, Any]:
        return {
            "webhook_url": "",
            "message_template": "**{title}**\n\n{message}",
            "theme_color": "0076D7",
            "included_fields": ["severity", "source_ip", "received_at"],
        }

    async def on_notification(self, notification_dict: dict, config: dict[str, Any]) -> None:
        webhook_url = config.get("webhook_url")
        if not webhook_url:
            logger.warning("[Teams] No webhook_url configured; skipping dispatch.")
            return

        template = config.get("message_template", "**{title}**\n\n{message}")
        try:
            text = template.format(
                title=notification_dict.get("title", "No Title"),
                message=notification_dict.get("message", "No Message"),
            )
        except KeyError:
            text = template

        facts = []
        included_fields = config.get("included_fields", [])
        custom_fields = notification_dict.get("custom_fields", {})

        for field in included_fields:
            if field in notification_dict:
                facts.append({"name": field, "value": str(notification_dict[field])})
            elif field in custom_fields:
                facts.append({"name": field, "value": str(custom_fields[field])})

        payload = {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": config.get("theme_color", "0076D7"),
            "summary": notification_dict.get("title", "Shoutrrr Logger Notification"),
            "sections": [
                {
                    "activityTitle": notification_dict.get("title", "Notification"),
                    "text": text,
                    "facts": facts,
                    "markdown": True,
                }
            ],
        }

        async with create_ssrf_safe_async_client(timeout=10.0) as client:
            resp = await client.post(webhook_url, json=payload)
            resp.raise_for_status()


plugin = TeamsPlugin()
