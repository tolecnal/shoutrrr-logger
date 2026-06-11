"""Tests for /api/v1/alerts — in particular access control on /test-email."""

from auth import generate_raw_token, hash_token
from models import AccessToken, AppSetting, Notification


async def _private_token(db, user):
    """Helper: insert and return an is_global=False token for the given user."""
    raw = generate_raw_token()
    tok = AccessToken(
        user_id=user.id,
        name=f"priv-{user.username}",
        token_hash=hash_token(raw),
        is_global=False,
    )
    db.add(tok)
    await db.flush()
    return tok


async def _enable_email_alerts(db):
    db.add(AppSetting(key="email_alerts_enabled", value=1))
    db.add(AppSetting(key="smtp_host", value="smtp.example.com"))
    db.add(AppSetting(key="smtp_port", value=587))
    db.add(AppSetting(key="smtp_from", value="alerts@example.com"))
    await db.flush()


class TestAlertRuleNameValidation:
    """AlertRule.name flows into the alert email Subject header, so it must
    not allow embedded CR/LF (header injection)."""

    async def test_create_rule_rejects_crlf_in_name(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/alerts/rules",
            headers=viewer_session_headers,
            json={"name": "Evil\r\nBcc: attacker@example.com", "match_pattern": "x"},
        )
        assert resp.status_code == 422

    async def test_create_rule_accepts_normal_name(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/alerts/rules",
            headers=viewer_session_headers,
            json={"name": "My Rule", "match_pattern": "x"},
        )
        assert resp.status_code == 201

    async def test_update_rule_rejects_crlf_in_name(self, client, viewer_session_headers):
        create = await client.post(
            "/api/v1/alerts/rules",
            headers=viewer_session_headers,
            json={"name": "My Rule", "match_pattern": "x"},
        )
        assert create.status_code == 201
        rule_id = create.json()["id"]

        resp = await client.patch(
            f"/api/v1/alerts/rules/{rule_id}",
            headers=viewer_session_headers,
            json={"name": "Evil\r\nBcc: attacker@example.com"},
        )
        assert resp.status_code == 422


class TestTestEmailAccessControl:
    """POST /alerts/test-email must not leak another user's private
    notification content into the test email."""

    async def _patch_send_email(self, monkeypatch):
        captured = {}

        async def _fake_send_email_async(**kwargs):
            captured.update(kwargs)

        import routers.alerts as alerts_router

        monkeypatch.setattr(alerts_router, "send_email_async", _fake_send_email_async)
        return captured

    async def test_viewer_cannot_pull_other_users_private_notification_into_email(
        self, client, viewer_session_headers, db, admin_user, monkeypatch
    ):
        captured = await self._patch_send_email(monkeypatch)
        await _enable_email_alerts(db)

        priv = await _private_token(db, admin_user)
        n = Notification(
            token_id=priv.id,
            title="Admin secret title",
            message="Admin secret message body",
        )
        db.add(n)
        await db.flush()
        await db.refresh(n)

        resp = await client.post(
            "/api/v1/alerts/test-email",
            headers=viewer_session_headers,
            json={
                "name": "My Rule",
                "match_type": "contains",
                "match_pattern": "anything",
                "send_email": True,
                "notification_id": str(n.id),
            },
        )
        assert resp.status_code == 204
        assert "Admin secret title" not in captured["body"]
        assert "Admin secret message body" not in captured["body"]
        assert (captured.get("html_body") or "") == "" or (
            "Admin secret" not in captured["html_body"]
        )

    async def test_template_attribute_access_falls_back_to_default_body(
        self, client, admin_session_headers
    ):
        """A `.format()`-style attribute-access payload in an admin-supplied
        template must not be evaluated; preview-template should fall back to
        the safe default body instead of leaking object internals."""
        resp = await client.post(
            "/api/v1/alerts/preview-template",
            headers=admin_session_headers,
            json={"template": "{title.__class__.__init__.__globals__}"},
        )
        assert resp.status_code == 200
        html = resp.json()["html"]
        assert "__globals__" not in html
        assert "__class__" not in html

    async def test_owner_can_use_own_notification_in_test_email(
        self, client, viewer_session_headers, db, viewer_user, monkeypatch
    ):
        captured = await self._patch_send_email(monkeypatch)
        await _enable_email_alerts(db)

        priv = await _private_token(db, viewer_user)
        n = Notification(
            token_id=priv.id,
            title="My own title",
            message="My own message body",
        )
        db.add(n)
        await db.flush()
        await db.refresh(n)

        resp = await client.post(
            "/api/v1/alerts/test-email",
            headers=viewer_session_headers,
            json={
                "name": "My Rule",
                "match_type": "contains",
                "match_pattern": "anything",
                "send_email": True,
                "notification_id": str(n.id),
            },
        )
        assert resp.status_code == 204
        assert "My own title" in captured["body"]
        assert "My own message body" in captured["body"]
