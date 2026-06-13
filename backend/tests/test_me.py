"""Integration tests for GET/POST/PATCH/DELETE /api/v1/me/tokens."""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from auth import generate_raw_token, hash_token  # noqa: E402
from models import AccessToken  # noqa: E402

# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def viewer_private_token(db: AsyncSession, viewer_user):
    """A private (is_global=False) token owned by viewer_user."""
    raw = generate_raw_token()
    tok = AccessToken(
        user_id=viewer_user.id,
        name="viewer-private-tok",
        token_hash=hash_token(raw),
        is_global=False,
    )
    db.add(tok)
    await db.flush()
    await db.refresh(tok)
    return raw, tok


@pytest_asyncio.fixture
async def admin_private_token(db: AsyncSession, admin_user):
    """A private token owned by admin_user (must not be visible to viewer)."""
    raw = generate_raw_token()
    tok = AccessToken(
        user_id=admin_user.id,
        name="admin-private-tok",
        token_hash=hash_token(raw),
        is_global=False,
    )
    db.add(tok)
    await db.flush()
    await db.refresh(tok)
    return raw, tok


# ---------------------------------------------------------------------------
# GET /me/tokens
# ---------------------------------------------------------------------------


class TestListMyTokens:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/me/tokens")
        assert resp.status_code == 401

    async def test_empty_for_new_user(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/me/tokens", headers=viewer_session_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_returns_own_private_tokens(
        self, client, viewer_session_headers, viewer_private_token
    ):
        _, tok = viewer_private_token
        resp = await client.get("/api/v1/me/tokens", headers=viewer_session_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "viewer-private-tok"
        assert data[0]["is_global"] is False

    async def test_does_not_return_other_users_private_tokens(
        self, client, viewer_session_headers, admin_private_token
    ):
        resp = await client.get("/api/v1/me/tokens", headers=viewer_session_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_does_not_return_global_tokens(
        self, client, viewer_session_headers, db, viewer_user
    ):
        """Global tokens owned by the same user must not appear in /me/tokens."""
        raw = generate_raw_token()
        db.add(
            AccessToken(
                user_id=viewer_user.id,
                name="viewer-global",
                token_hash=hash_token(raw),
                is_global=True,
            )
        )
        await db.flush()
        resp = await client.get("/api/v1/me/tokens", headers=viewer_session_headers)
        names = [t["name"] for t in resp.json()]
        assert "viewer-global" not in names


# ---------------------------------------------------------------------------
# POST /me/tokens
# ---------------------------------------------------------------------------


class TestCreateMyToken:
    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/me/tokens", json={"name": "tok"})
        assert resp.status_code == 401

    async def test_creates_private_token(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/me/tokens",
            json={"name": "my-new-token"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "my-new-token"
        assert data["is_global"] is False

    async def test_raw_token_present_in_response(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/me/tokens",
            json={"name": "tok"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "raw_token" in data
        assert len(data["raw_token"]) > 10

    async def test_raw_token_absent_from_list(self, client, viewer_session_headers):
        """The raw token must not be exposed via the list endpoint."""
        await client.post(
            "/api/v1/me/tokens",
            json={"name": "tok"},
            headers=viewer_session_headers,
        )
        list_resp = await client.get("/api/v1/me/tokens", headers=viewer_session_headers)
        for item in list_resp.json():
            assert "raw_token" not in item

    async def test_rejects_empty_name(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/me/tokens",
            json={"name": ""},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 422

    async def test_enforces_max_tokens_limit(self, client, viewer_session_headers, db, viewer_user):
        """After the default limit (3), a 4th creation must be rejected."""
        for i in range(3):
            raw = generate_raw_token()
            db.add(
                AccessToken(
                    user_id=viewer_user.id,
                    name=f"existing-{i}",
                    token_hash=hash_token(raw),
                    is_global=False,
                )
            )
        await db.flush()

        resp = await client.post(
            "/api/v1/me/tokens",
            json={"name": "one-too-many"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 422
        assert "maximum" in resp.json()["detail"].lower()

    async def test_limit_does_not_count_global_tokens(
        self, client, viewer_session_headers, db, viewer_user
    ):
        """Global tokens owned by the user don't count toward the private-token limit."""
        for i in range(3):
            raw = generate_raw_token()
            db.add(
                AccessToken(
                    user_id=viewer_user.id,
                    name=f"global-{i}",
                    token_hash=hash_token(raw),
                    is_global=True,
                )
            )
        await db.flush()

        resp = await client.post(
            "/api/v1/me/tokens",
            json={"name": "first-private"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 201

    async def test_created_token_is_usable_for_ingest(self, client, viewer_session_headers):
        """A freshly-created personal token must work on POST /shoutrrr."""
        import json as _json

        create_resp = await client.post(
            "/api/v1/me/tokens",
            json={"name": "ingest-test"},
            headers=viewer_session_headers,
        )
        raw = create_resp.json()["raw_token"]
        ingest_resp = await client.post(
            "/api/v1/shoutrrr",
            content=_json.dumps({"message": "hello via personal token"}),
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "application/json"},
        )
        assert ingest_resp.status_code == 202

    async def test_blocked_when_private_tokens_disabled(
        self, client, viewer_session_headers, admin_session_headers
    ):
        resp = await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"private_tokens_enabled": 0}},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200

        resp = await client.post(
            "/api/v1/me/tokens",
            json={"name": "blocked"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 403

    async def test_succeeds_after_reenabling(
        self, client, viewer_session_headers, admin_session_headers
    ):
        await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"private_tokens_enabled": 0}},
            headers=admin_session_headers,
        )
        await client.patch(
            "/api/v1/admin/settings",
            json={"values": {"private_tokens_enabled": 1}},
            headers=admin_session_headers,
        )

        resp = await client.post(
            "/api/v1/me/tokens",
            json={"name": "allowed-again"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 201


# ---------------------------------------------------------------------------
# PATCH /me/tokens/{token_id}
# ---------------------------------------------------------------------------


class TestUpdateMyToken:
    async def test_requires_auth(self, client, viewer_private_token):
        _, tok = viewer_private_token
        resp = await client.patch(f"/api/v1/me/tokens/{tok.id}", json={"name": "x"})
        assert resp.status_code == 401

    async def test_rename_token(self, client, viewer_session_headers, viewer_private_token):
        _, tok = viewer_private_token
        resp = await client.patch(
            f"/api/v1/me/tokens/{tok.id}",
            json={"name": "renamed"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed"

    async def test_deactivate_token(self, client, viewer_session_headers, viewer_private_token):
        _, tok = viewer_private_token
        resp = await client.patch(
            f"/api/v1/me/tokens/{tok.id}",
            json={"is_active": False},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_cannot_update_other_users_token(
        self, client, viewer_session_headers, admin_private_token
    ):
        _, tok = admin_private_token
        resp = await client.patch(
            f"/api/v1/me/tokens/{tok.id}",
            json={"name": "hijacked"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404

    async def test_cannot_update_global_token(
        self, client, viewer_session_headers, db, viewer_user
    ):
        """A global token must be rejected even if owned by the same user."""
        raw = generate_raw_token()
        tok = AccessToken(
            user_id=viewer_user.id, name="global", token_hash=hash_token(raw), is_global=True
        )
        db.add(tok)
        await db.flush()
        resp = await client.patch(
            f"/api/v1/me/tokens/{tok.id}",
            json={"name": "tamper"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404

    async def test_nonexistent_returns_404(self, client, viewer_session_headers):
        resp = await client.patch(
            "/api/v1/me/tokens/00000000-0000-0000-0000-000000000000",
            json={"name": "x"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /me/tokens/{token_id}
# ---------------------------------------------------------------------------


class TestDeleteMyToken:
    async def test_requires_auth(self, client, viewer_private_token):
        _, tok = viewer_private_token
        resp = await client.delete(f"/api/v1/me/tokens/{tok.id}")
        assert resp.status_code == 401

    async def test_deletes_own_private_token(
        self, client, viewer_session_headers, viewer_private_token
    ):
        _, tok = viewer_private_token
        resp = await client.delete(f"/api/v1/me/tokens/{tok.id}", headers=viewer_session_headers)
        assert resp.status_code == 204
        list_resp = await client.get("/api/v1/me/tokens", headers=viewer_session_headers)
        assert list_resp.json() == []

    async def test_cannot_delete_other_users_token(
        self, client, viewer_session_headers, admin_private_token
    ):
        _, tok = admin_private_token
        resp = await client.delete(f"/api/v1/me/tokens/{tok.id}", headers=viewer_session_headers)
        assert resp.status_code == 404

    async def test_cannot_delete_global_token_via_me(
        self, client, viewer_session_headers, access_token
    ):
        """Global tokens must not be deletable through /me/tokens, even if viewer owns them."""
        _, tok = access_token
        resp = await client.delete(f"/api/v1/me/tokens/{tok.id}", headers=viewer_session_headers)
        assert resp.status_code == 404

    async def test_nonexistent_returns_404(self, client, viewer_session_headers):
        resp = await client.delete(
            "/api/v1/me/tokens/00000000-0000-0000-0000-000000000000",
            headers=viewer_session_headers,
        )
        assert resp.status_code == 404
