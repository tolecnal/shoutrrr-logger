"""
Tests for plugins/registry.py — discovery, retrieval, and listing.
"""

from plugins import registry
from plugins.splunk.plugin import SplunkPlugin


class TestPluginRegistry:
    def setup_method(self):
        # Ensure a clean discovery state before each test
        registry._REGISTRY.clear()

    def test_discover_finds_splunk_plugin(self):
        registry.discover()
        assert "splunk" in registry._REGISTRY

    def test_discover_is_idempotent(self):
        registry.discover()
        registry.discover()
        # Should not double-register
        assert len([p for p in registry._REGISTRY if p == "splunk"]) == 1

    def test_get_plugin_returns_instance(self):
        registry.discover()
        plugin = registry.get_plugin("splunk")
        assert isinstance(plugin, SplunkPlugin)

    def test_get_plugin_unknown_returns_none(self):
        registry.discover()
        assert registry.get_plugin("nonexistent") is None

    def test_all_plugins_nonempty(self):
        registry.discover()
        plugins = registry.all_plugins()
        assert len(plugins) >= 1

    def test_splunk_plugin_id(self):
        registry.discover()
        plugin = registry.get_plugin("splunk")
        assert plugin.plugin_id == "splunk"

    def test_splunk_plugin_has_default_config(self):
        registry.discover()
        plugin = registry.get_plugin("splunk")
        cfg = plugin.default_config
        assert "hec_url" in cfg
        assert "hec_token" in cfg
        assert "field_mappings" in cfg
