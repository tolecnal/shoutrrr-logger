import json
import uuid

import httpx
import pytest
from pytest_httpx import HTTPXMock

from plugins.discord.plugin import DiscordPlugin

NOTIF = {
    "id": str(uuid.uuid4()),
    "message": "container updated to v2",
    "title": "Watchtower",
    "sender_name": "docker-host",
    "received_at": "2024-06-01T12:00:00Z",
    "source_ip": "10.0.0.1",
    "severity": "error",
    "custom_fields": {},
}

CONFIG = {
    "webhook_url": "https://discord.com/api/webhooks/123/abc",
    "bot_username": "Test Bot",
    "included_fields": ["source_ip", "severity"],
}


class TestDiscordPluginOnNotification:
    def _plugin(self) -> DiscordPlugin:
        return DiscordPlugin()

    async def test_happy_path(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://discord.com/api/webhooks/123/abc",
            method="POST",
            status_code=204,
        )
        plugin = self._plugin()
        await plugin.on_notification(NOTIF, CONFIG)
        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode("utf-8"))

        assert body["username"] == "Test Bot"
        embed = body["embeds"][0]
        assert embed["color"] == 16711680  # error color
        assert embed["title"] == "Watchtower"
        assert embed["description"] == "container updated to v2"
        assert len(embed["fields"]) == 2
        assert embed["fields"][0]["name"] == "source_ip"
        assert embed["fields"][0]["value"] == "10.0.0.1"

    async def test_skips_when_no_webhook_url(self, httpx_mock: HTTPXMock):
        plugin = self._plugin()
        cfg = {**CONFIG, "webhook_url": ""}
        await plugin.on_notification(NOTIF, cfg)

    async def test_non_204_raises_http_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://discord.com/api/webhooks/123/abc",
            method="POST",
            status_code=400,
        )
        plugin = self._plugin()
        with pytest.raises(httpx.HTTPStatusError):
            await plugin.on_notification(NOTIF, CONFIG)
