import uuid

import httpx
import pytest
from pytest_httpx import HTTPXMock

from plugins.pushover.plugin import PushoverPlugin

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
    "user_key": "test_user_key",
    "api_token": "test_api_token",
    "message_template": "{title}\n{message}",
    "title_template": "Shoutrrr Logger Alert",
    "priority": "1",
    "sound": "alien",
    "device": "iphone",
}


class TestPushoverPluginOnNotification:
    def _plugin(self) -> PushoverPlugin:
        return PushoverPlugin()

    async def test_happy_path(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            method="POST",
            status_code=200,
            json={"status": 1, "request": "abc-123"},
        )
        plugin = self._plugin()
        await plugin.on_notification(NOTIF, CONFIG)
        request = httpx_mock.get_requests()[0]
        # Data is sent as form data or json, but the plugin sends it as data (x-www-form-urlencoded)
        body = request.read().decode("utf-8")
        assert "token=test_api_token" in body
        assert "user=test_user_key" in body
        assert "priority=1" in body
        assert "sound=alien" in body
        assert "device=iphone" in body
        assert "Shoutrrr+Logger+Alert" in body  # URL encoded title

    async def test_skips_when_no_user_key(self, httpx_mock: HTTPXMock):
        plugin = self._plugin()
        cfg = {**CONFIG, "user_key": ""}
        await plugin.on_notification(NOTIF, cfg)

    async def test_skips_when_no_api_token(self, httpx_mock: HTTPXMock):
        plugin = self._plugin()
        cfg = {**CONFIG, "api_token": ""}
        await plugin.on_notification(NOTIF, cfg)

    async def test_non_200_raises_http_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.pushover.net/1/messages.json",
            method="POST",
            status_code=400,
            json={
                "user": "invalid",
                "errors": ["user key is invalid"],
                "status": 0,
                "request": "error-req",
            },
        )
        plugin = self._plugin()
        with pytest.raises(httpx.HTTPStatusError):
            await plugin.on_notification(NOTIF, CONFIG)
