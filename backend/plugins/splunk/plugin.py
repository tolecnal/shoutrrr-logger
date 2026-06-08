"""
Splunk HEC (HTTP Event Collector) plugin.

Forwards each received notification to a Splunk HEC endpoint.  The event
body is built from a configurable ordered list of field mappings so admins
can choose exactly which fields appear in the Splunk event and under what key.

Source field syntax
-------------------
- Any top-level NotificationOut field: ``id``, ``message``, ``title``,
  ``sender_name``, ``received_at``, ``source_ip``
- A key inside custom_fields:  ``custom_fields.<key>``
- A literal constant (prefixed with ``literal:``): ``literal:my-value``

This file is self-contained: adding the backend half of this plugin
requires only this folder — no changes to any core backend files.
The frontend config panel lives in ``frontend/plugins/splunk/`` and
requires one additional line in ``frontend/plugins/registry.tsx``.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from plugins.base import BasePlugin

logger = logging.getLogger(__name__)


def _exc_message(exc: BaseException) -> str:
    """
    Extract a useful message from an exception, walking the cause chain.
    httpx network errors often have an empty str() but carry the real
    reason in __cause__ (e.g. ssl.SSLCertVerificationError, OSError).
    """
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        msg = str(current).strip()
        if msg:
            parts.append(f"{type(current).__name__}: {msg}")
        current = current.__cause__ or current.__context__
    return " — caused by: ".join(parts) if parts else repr(exc)


def _to_epoch(value: Any) -> float | None:
    """Convert an ISO-8601 datetime string to a Unix epoch float (e.g. 1763007221.476147)."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


def _resolve_field(notification: dict[str, Any], source_field: str) -> Any:
    if source_field.startswith("literal:"):
        return source_field[len("literal:") :]
    if source_field.startswith("custom_fields."):
        key = source_field[len("custom_fields.") :]
        return (notification.get("custom_fields") or {}).get(key)
    value = notification.get(source_field)
    # received_at is always stored as an ISO string; convert to epoch float
    # so Splunk's timestamp field contains the correct numeric format.
    if source_field == "received_at" and value is not None:
        return _to_epoch(value)
    return value


def _build_event(
    notification: dict[str, Any],
    field_mappings: list[dict[str, str]],
) -> dict[str, Any]:
    """
    Build the Splunk event dict from the field mappings.
    Falls back to sending the full notification if no mappings are defined.
    """
    if not field_mappings:
        return {k: v for k, v in notification.items() if v is not None}

    event: dict[str, Any] = {}
    for mapping in field_mappings:
        output_key = mapping.get("output_key", "").strip()
        source_field = mapping.get("source_field", "").strip()
        if not output_key or not source_field:
            continue
        value = _resolve_field(notification, source_field)
        if value is not None:
            event[output_key] = value
    return event


class SplunkPlugin(BasePlugin):
    @property
    def plugin_id(self) -> str:
        return "splunk"

    @property
    def name(self) -> str:
        return "Splunk HEC"

    @property
    def description(self) -> str:
        return "Forwards notifications to Splunk via the HTTP Event Collector (HEC)."

    @property
    def default_config(self) -> dict[str, Any]:
        return {
            "hec_url": "",
            "hec_token": "",
            "index": "",
            "source": "shoutrrr-logger",
            "sourcetype": "_json",
            "field_mappings": [
                {"output_key": "timestamp", "source_field": "received_at"},
                {"output_key": "host", "source_field": "sender_name"},
                {"output_key": "message", "source_field": "message"},
                {"output_key": "title", "source_field": "title"},
                {"output_key": "id", "source_field": "id"},
            ],
            "verify_tls": True,
        }

    async def on_notification(
        self,
        notification: dict[str, Any],
        config: dict[str, Any],
    ) -> None:
        hec_url: str = config.get("hec_url", "").strip()
        hec_token: str = config.get("hec_token", "").strip()

        if not hec_url or not hec_token:
            self.log("hec_url or hec_token not configured — skipping", "warning")
            return

        field_mappings: list[dict[str, str]] = config.get("field_mappings", [])
        event_body = _build_event(notification, field_mappings)

        payload: dict[str, Any] = {"event": event_body}
        for meta_key in ("index", "source", "sourcetype"):
            val = config.get(meta_key, "").strip()
            if val:
                payload[meta_key] = val

        verify_tls: bool = bool(config.get("verify_tls", True))

        try:
            async with httpx.AsyncClient(
                verify=verify_tls,
                timeout=10.0,
                # Do NOT follow redirects automatically — a redirect from the
                # HEC port is almost always a misconfiguration (e.g. pointing
                # at the Splunk web UI on :8000 instead of HEC on :8088).
                # We want to surface the redirect clearly rather than silently
                # land on an HTML login page that returns 200 OK.
                follow_redirects=False,
            ) as client:
                resp = await client.post(
                    hec_url,
                    content=json.dumps(payload),
                    headers={
                        "Authorization": f"Splunk {hec_token}",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.ConnectError as exc:
            msg = f"Could not connect to HEC at {hec_url}: {_exc_message(exc)}"
            self.log(msg, "error")
            raise RuntimeError(msg) from exc
        except httpx.TimeoutException as exc:
            msg = f"Connection to HEC at {hec_url} timed out after 10s"
            self.log(msg, "error")
            raise RuntimeError(msg) from exc
        except httpx.RequestError as exc:
            msg = f"HTTP request to HEC failed: {_exc_message(exc)}"
            self.log(msg, "error")
            raise RuntimeError(msg) from exc

        if resp.status_code in (301, 302, 303, 307, 308):
            redirect_target = resp.headers.get("location", "(unknown)")
            msg = (
                f"HEC returned HTTP {resp.status_code} redirect to {redirect_target}. "
                f"This usually means the URL is pointing at the Splunk web UI "
                f"instead of the HEC port (default: 8088). "
                f"Check that your URL is http(s)://<host>:8088/services/collector/event"
            )
            self.log(msg, "error")
            raise RuntimeError(msg)

        if resp.status_code not in (200, 201):
            content_type = resp.headers.get("content-type", "")
            if "html" in content_type:
                msg = (
                    f"HEC returned HTTP {resp.status_code} with an HTML body — "
                    f"the URL may be pointing at the Splunk web UI rather than "
                    f"the HEC endpoint on port 8088."
                )
            else:
                msg = f"HEC returned HTTP {resp.status_code}: {resp.text[:300]}"
            self.log(msg, "error")
            raise RuntimeError(msg)

        self.log(f"Event forwarded for notification {notification.get('id')}")
