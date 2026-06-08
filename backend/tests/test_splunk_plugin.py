"""
Unit tests for the Splunk HEC plugin — pure functions and mocked HTTP calls.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from pytest_httpx import HTTPXMock

from plugins.splunk.plugin import (
    SplunkPlugin,
    _build_event,
    _resolve_field,
    _to_epoch,
)

# ---------------------------------------------------------------------------
# _to_epoch
# ---------------------------------------------------------------------------


class TestToEpoch:
    def test_none_returns_none(self):
        assert _to_epoch(None) is None

    def test_int_returns_float(self):
        assert _to_epoch(1700000000) == 1700000000.0

    def test_float_passthrough(self):
        val = 1700000000.123
        assert _to_epoch(val) == val

    def test_iso_string_with_z(self):
        result = _to_epoch("2024-01-15T10:30:00Z")
        assert isinstance(result, float)
        assert result > 0

    def test_iso_string_with_offset(self):
        result = _to_epoch("2024-01-15T10:30:00+00:00")
        assert isinstance(result, float)

    def test_invalid_string_returns_none(self):
        assert _to_epoch("not-a-date") is None

    def test_naive_datetime_string_assumed_utc(self):
        result = _to_epoch("2024-01-15T10:30:00")
        assert isinstance(result, float)

    def test_iso_string_consistent_with_manual(self):
        dt = datetime(2024, 6, 1, 12, 0, 0, tzinfo=UTC)
        iso = dt.isoformat()
        assert abs(_to_epoch(iso) - dt.timestamp()) < 0.001


# ---------------------------------------------------------------------------
# _resolve_field
# ---------------------------------------------------------------------------


class TestResolveField:
    _notif = {
        "id": "abc-123",
        "message": "container updated",
        "title": "Update",
        "sender_name": "myhost",
        "received_at": "2024-06-01T12:00:00Z",
        "source_ip": "1.2.3.4",
        "custom_fields": {"hostname": "srv01", "region": "eu-west-1"},
    }

    def test_literal_prefix(self):
        assert _resolve_field(self._notif, "literal:shoutrrr-logger") == "shoutrrr-logger"

    def test_literal_empty_value(self):
        assert _resolve_field(self._notif, "literal:") == ""

    def test_custom_fields_dot_notation(self):
        assert _resolve_field(self._notif, "custom_fields.hostname") == "srv01"

    def test_custom_fields_missing_key(self):
        assert _resolve_field(self._notif, "custom_fields.missing") is None

    def test_top_level_field(self):
        assert _resolve_field(self._notif, "message") == "container updated"

    def test_received_at_converted_to_epoch(self):
        result = _resolve_field(self._notif, "received_at")
        assert isinstance(result, float)

    def test_missing_top_level_field(self):
        assert _resolve_field(self._notif, "nonexistent_field") is None

    def test_none_custom_fields(self):
        notif = {**self._notif, "custom_fields": None}
        assert _resolve_field(notif, "custom_fields.hostname") is None


# ---------------------------------------------------------------------------
# _build_event
# ---------------------------------------------------------------------------


class TestBuildEvent:
    _notif = {
        "id": "abc-123",
        "message": "container updated",
        "title": "Update",
        "sender_name": "myhost",
        "received_at": "2024-06-01T12:00:00Z",
        "source_ip": "1.2.3.4",
        "custom_fields": {"hostname": "srv01"},
    }

    def test_no_mappings_returns_full_notification(self):
        event = _build_event(self._notif, [])
        assert event["message"] == "container updated"
        assert "id" in event

    def test_no_mappings_excludes_none_values(self):
        notif = {**self._notif, "title": None}
        event = _build_event(notif, [])
        assert "title" not in event

    def test_with_mappings_produces_mapped_keys(self):
        mappings = [
            {"output_key": "msg", "source_field": "message"},
            {"output_key": "host", "source_field": "sender_name"},
        ]
        event = _build_event(self._notif, mappings)
        assert event == {"msg": "container updated", "host": "myhost"}

    def test_mapping_missing_value_excluded(self):
        mappings = [
            {"output_key": "msg", "source_field": "message"},
            {"output_key": "missing", "source_field": "nonexistent_field"},
        ]
        event = _build_event(self._notif, mappings)
        assert "missing" not in event
        assert event["msg"] == "container updated"

    def test_mapping_with_literal(self):
        mappings = [{"output_key": "source", "source_field": "literal:shoutrrr-logger"}]
        event = _build_event(self._notif, mappings)
        assert event["source"] == "shoutrrr-logger"

    def test_mapping_with_custom_field(self):
        mappings = [{"output_key": "hostname", "source_field": "custom_fields.hostname"}]
        event = _build_event(self._notif, mappings)
        assert event["hostname"] == "srv01"

    def test_mapping_empty_output_key_skipped(self):
        mappings = [{"output_key": "", "source_field": "message"}]
        event = _build_event(self._notif, mappings)
        assert event == {}

    def test_mapping_empty_source_field_skipped(self):
        mappings = [{"output_key": "msg", "source_field": ""}]
        event = _build_event(self._notif, mappings)
        assert event == {}


# ---------------------------------------------------------------------------
# SplunkPlugin.on_notification — mocked HTTP
# ---------------------------------------------------------------------------

NOTIF = {
    "id": str(uuid.uuid4()),
    "message": "container updated to v2",
    "title": "Watchtower",
    "sender_name": "docker-host",
    "received_at": "2024-06-01T12:00:00Z",
    "source_ip": "10.0.0.1",
    "custom_fields": {},
}

CONFIG = {
    "hec_url": "http://splunk:8088/services/collector/event",
    "hec_token": "test-hec-token",
    "index": "main",
    "source": "shoutrrr-logger",
    "sourcetype": "_json",
    "field_mappings": [
        {"output_key": "timestamp", "source_field": "received_at"},
        {"output_key": "message", "source_field": "message"},
    ],
    "verify_tls": False,
}


class TestSplunkPluginOnNotification:
    def _plugin(self) -> SplunkPlugin:
        return SplunkPlugin()

    async def test_happy_path(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=CONFIG["hec_url"],
            method="POST",
            status_code=200,
            json={"text": "Success", "code": 0},
        )
        plugin = self._plugin()
        # Should not raise
        await plugin.on_notification(NOTIF, CONFIG)

    async def test_skips_when_no_hec_url(self, httpx_mock: HTTPXMock):
        """No HTTP calls should be made when hec_url is empty."""
        plugin = self._plugin()
        cfg = {**CONFIG, "hec_url": ""}
        await plugin.on_notification(NOTIF, cfg)
        # httpx_mock would fail the test if any unexpected call was made

    async def test_skips_when_no_hec_token(self, httpx_mock: HTTPXMock):
        plugin = self._plugin()
        cfg = {**CONFIG, "hec_token": ""}
        await plugin.on_notification(NOTIF, cfg)

    async def test_redirect_raises_runtime_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=CONFIG["hec_url"],
            method="POST",
            status_code=308,
            headers={"location": "http://splunk:8000/"},
        )
        plugin = self._plugin()
        with pytest.raises(RuntimeError, match="redirect"):
            await plugin.on_notification(NOTIF, CONFIG)

    async def test_html_response_raises_runtime_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=CONFIG["hec_url"],
            method="POST",
            status_code=403,
            headers={"content-type": "text/html"},
            text="<html><body>Forbidden</body></html>",
        )
        plugin = self._plugin()
        with pytest.raises(RuntimeError, match="HTML"):
            await plugin.on_notification(NOTIF, CONFIG)

    async def test_non_200_raises_runtime_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=CONFIG["hec_url"],
            method="POST",
            status_code=503,
            json={"text": "Service Unavailable"},
        )
        plugin = self._plugin()
        with pytest.raises(RuntimeError, match="503"):
            await plugin.on_notification(NOTIF, CONFIG)

    async def test_connect_error_raises_runtime_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_exception(httpx.ConnectError("connection refused"))
        plugin = self._plugin()
        with pytest.raises(RuntimeError, match="connect"):
            await plugin.on_notification(NOTIF, CONFIG)

    async def test_authorization_header_sent(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url=CONFIG["hec_url"],
            method="POST",
            status_code=200,
            json={"text": "Success", "code": 0},
        )
        plugin = self._plugin()
        await plugin.on_notification(NOTIF, CONFIG)
        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"] == f"Splunk {CONFIG['hec_token']}"
