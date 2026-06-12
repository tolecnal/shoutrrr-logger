"""
Integration tests for the admin audit log: entries written by user/token/
settings/plugin admin actions, secret redaction, and GET /admin/audit-logs.
"""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from auth import generate_raw_token, hash_token
from models import AccessToken


@pytest_asyncio.fixture
async def extra_global_token(db: AsyncSession, admin_user):
    """A second global token not used for bearer auth — safe to delete in tests."""
    raw = generate_raw_token()
    tok = AccessToken(
        user_id=admin_user.id,
        name="extra-global",
        token_hash=hash_token(raw),
        is_global=True,
    )
    db.add(tok)
    await db.flush()
    await db.refresh(tok)
    return raw, tok


# ---------------------------------------------------------------------------
# User actions
# ---------------------------------------------------------------------------


class TestUserAuditLogs:
    async def test_create_user_logs_audit_entry(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/users",
            json={
                "sub": "new-sub-001",
                "email": "newuser@example.com",
                "username": "newuser",
                "role": "viewer",
            },
            headers=admin_session_headers,
        )
        assert resp.status_code == 201
        user_id = resp.json()["id"]

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "user.create"},
            headers=admin_session_headers,
        )
        assert logs_resp.status_code == 200
        entry = next(e for e in logs_resp.json()["items"] if e["target_id"] == user_id)
        assert entry["target_type"] == "user"
        assert entry["actor_username"] == "admin"
        assert entry["details"]["username"] == "newuser"
        assert entry["details"]["email"] == "newuser@example.com"

    async def test_update_user_role_change_logs_audit_entry(
        self, client, admin_session_headers, viewer_user
    ):
        resp = await client.patch(
            f"/api/v1/admin/users/{viewer_user.id}",
            json={"role": "admin"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "user.update"},
            headers=admin_session_headers,
        )
        entry = next(e for e in logs_resp.json()["items"] if e["target_id"] == str(viewer_user.id))
        assert entry["details"]["role"] == "admin"

    async def test_delete_user_logs_audit_entry_with_snapshot(
        self, client, admin_session_headers, viewer_user
    ):
        resp = await client.delete(
            f"/api/v1/admin/users/{viewer_user.id}", headers=admin_session_headers
        )
        assert resp.status_code == 204

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "user.delete"},
            headers=admin_session_headers,
        )
        entry = next(e for e in logs_resp.json()["items"] if e["target_id"] == str(viewer_user.id))
        assert entry["details"]["username"] == "viewer"
        assert entry["details"]["email"] == "viewer@example.com"
        assert entry["details"]["role"] == "viewer"


# ---------------------------------------------------------------------------
# Token actions
# ---------------------------------------------------------------------------


class TestTokenAuditLogs:
    async def test_create_token_logs_audit_entry_without_raw_token(
        self, client, admin_session_headers
    ):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "audited-token", "rate_limit_override": 5},
            headers=admin_session_headers,
        )
        assert resp.status_code == 201
        raw_token = resp.json()["raw_token"]
        token_id = resp.json()["id"]

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "token.create"},
            headers=admin_session_headers,
        )
        entry = next(e for e in logs_resp.json()["items"] if e["target_id"] == token_id)
        assert entry["target_type"] == "access_token"
        assert entry["details"]["name"] == "audited-token"
        assert entry["details"]["is_global"] is True
        assert entry["details"]["rate_limit_override"] == 5
        # The raw token value must never be persisted in audit details.
        assert raw_token not in str(entry["details"])

    async def test_update_token_logs_audit_entry(
        self, client, admin_session_headers, extra_global_token
    ):
        _, tok = extra_global_token
        resp = await client.patch(
            f"/api/v1/admin/tokens/{tok.id}",
            json={"name": "renamed-audited", "rate_limit_override": 10},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "token.update"},
            headers=admin_session_headers,
        )
        entry = next(e for e in logs_resp.json()["items"] if e["target_id"] == str(tok.id))
        assert entry["details"]["name"] == "renamed-audited"
        assert entry["details"]["rate_limit_override"] == 10

    async def test_delete_token_logs_audit_entry_with_snapshot(
        self, client, admin_session_headers, extra_global_token
    ):
        _, tok = extra_global_token
        resp = await client.delete(f"/api/v1/admin/tokens/{tok.id}", headers=admin_session_headers)
        assert resp.status_code == 204

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "token.delete"},
            headers=admin_session_headers,
        )
        entry = next(e for e in logs_resp.json()["items"] if e["target_id"] == str(tok.id))
        assert entry["details"]["name"] == "extra-global"
        assert entry["details"]["is_global"] is True


# ---------------------------------------------------------------------------
# Settings actions
# ---------------------------------------------------------------------------


