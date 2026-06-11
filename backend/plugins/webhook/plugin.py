import json
import logging
from typing import Any

from plugins.base import BasePlugin
from utils.ssrf import create_ssrf_safe_async_client, validate_url_for_ssrf

logger = logging.getLogger(__name__)


class WebhookPlugin(BasePlugin):
    plugin_id = "webhook"
    name = "Generic Webhook"
    description = "Send notifications to an arbitrary HTTP endpoint."

    default_config = {
        "url": "",
        "method": "POST",
        "headers": '{"Content-Type": "application/json"}',
        "payload_template": '{"title": "{title}", "message": "{message}"}',
    }

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, str]:
        if not config.get("url"):
            return False, "URL is required"
        try:
            validate_url_for_ssrf(config.get("url"))
        except ValueError as e:
            return False, f"Invalid URL (SSRF Policy): {str(e)}"

        method = config.get("method", "").upper()
        if method not in ["POST", "PUT", "PATCH", "GET"]:
            return False, "Method must be POST, PUT, PATCH, or GET"

        headers_str = config.get("headers", "{}")
        try:
            headers = json.loads(headers_str)
            if not isinstance(headers, dict):
                return False, "Headers must be a JSON object"
        except json.JSONDecodeError:
            return False, "Headers must be valid JSON"

        # Do a test parse of payload template if it's supposed to be JSON
        # It's a template so it might not be valid JSON until rendered, but we can't fully validate
        return True, ""

    async def on_notification(self, notification: dict[str, Any], config: dict[str, Any]) -> None:
        url = config.get("url", "").strip()
        if not url:
            logger.warning("Webhook plugin enabled but url is not configured.")
            return

        try:
            validate_url_for_ssrf(url)
        except ValueError as e:
            msg = f"Security error: Webhook URL blocked by SSRF policy: {e}"
            self.log(msg, "error")
            raise RuntimeError(msg)

        template = config.get("payload_template") or self.default_config["payload_template"]

        # Basic substitution
        payload_text = template
        for k, v in notification.items():
            if k != "custom_fields":
                # JSON escape string values for safety if they are injected into JSON quotes
                # A simple replace isn't fully safe against JSON injection if users don't quote properly,
                # but standard json.dumps is too structured. We use string replace.
                val = str(v).replace('"', '\\"').replace("\n", "\\n")
                payload_text = payload_text.replace(f"{{{k}}}", val)

        custom_fields = notification.get("custom_fields", {})
        for k, v in custom_fields.items():
            val = str(v).replace('"', '\\"').replace("\n", "\\n")
            payload_text = payload_text.replace(f"{{custom_fields.{k}}}", val)

        headers = {}
        headers_str = config.get("headers", "{}")
        try:
            headers = json.loads(headers_str)
        except json.JSONDecodeError:
            pass

        method = config.get("method", "POST").upper()

        async with create_ssrf_safe_async_client(timeout=10.0) as client:
            # We send payload_text as content (bytes) rather than json=, so they can use arbitrary formats.
            if method == "GET":
                resp = await client.get(url, headers=headers)
            elif method == "PUT":
                resp = await client.put(url, headers=headers, content=payload_text.encode("utf-8"))
            elif method == "PATCH":
                resp = await client.patch(
                    url, headers=headers, content=payload_text.encode("utf-8")
                )
            else:
                resp = await client.post(url, headers=headers, content=payload_text.encode("utf-8"))

            resp.raise_for_status()


plugin = WebhookPlugin()
