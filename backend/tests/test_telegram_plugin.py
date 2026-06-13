import json
import uuid

import httpx
import pytest
from pytest_httpx import HTTPXMock

from plugins.telegram.plugin import TelegramPlugin

NOTIF = {
    "id": str(uuid.uuid4()),
    "message": "container updated to v2",
    "title": "Watchtower",
    "sender_name": "docker-host",
    "received_at": "2024-06-01T12:00:00Z",
    "source_ip": "10.0.0.1",
    "severity": "info",
    "custom_fields": {},
}

CONFIG = {
    "bot_token": "123:ABC",
    "chat_id": "@mychannel",
    "message_template": "<b>{title}</b>\n{message}",
    "included_fields": ["source_ip", "severity"],
}


class TestTelegramPluginOnNotification:
    def _plugin(self) -> TelegramPlugin:
        return TelegramPlugin()

    async def test_happy_path(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.telegram.org/bot123:ABC/sendMessage",
            method="POST",
            status_code=200,
        )
        plugin = self._plugin()
        await plugin.on_notification(NOTIF, CONFIG)
        request = httpx_mock.get_requests()[0]
        body = json.loads(request.read().decode("utf-8"))

        assert body["chat_id"] == "@mychannel"
        assert body["parse_mode"] == "HTML"
        assert body["disable_web_page_preview"] is True

        text = body["text"]
        assert "<b>Watchtower</b>" in text
        assert "container updated to v2" in text
        assert "<pre>" in text
        assert "source_ip: 10.0.0.1" in text
        assert "severity: info" in text

    async def test_skips_when_missing_config(self, httpx_mock: HTTPXMock):
        plugin = self._plugin()
        cfg = {**CONFIG, "bot_token": ""}
        await plugin.on_notification(NOTIF, cfg)

        cfg2 = {**CONFIG, "chat_id": ""}
        await plugin.on_notification(NOTIF, cfg2)

    async def test_non_200_raises_http_error(self, httpx_mock: HTTPXMock):
        httpx_mock.add_response(
            url="https://api.telegram.org/bot123:ABC/sendMessage",
            method="POST",
            status_code=400,
        )
        plugin = self._plugin()
        with pytest.raises(httpx.HTTPStatusError):
            await plugin.on_notification(NOTIF, CONFIG)
