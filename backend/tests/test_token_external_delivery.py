"""
Tests for the per-token external delivery policy: allow_plugin_dispatch and
allow_email_alerts on access tokens.

Covers the API surface (defaults, create, update for both admin and personal
tokens) and the two ingestion-time gates:
  - plugins: dispatch_plugins is not enqueued when allow_plugin_dispatch is off
  - email: the GUI alert is still created, but pre-marked email_sent so the
    digest worker skips it, when allow_email_alerts is off
"""

from auth import generate_raw_token, hash_token
from models import AccessToken, AlertRule, Notification, UserAlert

# ---------------------------------------------------------------------------
# API: defaults and create
# ---------------------------------------------------------------------------


class TestTokenDeliveryDefaults:
    async def test_admin_create_defaults_to_allowed(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "defaults"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["allow_plugin_dispatch"] is True
        assert body["allow_email_alerts"] is True

    async def test_admin_create_with_flags_off(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "locked", "allow_plugin_dispatch": False, "allow_email_alerts": False},
            headers=admin_session_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["allow_plugin_dispatch"] is False
        assert body["allow_email_alerts"] is False

    async def test_personal_create_with_flags(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/me/tokens",
            json={"name": "mine", "allow_plugin_dispatch": False},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["allow_plugin_dispatch"] is False
        assert body["allow_email_alerts"] is True


class TestTokenDeliveryUpdate:
    async def test_admin_update_toggles_flags(self, client, admin_session_headers):
        created = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "t"},
            headers=admin_session_headers,
        )
        token_id = created.json()["id"]
        resp = await client.patch(
            f"/api/v1/admin/tokens/{token_id}",
            json={"allow_plugin_dispatch": False, "allow_email_alerts": False},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["allow_plugin_dispatch"] is False
        assert resp.json()["allow_email_alerts"] is False

    async def test_admin_update_leaves_unspecified_flag_unchanged(
        self, client, admin_session_headers
    ):
        created = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "t2", "allow_email_alerts": False},
            headers=admin_session_headers,
        )
        token_id = created.json()["id"]
        # Only touch plugin flag; email flag must stay False.
        resp = await client.patch(
            f"/api/v1/admin/tokens/{token_id}",
            json={"allow_plugin_dispatch": False},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["allow_plugin_dispatch"] is False
        assert resp.json()["allow_email_alerts"] is False

    async def test_personal_update_toggles_flags(self, client, viewer_session_headers):
        created = await client.post(
            "/api/v1/me/tokens",
            json={"name": "mine2"},
            headers=viewer_session_headers,
        )
        token_id = created.json()["id"]
        resp = await client.patch(
            f"/api/v1/me/tokens/{token_id}",
            json={"allow_email_alerts": False},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["allow_email_alerts"] is False
        assert resp.json()["allow_plugin_dispatch"] is True

    async def test_create_audit_logs_flags(self, client, admin_session_headers):
        await client.post(
            "/api/v1/admin/tokens",
            json={"name": "audited", "allow_plugin_dispatch": False},
            headers=admin_session_headers,
        )
        logs = await client.get(
            "/api/v1/admin/audit-logs",
            params={"action": "token.create"},
            headers=admin_session_headers,
        )
        entry = next(e for e in logs.json()["items"] if e["details"].get("name") == "audited")
        assert entry["details"]["allow_plugin_dispatch"] is False
        assert entry["details"]["allow_email_alerts"] is True


# ---------------------------------------------------------------------------
# Ingestion gates
# ---------------------------------------------------------------------------


class TestPluginDispatchGate:
    async def test_plugin_dispatch_skipped_when_disallowed(
        self, client, db, admin_user, monkeypatch
    ):
        """Ingesting with a token that disallows plugins must not run dispatch."""
        from services import notifications as notif_module

        raw = generate_raw_token()
        tok = AccessToken(
            user_id=admin_user.id,
            name="no-plugins",
            token_hash=hash_token(raw),
            is_global=True,
            allow_plugin_dispatch=False,
        )
        db.add(tok)
        await db.commit()

        called = {"dispatch": False}

        async def fake_dispatch(notification_dict, user_id_str):
            called["dispatch"] = True

        monkeypatch.setattr(notif_module.notification_service, "dispatch_plugins", fake_dispatch)

        resp = await client.post(
            "/api/v1/shoutrrr",
            content=b"hello world",
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "text/plain"},
        )
        assert resp.status_code == 202
        assert called["dispatch"] is False

    async def test_plugin_dispatch_runs_when_allowed(self, client, db, admin_user, monkeypatch):
        from services import notifications as notif_module

        raw = generate_raw_token()
        tok = AccessToken(
            user_id=admin_user.id,
            name="ok",
            token_hash=hash_token(raw),
            is_global=True,
            allow_plugin_dispatch=True,
        )
        db.add(tok)
        await db.commit()

        called = {"dispatch": False}

        async def fake_dispatch(notification_dict, user_id_str):
            called["dispatch"] = True

        monkeypatch.setattr(notif_module.notification_service, "dispatch_plugins", fake_dispatch)

        resp = await client.post(
            "/api/v1/shoutrrr",
            content=b"hello world",
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "text/plain"},
        )
        assert resp.status_code == 202
        assert called["dispatch"] is True


