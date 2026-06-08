"""
Integration tests for /api/v1/admin/plugins — listing, updating, and testing plugins.
"""


class TestListPlugins:
    async def test_requires_admin(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/admin/plugins", headers=viewer_session_headers)
        assert resp.status_code == 403

    async def test_lists_registered_plugins(self, client, admin_session_headers):
        resp = await client.get("/api/v1/admin/plugins", headers=admin_session_headers)
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.json()]
        assert "splunk" in ids


class TestTestPlugin:
    async def test_requires_admin(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/admin/plugins/splunk/test", headers=viewer_session_headers
        )
        assert resp.status_code == 403

    async def test_unknown_plugin_returns_404(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/plugins/does-not-exist/test", headers=admin_session_headers
        )
        assert resp.status_code == 404

    async def test_disabled_plugin_returns_400(self, client, admin_session_headers):
        resp = await client.post("/api/v1/admin/plugins/splunk/test", headers=admin_session_headers)
        assert resp.status_code == 400
        assert resp.json()["detail"] == "Plugin is disabled"

    async def test_enabled_plugin_returns_detail_message(self, client, admin_session_headers):
        # Enable the plugin without an HEC URL/token configured — on_notification
        # then takes its no-op "skip" path and returns successfully, exercising
        # the same response path that previously raised ResponseValidationError
        # because the route declared `-> dict` but returned nothing.
        patch_resp = await client.patch(
            "/api/v1/admin/plugins/splunk",
            json={"enabled": True},
            headers=admin_session_headers,
        )
        assert patch_resp.status_code == 200

        resp = await client.post("/api/v1/admin/plugins/splunk/test", headers=admin_session_headers)
        assert resp.status_code == 202
        body = resp.json()
        assert body == {"detail": "Test notification sent to plugin 'splunk'"}
