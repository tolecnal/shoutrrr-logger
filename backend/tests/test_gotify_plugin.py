import pytest

from plugins.gotify.plugin import GotifyPlugin


def test_validate_config():
    plugin = GotifyPlugin()
    valid, msg = plugin.validate_config(
        {"server_url": "https://gotify.com", "app_token": "token123"}
    )
    assert valid is True

    valid, msg = plugin.validate_config({"app_token": "token123"})
    assert valid is False
    assert "server_url" in msg

    valid, msg = plugin.validate_config({"server_url": "https://gotify.com"})
    assert valid is False
    assert "app_token" in msg


@pytest.mark.asyncio
async def test_on_notification_success(httpx_mock):
    httpx_mock.add_response(url="https://gotify.com/message", status_code=200)

    plugin = GotifyPlugin()
    config = {
        "server_url": "https://gotify.com",
        "app_token": "token123",
        "priority": 8,
        "use_markdown": True,
    }
    notification = {"title": "Test Title", "message": "Test Msg"}

    await plugin.on_notification(notification, config)

    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["x-gotify-key"] == "token123"
    import json

    data = json.loads(request.read())
    assert data["title"] == "Test Title"
    assert "Test Msg" in data["message"]
    assert data["priority"] == 8
    assert data["extras"]["client::display"]["contentType"] == "text/markdown"
