import uuid

import httpx
import pytest
from pytest_httpx import HTTPXMock

from plugins.ntfy.plugin import NtfyPlugin

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
    "server_url": "https://ntfy.sh",
    "topic": "test_topic",
    "priority": "high",
    "tags": "warning,test",
    "message_template": "{title}\n{message}",
    "access_token": "secret_token",
}


class TestNtfyPluginOnNotification:
    def _plugin(self) -> NtfyPlugin:
        return NtfyPlugin()

    async def test_happy_path(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://ntfy.sh",
            method="POST",
            status_code=200,
            json={
                "id": "abc",
                "time": 12345,
                "event": "message",
                "topic": "test_topic",
                "message": "Watchtower\ncontainer updated to v2",
            },
        )
        plugin = self._plugin()
        await plugin.on_notification(NOTIF, CONFIG)
        request = httpx_mock.get_requests()[0]
        assert request.headers["Authorization"] == "Bearer secret_token"
        assert request.headers["Tags"] == "warning,test"
        assert request.headers["Priority"] == "4"

    async def test_skips_when_no_server_url(self, httpx_mock: HTTPXMock):
        plugin = self._plugin()
        cfg = {**CONFIG, "server_url": ""}
        await plugin.on_notification(NOTIF, cfg)

    async def test_skips_when_no_topic(self, httpx_mock: HTTPXMock):
        plugin = self._plugin()
        cfg = {**CONFIG, "topic": ""}
        await plugin.on_notification(NOTIF, cfg)

    async def test_non_200_raises_http_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://ntfy.sh",
            method="POST",
            status_code=503,
            text="Service Unavailable",
        )
        plugin = self._plugin()
        with pytest.raises(httpx.HTTPStatusError):
            await plugin.on_notification(NOTIF, CONFIG)
