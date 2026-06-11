"""Tests for admin-configurable settings: the ``private_tokens_enabled``
toggle and the ``stats_window_days`` vs. retention cross-field validation."""

from services.settings import SECRET_PLACEHOLDER


class TestSettingsExposure:
    async def test_private_tokens_enabled_exposed(self, client, admin_session_headers):
        resp = await client.get("/api/v1/admin/settings", headers=admin_session_headers)
        assert resp.status_code == 200
        by_key = {s["key"]: s for s in resp.json()}
        assert by_key["private_tokens_enabled"]["value"] == 1
        assert by_key["private_tokens_enabled"]["default"] == 1
        assert by_key["private_tokens_enabled"]["value_type"] == "bool"

    async def test_int_settings_have_value_type_int(self, client, admin_session_headers):
        resp = await client.get("/api/v1/admin/settings", headers=admin_session_headers)
        by_key = {s["key"]: s for s in resp.json()}
        assert by_key["retention_days"]["value_type"] == "int"
        assert by_key["stats_window_days"]["value_type"] == "int"


class TestSecretSettingMasking:
    """smtp_password must never be exposed in plaintext via GET /settings or
    GET /admin/settings, and re-submitting the placeholder must not clobber
    the stored value."""

    async def test_unset_secret_is_empty(self, client, admin_session_headers):
        resp = await client.get("/api/v1/admin/settings", headers=admin_session_headers)
        by_key = {s["key"]: s for s in resp.json()}
        assert by_key["smtp_password"]["value"] == ""

    async def test_set_secret_is_masked_for_admin_and_viewer(
        self, client, admin_session_headers, viewer_session_headers
    ):
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"smtp_password": "hunter2"}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        by_key = {s["key"]: s for s in resp.json()}
        assert by_key["smtp_password"]["value"] == SECRET_PLACEHOLDER

        admin_resp = await client.get("/api/v1/admin/settings", headers=admin_session_headers)
        assert {s["key"]: s for s in admin_resp.json()}["smtp_password"]["value"] == (
            SECRET_PLACEHOLDER
        )

        viewer_resp = await client.get("/api/v1/settings", headers=viewer_session_headers)
        assert {s["key"]: s for s in viewer_resp.json()}["smtp_password"]["value"] == (
            SECRET_PLACEHOLDER
        )

    async def test_resubmitting_placeholder_does_not_change_stored_secret(
        self, client, admin_session_headers
    ):
        await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"smtp_password": "hunter2"}},
            headers=admin_session_headers,
        )

        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"smtp_password": SECRET_PLACEHOLDER, "rate_limit_per_minute": 5}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        by_key = {s["key"]: s for s in resp.json()}
        assert by_key["smtp_password"]["value"] == SECRET_PLACEHOLDER
        assert by_key["rate_limit_per_minute"]["value"] == 5

        # No audit entry for smtp_password since it wasn't actually changed.
        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "settings.update"},
            headers=admin_session_headers,
        )
        latest = logs_resp.json()["items"][0]
        assert "smtp_password" not in latest["details"]
        assert latest["details"]["rate_limit_per_minute"] == {"old": 0, "new": 5}

    async def test_empty_string_clears_secret(self, client, admin_session_headers):
        await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"smtp_password": "hunter2"}},
            headers=admin_session_headers,
        )

        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"smtp_password": ""}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        by_key = {s["key"]: s for s in resp.json()}
        assert by_key["smtp_password"]["value"] == ""


class TestSmtpTestEndpoint:
    """POST /admin/settings/test-smtp must use the real stored password when
    the frontend echoes back the masked placeholder."""

    def _patch_send_email(self, monkeypatch):
        captured = {}

        async def _fake_send_email_async(**kwargs):
            captured.update(kwargs)

        import routers.settings as settings_router

        monkeypatch.setattr(settings_router, "send_email_async", _fake_send_email_async)
        return captured

    async def test_placeholder_password_is_substituted_with_stored_value(
        self, client, admin_session_headers, monkeypatch
    ):
        captured = self._patch_send_email(monkeypatch)

        await client.patch(
            "/api/v1/admin/settings",
            json={
                "values": {
                    "smtp_host": "smtp.example.com",
                    "smtp_user": "alerts",
                    "smtp_password": "hunter2",
                    "smtp_from": "alerts@example.com",
                }
            },
            headers=admin_session_headers,
        )

        resp = await client.post(
            "/api/v1/admin/settings/test-smtp",
            json={
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "alerts",
                "smtp_password": SECRET_PLACEHOLDER,
                "smtp_from_address": "alerts@example.com",
            },
            headers=admin_session_headers,
        )
        assert resp.status_code == 204
        assert captured["password"] == "hunter2"

    async def test_new_unsaved_password_is_used_directly(
        self, client, admin_session_headers, monkeypatch
    ):
        captured = self._patch_send_email(monkeypatch)

        resp = await client.post(
            "/api/v1/admin/settings/test-smtp",
            json={
                "smtp_host": "smtp.example.com",
                "smtp_port": 587,
                "smtp_user": "alerts",
                "smtp_password": "not-yet-saved",
                "smtp_from_address": "alerts@example.com",
            },
            headers=admin_session_headers,
        )
        assert resp.status_code == 204
        assert captured["password"] == "not-yet-saved"


class TestStatsWindowVsRetentionValidation:
    async def test_stats_window_exceeds_retention_rejected(self, client, admin_session_headers):
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"retention_days": 10, "stats_window_days": 30}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 422
        assert "Retention period" in resp.json()["detail"]

    async def test_stats_window_exceeds_api_metrics_retention_rejected(
        self, client, admin_session_headers
    ):
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"api_metrics_retention_days": 10, "stats_window_days": 30}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 422
        assert "API metrics retention" in resp.json()["detail"]

    async def test_zero_retention_means_no_constraint(self, client, admin_session_headers):
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={
                "values": {
                    "retention_days": 0,
                    "api_metrics_retention_days": 0,
                    "stats_window_days": 365,
                }
            },
            headers=admin_session_headers,
        )
        assert resp.status_code == 200

    async def test_lowering_retention_below_existing_stats_window_rejected(
        self, client, admin_session_headers
    ):
        # stats_window_days defaults to 30; lowering retention_days below
        # that must be rejected even though stats_window_days isn't part
        # of this request.
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"retention_days": 10}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 422
        assert "Retention period" in resp.json()["detail"]
