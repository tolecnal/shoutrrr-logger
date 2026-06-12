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


async def _default_profile_id(client, headers, plugin_id: str) -> str:
    resp = await client.get(f"/api/v1/admin/plugins/{plugin_id}", headers=headers)
    assert resp.status_code == 200
    return resp.json()["profiles"][0]["id"]


class TestTestPluginProfile:
    async def test_requires_admin(self, client, admin_session_headers, viewer_session_headers):
        profile_id = await _default_profile_id(client, admin_session_headers, "splunk")
        resp = await client.post(
            f"/api/v1/admin/plugins/splunk/profiles/{profile_id}/test",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 403

    async def test_unknown_plugin_returns_404(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/plugins/does-not-exist/profiles/"
            "00000000-0000-0000-0000-000000000000/test",
            headers=admin_session_headers,
        )
        assert resp.status_code == 404

    async def test_unknown_profile_returns_404(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/plugins/splunk/profiles/00000000-0000-0000-0000-000000000000/test",
            headers=admin_session_headers,
        )
        assert resp.status_code == 404

    async def test_profile_test_returns_detail_message(self, client, admin_session_headers):
        # The default profile has no HEC URL/token configured — on_notification
        # takes its no-op "skip" path and returns successfully. Testing does
        # not require the profile to be enabled.
        profile_id = await _default_profile_id(client, admin_session_headers, "splunk")
        resp = await client.post(
            f"/api/v1/admin/plugins/splunk/profiles/{profile_id}/test",
            headers=admin_session_headers,
        )
        assert resp.status_code == 202
        assert resp.json() == {"detail": "Test notification sent"}


class TestGlobalPluginProfiles:
    async def test_every_plugin_gets_a_default_profile(self, client, admin_session_headers):
        resp = await client.get("/api/v1/admin/plugins", headers=admin_session_headers)
        assert resp.status_code == 200
        for plugin in resp.json():
            assert len(plugin["profiles"]) == 1
            assert plugin["profiles"][0]["name"] == "Default"

    async def test_create_rename_delete_profile(self, client, admin_session_headers):
        created = await client.post(
            "/api/v1/admin/plugins/slack/profiles",
            json={"name": "Ops"},
            headers=admin_session_headers,
        )
        assert created.status_code == 201
        profile_id = created.json()["id"]

        renamed = await client.patch(
            f"/api/v1/admin/plugins/slack/profiles/{profile_id}",
            json={"name": "Ops EU", "enabled": True},
            headers=admin_session_headers,
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "Ops EU"
        assert renamed.json()["enabled"] is True

        deleted = await client.delete(
            f"/api/v1/admin/plugins/slack/profiles/{profile_id}",
            headers=admin_session_headers,
        )
        assert deleted.status_code == 204

    async def test_duplicate_name_is_rejected(self, client, admin_session_headers):
        await _default_profile_id(client, admin_session_headers, "slack")
        resp = await client.post(
            "/api/v1/admin/plugins/slack/profiles",
            json={"name": "Default"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 409

    async def test_update_plugin_only_touches_plugin_level_settings(
        self, client, admin_session_headers
    ):
        resp = await client.patch(
            "/api/v1/admin/plugins/slack",
            json={"allow_user_configs": False},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["allow_user_configs"] is False
