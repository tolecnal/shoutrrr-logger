import re

import pytest

from plugins.matrix.plugin import MatrixPlugin


@pytest.fixture
def matrix_plugin():
    return MatrixPlugin()


@pytest.mark.asyncio
async def test_matrix_plugin_requires_config(matrix_plugin, caplog):
    config = {"homeserver_url": "https://matrix.org"}
    notification = {"title": "Test", "message": "Body"}
    await matrix_plugin.on_notification(notification, config)
    assert "Missing access_token or room_id" in caplog.text


@pytest.mark.asyncio
async def test_matrix_plugin_dispatches_successfully(matrix_plugin, httpx_mock):
    config = {
        "homeserver_url": "https://matrix.example.com",
        "access_token": "secret_token",
        "room_id": "!room:example.com",
        "message_template": "{title} - {message}",
    }
    notification = {"title": "Test", "message": "Body"}

    httpx_mock.add_response(
        method="PUT",
        url=re.compile(
            r"https://matrix\.example\.com/_matrix/client/v3/rooms/%21room%3Aexample\.com/send/m\.room\.message/.*"
        ),
        status_code=200,
    )

    await matrix_plugin.on_notification(notification, config)

    request = httpx_mock.get_request()
    assert request is not None
    assert request.headers["Authorization"] == "Bearer secret_token"

    import json

    payload = json.loads(request.read().decode("utf-8"))

    assert payload["msgtype"] == "m.text"
    assert payload["body"] == "Test - Body"
