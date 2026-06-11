"""
Integration tests for GET /api/v1/notifications — pagination, search, and scope filtering.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from auth import generate_raw_token, hash_token
from models import AccessToken, AppSetting, Notification


async def _seed(
    db: AsyncSession, token_id, count: int, base_msg: str = "msg"
) -> list[Notification]:
    rows = []
    for i in range(count):
        n = Notification(
            token_id=token_id,
            sender_name="host",
            message=f"{base_msg}-{i}",
        )
        db.add(n)
        rows.append(n)
    await db.flush()
    return rows


class TestListNotifications:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/notifications")
        assert resp.status_code == 401

    async def test_empty_returns_zero(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/notifications", headers=viewer_session_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["items"] == []
        assert data["pages"] == 1
        assert data["next_cursor"] is None

    async def test_pagination_page_size(self, client, viewer_session_headers, db, access_token):
        _, tok = access_token
        await _seed(db, tok.id, 25)
        resp = await client.get(
            "/api/v1/notifications",
            params={"page_size": 10},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 25
        assert len(data["items"]) == 10
        assert data["pages"] == 3
        assert data["next_cursor"] is not None

    async def test_second_page_via_cursor(self, client, viewer_session_headers, db, access_token):
        _, tok = access_token
        await _seed(db, tok.id, 5)
        resp = await client.get(
            "/api/v1/notifications",
            params={"page_size": 3},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 3
        assert data["next_cursor"] is not None

        resp2 = await client.get(
            "/api/v1/notifications",
            params={"page_size": 3, "cursor": data["next_cursor"]},
            headers=viewer_session_headers,
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert len(data2["items"]) == 2  # 5 total, 3 on page 1 → 2 on page 2
        assert data2["next_cursor"] is None

        # No overlap between the two pages.
        ids1 = {n["id"] for n in data["items"]}
        ids2 = {n["id"] for n in data2["items"]}
        assert ids1.isdisjoint(ids2)

    async def test_invalid_cursor_returns_400(self, client, viewer_session_headers):
        resp = await client.get(
            "/api/v1/notifications",
            params={"cursor": "not-a-valid-cursor"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 400

    async def test_search_matches_message(self, client, viewer_session_headers, db, access_token):
        _, tok = access_token
        db.add(Notification(token_id=tok.id, message="container updated successfully"))
        db.add(Notification(token_id=tok.id, message="startup complete"))
        await db.flush()
        resp = await client.get(
            "/api/v1/notifications",
            params={"q": "updated"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert "updated" in data["items"][0]["message"]

    async def test_search_matches_title(self, client, viewer_session_headers, db, access_token):
        _, tok = access_token
        db.add(Notification(token_id=tok.id, message="some message", title="Deployment Error"))
        db.add(Notification(token_id=tok.id, message="other message", title="Success"))
        await db.flush()
        resp = await client.get(
            "/api/v1/notifications",
            params={"q": "Error"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["title"] == "Deployment Error"

    async def test_viewer_can_read(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/notifications", headers=viewer_session_headers)
        assert resp.status_code == 200

    async def test_admin_can_read(self, client, admin_session_headers):
        resp = await client.get("/api/v1/notifications", headers=admin_session_headers)
        assert resp.status_code == 200


class TestGetNotification:
    async def test_get_existing(self, client, viewer_session_headers, sample_notification):
        resp = await client.get(
            f"/api/v1/notifications/{sample_notification.id}",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(sample_notification.id)
        assert data["message"] == sample_notification.message

    async def test_get_nonexistent_returns_404(self, client, viewer_session_headers):
        resp = await client.get(
            "/api/v1/notifications/00000000-0000-0000-0000-000000000000",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404

    async def test_custom_fields_populated(
        self, client, viewer_session_headers, sample_notification
    ):
        """sample_notification has a raw_payload with hostname and severity."""
        resp = await client.get(
            f"/api/v1/notifications/{sample_notification.id}",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["custom_fields"]["hostname"] == "test-host"
        assert data["custom_fields"]["severity"] == "info"


# ---------------------------------------------------------------------------
# Scope filtering: scope=global / scope=mine / scope=all
# ---------------------------------------------------------------------------


async def _private_token(db: AsyncSession, user):
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


class TestNotificationScope:
    """GET /api/v1/notifications?scope=... filtering behaviour."""

    async def test_scope_global_shows_global_token_notifications(
        self, client, viewer_session_headers, db, access_token
    ):
        """scope=global must include notifications from global tokens."""
        _, global_tok = access_token
        db.add(Notification(token_id=global_tok.id, message="global-visible"))
        await db.flush()

        resp = await client.get(
            "/api/v1/notifications",
            params={"scope": "global"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        msgs = [n["message"] for n in resp.json()["items"]]
        assert "global-visible" in msgs

    async def test_scope_global_excludes_private_notifications(
        self, client, viewer_session_headers, db, viewer_user
    ):
        """scope=global must NOT include notifications from private tokens."""
        priv = await _private_token(db, viewer_user)
        db.add(Notification(token_id=priv.id, message="private-hidden"))
        await db.flush()

        resp = await client.get(
            "/api/v1/notifications",
            params={"scope": "global"},
            headers=viewer_session_headers,
        )
        msgs = [n["message"] for n in resp.json()["items"]]
        assert "private-hidden" not in msgs

    async def test_scope_mine_shows_own_private_notifications(
        self, client, viewer_session_headers, db, viewer_user
    ):
        """scope=mine must return notifications from the caller's private tokens."""
        priv = await _private_token(db, viewer_user)
        db.add(Notification(token_id=priv.id, message="my-private"))
        await db.flush()

        resp = await client.get(
            "/api/v1/notifications",
            params={"scope": "mine"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["items"][0]["message"] == "my-private"

    async def test_scope_mine_excludes_global_notifications(
        self, client, viewer_session_headers, db, access_token
    ):
        """scope=mine must NOT include notifications from global tokens."""
        _, global_tok = access_token
        db.add(Notification(token_id=global_tok.id, message="global-excluded"))
        await db.flush()

        resp = await client.get(
            "/api/v1/notifications",
            params={"scope": "mine"},
            headers=viewer_session_headers,
        )
        msgs = [n["message"] for n in resp.json()["items"]]
        assert "global-excluded" not in msgs

    async def test_scope_all_viewer_sees_global_and_own_private(
        self, client, viewer_session_headers, db, viewer_user, access_token
    ):
        """Viewer with scope=all sees both global and own private notifications."""
        _, global_tok = access_token
        priv = await _private_token(db, viewer_user)
        db.add(Notification(token_id=global_tok.id, message="global-ok"))
        db.add(Notification(token_id=priv.id, message="mine-ok"))
        await db.flush()

        resp = await client.get(
            "/api/v1/notifications",
            params={"scope": "all"},
            headers=viewer_session_headers,
        )
        msgs = [n["message"] for n in resp.json()["items"]]
        assert "global-ok" in msgs
        assert "mine-ok" in msgs

    async def test_scope_all_viewer_excluded_from_others_private(
        self, client, viewer_session_headers, db, admin_user
    ):
        """Viewer with scope=all must not see another user's private notifications."""
        priv = await _private_token(db, admin_user)
        db.add(Notification(token_id=priv.id, message="admin-private"))
        await db.flush()

        resp = await client.get(
            "/api/v1/notifications",
            params={"scope": "all"},
            headers=viewer_session_headers,
        )
        msgs = [n["message"] for n in resp.json()["items"]]
        assert "admin-private" not in msgs

    async def test_scope_all_admin_sees_everything(
        self, client, admin_session_headers, db, viewer_user, access_token
    ):
        """Admin with scope=all sees all notifications regardless of token scope."""
        _, global_tok = access_token
        priv = await _private_token(db, viewer_user)
        db.add(Notification(token_id=global_tok.id, message="global-for-all"))
        db.add(Notification(token_id=priv.id, message="viewer-private-for-admin"))
        await db.flush()

        resp = await client.get(
            "/api/v1/notifications",
            params={"scope": "all"},
            headers=admin_session_headers,
        )
        msgs = [n["message"] for n in resp.json()["items"]]
        assert "global-for-all" in msgs
        assert "viewer-private-for-admin" in msgs

    async def test_invalid_scope_rejected(self, client, viewer_session_headers):
        resp = await client.get(
            "/api/v1/notifications",
            params={"scope": "invalid"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Access control: a viewer must not be able to read or modify another user's
# private-token notifications by guessing/obtaining their UUID.
# ---------------------------------------------------------------------------


class TestNotificationAccessControl:
    async def test_viewer_cannot_get_other_users_private_notification(
        self, client, viewer_session_headers, db, admin_user
    ):
        priv = await _private_token(db, admin_user)
        n = Notification(token_id=priv.id, message="admin-only-secret")
        db.add(n)
        await db.flush()
        await db.refresh(n)

        resp = await client.get(
            f"/api/v1/notifications/{n.id}",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404

    async def test_admin_can_get_other_users_private_notification(
        self, client, admin_session_headers, db, viewer_user
    ):
        priv = await _private_token(db, viewer_user)
        n = Notification(token_id=priv.id, message="viewer-only-secret")
        db.add(n)
        await db.flush()
        await db.refresh(n)

        resp = await client.get(
            f"/api/v1/notifications/{n.id}",
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "viewer-only-secret"

    async def test_owner_can_get_own_private_notification(
        self, client, viewer_session_headers, db, viewer_user
    ):
        priv = await _private_token(db, viewer_user)
        n = Notification(token_id=priv.id, message="my-own-secret")
        db.add(n)
        await db.flush()
        await db.refresh(n)

        resp = await client.get(
            f"/api/v1/notifications/{n.id}",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["message"] == "my-own-secret"

    async def test_viewer_cannot_update_state_of_other_users_private_notification(
        self, client, viewer_session_headers, db, admin_user
    ):
        db.add(AppSetting(key="alert_states_enabled", value=1))
        priv = await _private_token(db, admin_user)
        n = Notification(token_id=priv.id, message="admin-only-secret")
        db.add(n)
        await db.flush()
        await db.refresh(n)

        resp = await client.patch(
            f"/api/v1/notifications/{n.id}/state",
            json={"state": "acknowledged"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404

    async def test_owner_can_update_state_of_own_notification(
        self, client, viewer_session_headers, db, viewer_user
    ):
        db.add(AppSetting(key="alert_states_enabled", value=1))
        priv = await _private_token(db, viewer_user)
        n = Notification(token_id=priv.id, message="my-own-secret")
        db.add(n)
        await db.flush()
        await db.refresh(n)

        resp = await client.patch(
            f"/api/v1/notifications/{n.id}/state",
            json={"state": "acknowledged"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "acknowledged"