class TestSettingsAuditLog:
    async def test_update_settings_logs_audit_entry(self, client, admin_session_headers):
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"rate_limit_per_minute": 42}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "settings.update"},
            headers=admin_session_headers,
        )
        items = logs_resp.json()["items"]
        entry = items[0]
        assert entry["target_type"] == "setting"
        assert entry["details"]["rate_limit_per_minute"] == {"old": 0, "new": 42}

    async def test_update_settings_no_change_does_not_log(self, client, admin_session_headers):
        # rate_limit_per_minute already defaults to 0 — submitting the same
        # value again is not a change and should not produce a new entry.
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"rate_limit_per_minute": 0}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "settings.update"},
            headers=admin_session_headers,
        )
        assert logs_resp.json()["items"] == []

    async def test_smtp_password_redacted_in_audit_details(self, client, admin_session_headers):
        """The SMTP password must never be persisted in plaintext in the
        audit log, for either the old or new value."""
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"smtp_password": "hunter2"}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "settings.update"},
            headers=admin_session_headers,
        )
        entry = logs_resp.json()["items"][0]
        assert entry["details"]["smtp_password"] == {
            "old": "***REDACTED***",
            "new": "***REDACTED***",
        }
        assert "hunter2" not in str(entry["details"])

    async def test_max_private_tokens_not_redacted(self, client, admin_session_headers):
        """Setting keys containing 'token' but holding non-secret integer
        values (e.g. max_private_tokens) must not be redacted."""
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"max_private_tokens": 7}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "settings.update"},
            headers=admin_session_headers,
        )
        entry = logs_resp.json()["items"][0]
        assert entry["details"]["max_private_tokens"]["new"] == 7


# ---------------------------------------------------------------------------
# Plugin actions
# ---------------------------------------------------------------------------


class TestPluginAuditLog:
    async def test_update_plugin_redacts_secrets_in_audit_details(
        self, client, admin_session_headers
    ):
        resp = await client.patch(
            "/api/v1/admin/plugins/splunk",
            json={
                "enabled": True,
                "config": {
                    "hec_url": "https://splunk.example.com:8088",
                    "hec_token": "supersecret123",
                },
            },
            headers=admin_session_headers,
        )
        assert resp.status_code == 200

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "plugin.update"},
            headers=admin_session_headers,
        )
        entry = logs_resp.json()["items"][0]
        assert entry["target_type"] == "plugin"
        assert entry["target_id"] == "splunk"
        # Both keys are masked: "hec_token" matches "token"/"hec", and
        # "hec_url" matches "hec" too — the redaction errs on the side of caution.
        assert entry["details"]["config"]["hec_token"] == "***REDACTED***"
        assert entry["details"]["config"]["hec_url"] == "***REDACTED***"
        assert "supersecret123" not in str(entry["details"])
        assert "splunk.example.com" not in str(entry["details"])


# ---------------------------------------------------------------------------
# GET /admin/audit-logs
# ---------------------------------------------------------------------------


class TestListAuditLogs:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/admin/audit-logs")
        assert resp.status_code == 401

    async def test_viewer_is_forbidden(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/admin/audit-logs", headers=viewer_session_headers)
        assert resp.status_code == 403

    async def test_pagination(self, client, admin_session_headers):
        # Generate three audit entries.
        for i in range(3):
            resp = await client.post(
                "/api/v1/admin/tokens",
                json={"name": f"page-token-{i}"},
                headers=admin_session_headers,
            )
            assert resp.status_code == 201

        resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "token.create", "page_size": 2},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 3
        assert body["page_size"] == 2
        assert body["pages"] == 2
        assert body["next_cursor"] is not None

        resp2 = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "token.create", "page_size": 2, "cursor": body["next_cursor"]},
            headers=admin_session_headers,
        )
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert len(body2["items"]) == 1
        assert body2["next_cursor"] is None

    async def test_action_filter(self, client, admin_session_headers, extra_global_token):
        _, tok = extra_global_token
        await client.patch(
            f"/api/v1/admin/tokens/{tok.id}",
            json={"name": "filter-check"},
            headers=admin_session_headers,
        )

        resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "token.update"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) >= 1
        assert all(e["action"] == "token.update" for e in items)


# ---------------------------------------------------------------------------
# Notification bulk delete
# ---------------------------------------------------------------------------


class TestBulkDeleteAuditLogs:
    async def test_bulk_delete_logs_audit_entry(
        self, client, admin_session_headers, sample_notification
    ):
        resp = await client.delete(
            "/api/v1/notifications",
            params={"q": "Watchtower"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 1

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "notification.bulk_delete"},
            headers=admin_session_headers,
        )
        assert logs_resp.status_code == 200
        items = logs_resp.json()["items"]
        assert len(items) == 1
        entry = items[0]
        assert entry["target_type"] == "notification"
        assert entry["details"]["deleted_count"] == 1
        assert entry["details"]["query"] == "Watchtower"
        assert entry["details"]["scope"] == "all"

    async def test_viewer_bulk_delete_is_also_audited(
        self, client, viewer_session_headers, admin_session_headers, sample_notification
    ):
        resp = await client.delete(
            "/api/v1/notifications",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200

        logs_resp = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "notification.bulk_delete"},
            headers=admin_session_headers,
        )
        items = logs_resp.json()["items"]
        assert len(items) == 1
        assert items[0]["actor_username"] == "viewer"
