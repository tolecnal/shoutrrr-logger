import pytest

from plugins.teams.plugin import TeamsPlugin


@pytest.fixture
def teams_plugin():
    return TeamsPlugin()


@pytest.mark.asyncio
async def test_teams_plugin_requires_webhook_url(teams_plugin, caplog):
    config = {}
    notification = {"title": "Test", "message": "Body"}
    await teams_plugin.on_notification(notification, config)
    assert "No webhook_url configured" in caplog.text


@pytest.mark.asyncio
async def test_teams_plugin_dispatches_successfully(teams_plugin, httpx_mock):
    config = {
        "webhook_url": "https://teams.microsoft.com/webhook",
        "theme_color": "FF0000",
        "message_template": "{title} - {message}",
        "included_fields": ["severity"],
    }
    notification = {"title": "Test", "message": "Body", "severity": "High"}

    httpx_mock.add_response(url=config["webhook_url"], status_code=200)

    await teams_plugin.on_notification(notification, config)

    request = httpx_mock.get_request()
    assert request is not None

    import json

    payload = json.loads(request.read().decode("utf-8"))

    assert payload["@type"] == "MessageCard"
    assert payload["themeColor"] == "FF0000"

    section = payload["sections"][0]
    assert section["text"] == "Test - Body"
    assert section["facts"] == [{"name": "severity", "value": "High"}]
