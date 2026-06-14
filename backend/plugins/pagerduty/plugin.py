import logging
from typing import Any

from plugins.base import BasePlugin
from utils.ssrf import create_ssrf_safe_async_client, validate_url_for_ssrf

logger = logging.getLogger(__name__)


class PagerDutyPlugin(BasePlugin):
    plugin_id = "pagerduty"
    name = "PagerDuty"
    description = "Send incidents to PagerDuty using the Events API V2."

    default_config = {
        "integration_key": "",
        "source": "Shoutrrr Logger",
        "severity": "info",
    }

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        integration_key = config.get("integration_key", "").strip()

        if not integration_key:
            return False, "integration_key is required"

        return True, ""

    async def on_notification(self, notification: dict[str, Any], config: dict[str, Any]) -> None:
        integration_key = config.get("integration_key", "").strip()

        if not integration_key:
            logger.warning("PagerDuty plugin enabled but integration_key is not configured.")
            return

        server_url = "https://events.pagerduty.com/v2/enqueue"

        try:
            validate_url_for_ssrf(server_url)
        except ValueError as e:
            msg = f"Security error: PagerDuty server URL blocked by SSRF policy: {e}"
            self.log(msg, "error")
            raise RuntimeError(msg)

        custom_fields = notification.get("custom_fields", {})

        # Determine severity based on payload or config
        # Pagerduty severities: critical, error, warning, info
        severity_mapping = {
            "debug": "info",
            "info": "info",
            "warning": "warning",
            "error": "error",
            "critical": "critical",
        }

        event_severity = str(notification.get("severity", config.get("severity", "info"))).lower()
        pd_severity = severity_mapping.get(event_severity, "info")

        payload: dict[str, Any] = {
            "routing_key": integration_key,
            "event_action": "trigger",
            "payload": {
                "summary": notification.get("title")
                or (notification.get("message") or "")[:100]
                or "New Alert",
                "source": config.get("source", "Shoutrrr Logger"),
                "severity": pd_severity,
                "custom_details": {
                    "message": notification.get("message", ""),
                    "received_at": notification.get("received_at", ""),
                    "source_ip": notification.get("source_ip", ""),
                    **custom_fields,
                },
            },
        }

        async with create_ssrf_safe_async_client(timeout=10.0) as client:
            resp = await client.post(server_url, json=payload)
            resp.raise_for_status()


plugin = PagerDutyPlugin()
