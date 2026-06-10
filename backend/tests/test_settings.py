"""Tests for admin-configurable settings: the ``private_tokens_enabled``
toggle and the ``stats_window_days`` vs. retention cross-field validation."""


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
