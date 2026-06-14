import pytest

from plugins.pagerduty.plugin import PagerDutyPlugin


def test_validate_config():
    plugin = PagerDutyPlugin()
    valid, msg = plugin.validate_config({"integration_key": "12345"})
    assert valid is True

    valid, msg = plugin.validate_config({})
    assert valid is False
    assert "integration_key" in msg


@pytest.mark.asyncio
async def test_on_notification_success(httpx_mock):
    httpx_mock.add_response(url="https://events.pagerduty.com/v2/enqueue", status_code=202)

    plugin = PagerDutyPlugin()
    config = {"integration_key": "12345", "source": "test_src"}
    notification = {"title": "Test Alert", "message": "Things are broken", "severity": "error"}

    await plugin.on_notification(notification, config)

    request = httpx_mock.get_request()
    assert request is not None
    import json

    data = json.loads(request.read())

    assert data["routing_key"] == "12345"
    assert data["event_action"] == "trigger"
    assert data["payload"]["summary"] == "Test Alert"
    assert data["payload"]["source"] == "test_src"
    assert data["payload"]["severity"] == "error"
    assert data["payload"]["custom_details"]["message"] == "Things are broken"
