"""
Integration tests for /api/v1/user-plugins — named per-user plugin
configuration profiles: CRUD, the per-plugin profile cap (admins exempt),
duplicate-name rejection, per-profile test dispatch, and multi-profile
dispatch via the routing engine.
"""

import pytest

from services.settings import settings_service


async def _profiles(client, headers, plugin_id: str) -> list[dict]:
    resp = await client.get(f"/api/v1/user-plugins/{plugin_id}", headers=headers)
    assert resp.status_code == 200
    return resp.json()["profiles"]


class TestListUserPlugins:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/user-plugins")
        assert resp.status_code == 401

    async def test_every_plugin_gets_a_default_profile(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/user-plugins", headers=viewer_session_headers)
        assert resp.status_code == 200
        plugins = resp.json()
        assert len(plugins) >= 1
        for plugin in plugins:
            assert len(plugin["profiles"]) == 1
            assert plugin["profiles"][0]["name"] == "Default"
            assert plugin["profiles"][0]["enabled"] is False

    async def test_viewer_sees_configured_cap(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/user-plugins", headers=viewer_session_headers)
        assert all(p["max_profiles"] == 5 for p in resp.json())

    async def test_admin_cap_is_unlimited(self, client, admin_session_headers):
        resp = await client.get("/api/v1/user-plugins", headers=admin_session_headers)
        assert all(p["max_profiles"] == 0 for p in resp.json())


class TestCreateProfile:
    async def test_create_named_profile(self, client, viewer_session_headers):
        await _profiles(client, viewer_session_headers, "slack")  # materialize Default
        resp = await client.post(
            "/api/v1/user-plugins/slack/profiles",
            json={"name": "Ops channel"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Ops channel"
        assert body["enabled"] is False

        names = [p["name"] for p in await _profiles(client, viewer_session_headers, "slack")]
        assert names == ["Default", "Ops channel"]

    async def test_duplicate_name_is_rejected(self, client, viewer_session_headers):
        await _profiles(client, viewer_session_headers, "slack")  # materialize Default
        resp = await client.post(
            "/api/v1/user-plugins/slack/profiles",
            json={"name": "Default"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 409

    async def test_unknown_plugin_returns_404(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/user-plugins/nope/profiles",
            json={"name": "x"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404

    async def test_copy_from_duplicates_config_and_rules(self, client, viewer_session_headers):
        source = (await _profiles(client, viewer_session_headers, "slack"))[0]
        rules = [{"name": "crit only", "severities": ["critical"]}]
        resp = await client.patch(
            f"/api/v1/user-plugins/slack/profiles/{source['id']}",
            json={"config": {"webhook_url": "https://hooks.slack.com/services/X"}, "rules": rules},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200

        resp = await client.post(
            "/api/v1/user-plugins/slack/profiles",
            json={"name": "Copy", "copy_from": source["id"]},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 201
        copy = resp.json()
        assert copy["config"]["webhook_url"] == "https://hooks.slack.com/services/X"
        assert copy["rules"] == rules
        assert copy["enabled"] is False  # never copied enabled

    async def test_viewer_cap_enforced(self, client, viewer_session_headers, db):
        await settings_service.update(db, {"user_plugin_profiles_max": 2})
        await db.commit()

        await _profiles(client, viewer_session_headers, "slack")  # Default = 1
        resp = await client.post(
            "/api/v1/user-plugins/slack/profiles",
            json={"name": "Second"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 201
        resp = await client.post(
            "/api/v1/user-plugins/slack/profiles",
            json={"name": "Third"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 403
        assert "Profile limit reached" in resp.json()["detail"]

    async def test_cap_is_per_plugin(self, client, viewer_session_headers, db):
        await settings_service.update(db, {"user_plugin_profiles_max": 1})
        await db.commit()

        await _profiles(client, viewer_session_headers, "slack")
        resp = await client.post(
            "/api/v1/user-plugins/slack/profiles",
            json={"name": "Over cap"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 403
        # A different plugin still has room for its own Default
        assert len(await _profiles(client, viewer_session_headers, "webhook")) == 1

    async def test_admin_bypasses_cap(self, client, admin_session_headers, db):
        await settings_service.update(db, {"user_plugin_profiles_max": 1})
        await db.commit()

        await _profiles(client, admin_session_headers, "slack")
        for i in range(3):
            resp = await client.post(
                "/api/v1/user-plugins/slack/profiles",
                json={"name": f"Extra {i}"},
                headers=admin_session_headers,
            )
            assert resp.status_code == 201

    async def test_zero_cap_means_unlimited(self, client, viewer_session_headers, db):
        await settings_service.update(db, {"user_plugin_profiles_max": 0})
        await db.commit()

        await _profiles(client, viewer_session_headers, "slack")
        for i in range(7):
            resp = await client.post(
                "/api/v1/user-plugins/slack/profiles",
                json={"name": f"P{i}"},
                headers=viewer_session_headers,
            )
            assert resp.status_code == 201


class TestUpdateProfile:
    async def test_update_config_and_enable(self, client, viewer_session_headers):
        profile = (await _profiles(client, viewer_session_headers, "slack"))[0]
        resp = await client.patch(
            f"/api/v1/user-plugins/slack/profiles/{profile['id']}",
            json={"enabled": True, "config": {"webhook_url": "https://hooks.slack.com/x"}},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["enabled"] is True
        assert resp.json()["config"]["webhook_url"] == "https://hooks.slack.com/x"

    async def test_rename(self, client, viewer_session_headers):
        profile = (await _profiles(client, viewer_session_headers, "slack"))[0]
        resp = await client.patch(
            f"/api/v1/user-plugins/slack/profiles/{profile['id']}",
            json={"name": "Renamed"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    async def test_rename_to_existing_name_is_rejected(self, client, viewer_session_headers):
        first = (await _profiles(client, viewer_session_headers, "slack"))[0]
        resp = await client.post(
            "/api/v1/user-plugins/slack/profiles",
            json={"name": "Other"},
            headers=viewer_session_headers,
        )
        other_id = resp.json()["id"]
        resp = await client.patch(
            f"/api/v1/user-plugins/slack/profiles/{other_id}",
            json={"name": first["name"]},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 409

    async def test_cannot_touch_another_users_profile(
        self, client, viewer_session_headers, admin_session_headers
    ):
        admin_profile = (await _profiles(client, admin_session_headers, "slack"))[0]
        resp = await client.patch(
            f"/api/v1/user-plugins/slack/profiles/{admin_profile['id']}",
            json={"enabled": True},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404


class TestDeleteProfile:
    async def test_delete(self, client, viewer_session_headers):
        await _profiles(client, viewer_session_headers, "slack")
        resp = await client.post(
            "/api/v1/user-plugins/slack/profiles",
            json={"name": "Doomed"},
            headers=viewer_session_headers,
        )
        doomed_id = resp.json()["id"]
        resp = await client.delete(
            f"/api/v1/user-plugins/slack/profiles/{doomed_id}",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 204
        names = [p["name"] for p in await _profiles(client, viewer_session_headers, "slack")]
        assert "Doomed" not in names

    async def test_deleting_last_profile_recreates_default(self, client, viewer_session_headers):
        profile = (await _profiles(client, viewer_session_headers, "slack"))[0]
        resp = await client.delete(
            f"/api/v1/user-plugins/slack/profiles/{profile['id']}",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 204
        profiles = await _profiles(client, viewer_session_headers, "slack")
        assert len(profiles) == 1
        assert profiles[0]["name"] == "Default"

    async def test_cannot_delete_another_users_profile(
        self, client, viewer_session_headers, admin_session_headers
    ):
        admin_profile = (await _profiles(client, admin_session_headers, "slack"))[0]
        resp = await client.delete(
            f"/api/v1/user-plugins/slack/profiles/{admin_profile['id']}",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404


class TestTestProfile:
    async def test_viewer_can_test_own_profile(self, client, viewer_session_headers, monkeypatch):
        """Viewers test through /user-plugins — the old UI called the
        admin-only endpoint and always got 403."""
        from plugins import registry as plugin_registry

        profile = (await _profiles(client, viewer_session_headers, "slack"))[0]

        sent = []

        async def fake_on_notification(notification, config):
            sent.append((notification, config))

        plugin = plugin_registry.get_plugin("slack")
        monkeypatch.setattr(plugin, "on_notification", fake_on_notification)

        resp = await client.post(
            f"/api/v1/user-plugins/slack/profiles/{profile['id']}/test",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 202
        assert len(sent) == 1
        assert "Profile test" in sent[0][0]["title"]

    async def test_plugin_failure_returns_502(self, client, viewer_session_headers, monkeypatch):
        from plugins import registry as plugin_registry

        profile = (await _profiles(client, viewer_session_headers, "slack"))[0]

        async def boom(notification, config):
            raise RuntimeError("kaboom")

        plugin = plugin_registry.get_plugin("slack")
        monkeypatch.setattr(plugin, "on_notification", boom)

        resp = await client.post(
            f"/api/v1/user-plugins/slack/profiles/{profile['id']}/test",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 502
        assert "kaboom" in resp.json()["detail"]


class TestProfileAuditLogs:
    async def test_profile_lifecycle_is_audited(
        self, client, viewer_session_headers, admin_session_headers
    ):
        await _profiles(client, viewer_session_headers, "slack")
        created = await client.post(
            "/api/v1/user-plugins/slack/profiles",
            json={"name": "Audited"},
            headers=viewer_session_headers,
        )
        profile_id = created.json()["id"]
        await client.patch(
            f"/api/v1/user-plugins/slack/profiles/{profile_id}",
            json={"enabled": True},
            headers=viewer_session_headers,
        )
        await client.delete(
            f"/api/v1/user-plugins/slack/profiles/{profile_id}",
            headers=viewer_session_headers,
        )

        for action in ("plugin_profile.create", "plugin_profile.update", "plugin_profile.delete"):
            resp = await client.get(
                "/api/v1/admin/audit-logs",
                params={"action": action},
                headers=admin_session_headers,
            )
            items = resp.json()["items"]
            assert len(items) == 1, action
            assert items[0]["target_id"] == f"slack:{profile_id}"


@pytest.mark.usefixtures("db")
class TestMultiProfileDispatch:
    async def test_each_enabled_profile_dispatches_with_own_rules(
        self, db, engine, viewer_user, monkeypatch
    ):
        """Two enabled Slack profiles with different routing rules: a critical
        notification must fire only the profile whose rule matches."""
        from models import UserPluginConfig
        from plugins import registry as plugin_registry
        from services.notifications import notification_service

        matching = UserPluginConfig(
            user_id=viewer_user.id,
            plugin_id="slack",
            name="Critical only",
            enabled=True,
            config={"webhook_url": "https://hooks.slack.com/crit"},
            rules=[{"name": "crit", "severities": ["critical"]}],
        )
        non_matching = UserPluginConfig(
            user_id=viewer_user.id,
            plugin_id="slack",
            name="Info only",
            enabled=True,
            config={"webhook_url": "https://hooks.slack.com/info"},
            rules=[{"name": "info", "severities": ["info"]}],
        )
        db.add_all([matching, non_matching])
        await db.commit()

        fired_configs = []

        async def fake_on_notification(notification, config):
            fired_configs.append(config)

        plugin = plugin_registry.get_plugin("slack")
        monkeypatch.setattr(plugin, "on_notification", fake_on_notification)

        # Point the dispatch session factory at this test's engine
        import database

        monkeypatch.setattr(database, "engine", engine)

        notification = {
            "id": "00000000-0000-0000-0000-000000000001",
            "title": "DB down",
            "message": "quorum lost",
            "severity": "critical",
            "custom_fields": {},
        }
        await notification_service.dispatch_plugins(notification, str(viewer_user.id))

        urls = [c.get("webhook_url") for c in fired_configs]
        assert "https://hooks.slack.com/crit" in urls
        assert "https://hooks.slack.com/info" not in urls
