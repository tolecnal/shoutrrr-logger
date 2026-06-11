"""Tests for NotificationService.dispatch_plugins error isolation.

Covers the fix for malformed per-plugin routing rules: a plugin config with
rules that fail RoutingRuleCreate validation must not abort dispatch for the
remaining plugin configs.
"""

from models import PluginConfig
from plugins import registry
from services.notifications import notification_service


class TestDispatchPluginsRuleValidation:
    async def test_malformed_rules_on_one_plugin_does_not_block_others(self, app, db, caplog):
        # "slack" has rules that fail RoutingRuleCreate validation (missing
        # required "name" field) - simulates a user-set malformed rules JSON.
        bad = PluginConfig(id="slack", enabled=True, config={}, rules=[{"severities": ["error"]}])
        # "splunk" has valid (empty) rules and should still run.
        good = PluginConfig(id="splunk", enabled=True, config={}, rules=[])
        db.add_all([bad, good])
        await db.commit()

        registry.discover()
        splunk_plugin = registry.get_plugin("splunk")

        called = {}

        async def _fake_on_notification(notification, config):
            called["splunk"] = True

        original = splunk_plugin.on_notification
        splunk_plugin.on_notification = _fake_on_notification
        try:
            with caplog.at_level("ERROR"):
                await notification_service.dispatch_plugins(
                    {"severity": "error", "message": "test"}, None
                )
        finally:
            splunk_plugin.on_notification = original

        assert called.get("splunk") is True
        assert "failed to evaluate routing rules" in caplog.text