class TestEmailAlertGate:
    async def test_email_suppressed_but_gui_alert_created(self, app, db, viewer_user):
        """allow_email_alerts=False → UserAlert is created (GUI) but pre-marked
        email_sent so the digest worker skips it."""
        from services.trigger_engine import run_trigger_engine

        raw = generate_raw_token()
        tok = AccessToken(
            user_id=viewer_user.id,
            name="no-email",
            token_hash=hash_token(raw),
            is_global=False,
            allow_email_alerts=False,
        )
        db.add(tok)
        await db.flush()

        notif = Notification(
            token_id=tok.id,
            sender_name="x",
            title="DB down",
            message="quorum lost",
            severity="critical",
        )
        db.add(notif)
        rule = AlertRule(
            user_id=viewer_user.id,
            name="crit",
            match_pattern="quorum",
            match_type="contains",
            match_target="all",
            send_email=True,
            notification_scope="personal_only",
        )
        db.add(rule)
        await db.commit()

        await run_trigger_engine(str(notif.id), str(tok.id), "quorum lost", "DB down")

        from sqlalchemy import select

        alerts = (
            (await db.execute(select(UserAlert).where(UserAlert.notification_id == notif.id)))
            .scalars()
            .all()
        )
        assert len(alerts) == 1  # GUI alert created
        assert alerts[0].email_sent is True  # but email suppressed

    async def test_email_enqueued_when_allowed(self, app, db, viewer_user):
        from services.trigger_engine import run_trigger_engine

        raw = generate_raw_token()
        tok = AccessToken(
            user_id=viewer_user.id,
            name="email-ok",
            token_hash=hash_token(raw),
            is_global=False,
            allow_email_alerts=True,
        )
        db.add(tok)
        await db.flush()

        notif = Notification(
            token_id=tok.id,
            sender_name="x",
            title="DB down",
            message="quorum lost",
            severity="critical",
        )
        db.add(notif)
        rule = AlertRule(
            user_id=viewer_user.id,
            name="crit",
            match_pattern="quorum",
            match_type="contains",
            match_target="all",
            send_email=True,
            notification_scope="personal_only",
        )
        db.add(rule)
        await db.commit()

        await run_trigger_engine(str(notif.id), str(tok.id), "quorum lost", "DB down")

        from sqlalchemy import select

        alert = (
            (await db.execute(select(UserAlert).where(UserAlert.notification_id == notif.id)))
            .scalars()
            .one()
        )
        assert alert.email_sent is False  # left for the digest worker to send


class TestAdminMasterSwitch:
    """The user_external_delivery_enabled admin master switch overrides each
    private token's own toggles; global (admin) tokens are exempt."""

    async def test_master_switch_blocks_private_token_plugins(
        self, client, db, viewer_user, monkeypatch
    ):
        from services import notifications as notif_module
        from services.settings import settings_service

        await settings_service.update(db, {"user_external_delivery_enabled": 0})
        await db.commit()

        raw = generate_raw_token()
        tok = AccessToken(
            user_id=viewer_user.id,
            name="priv",
            token_hash=hash_token(raw),
            is_global=False,
            allow_plugin_dispatch=True,  # token allows, but master switch is off
        )
        db.add(tok)
        await db.commit()

        called = {"dispatch": False}

        async def fake_dispatch(notification_dict, user_id_str):
            called["dispatch"] = True

        monkeypatch.setattr(notif_module.notification_service, "dispatch_plugins", fake_dispatch)

        resp = await client.post(
            "/api/v1/shoutrrr",
            content=b"hello",
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "text/plain"},
        )
        assert resp.status_code == 202
        assert called["dispatch"] is False

    async def test_master_switch_does_not_affect_global_tokens(
        self, client, db, admin_user, monkeypatch
    ):
        from services import notifications as notif_module
        from services.settings import settings_service

        await settings_service.update(db, {"user_external_delivery_enabled": 0})
        await db.commit()

        raw = generate_raw_token()
        tok = AccessToken(
            user_id=admin_user.id,
            name="glob",
            token_hash=hash_token(raw),
            is_global=True,
            allow_plugin_dispatch=True,
        )
        db.add(tok)
        await db.commit()

        called = {"dispatch": False}

        async def fake_dispatch(notification_dict, user_id_str):
            called["dispatch"] = True

        monkeypatch.setattr(notif_module.notification_service, "dispatch_plugins", fake_dispatch)

        resp = await client.post(
            "/api/v1/shoutrrr",
            content=b"hello",
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "text/plain"},
        )
        assert resp.status_code == 202
        assert called["dispatch"] is True  # global token unaffected by the switch

    async def test_master_switch_suppresses_private_token_email(self, app, db, viewer_user):
        from services.settings import settings_service
        from services.trigger_engine import run_trigger_engine

        await settings_service.update(db, {"user_external_delivery_enabled": 0})
        await db.commit()

        raw = generate_raw_token()
        tok = AccessToken(
            user_id=viewer_user.id,
            name="priv-email",
            token_hash=hash_token(raw),
            is_global=False,
            allow_email_alerts=True,  # token allows, but master switch is off
        )
        db.add(tok)
        await db.flush()
        notif = Notification(
            token_id=tok.id, sender_name="x", title="t", message="quorum", severity="critical"
        )
        db.add(notif)
        rule = AlertRule(
            user_id=viewer_user.id,
            name="crit",
            match_pattern="quorum",
            match_type="contains",
            match_target="all",
            send_email=True,
            notification_scope="personal_only",
        )
        db.add(rule)
        await db.commit()

        await run_trigger_engine(str(notif.id), str(tok.id), "quorum", "t")

        from sqlalchemy import select

        alert = (
            (await db.execute(select(UserAlert).where(UserAlert.notification_id == notif.id)))
            .scalars()
            .one()
        )
        assert alert.email_sent is True  # GUI alert created, email suppressed
