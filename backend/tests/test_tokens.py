"""Integration tests for admin token management: GET/POST/PATCH/DELETE /api/v1/admin/tokens."""

import json

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
# GET /admin/tokens
# ---------------------------------------------------------------------------


class TestAdminListTokens:
    async def test_requires_auth(self, client):
        resp = await client.get("/api/v1/admin/tokens")
        assert resp.status_code == 401

    async def test_viewer_is_forbidden(self, client, viewer_session_headers):
        resp = await client.get("/api/v1/admin/tokens", headers=viewer_session_headers)
        assert resp.status_code == 403

    async def test_admin_can_list(self, client, admin_session_headers, access_token):
        resp = await client.get("/api/v1/admin/tokens", headers=admin_session_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    async def test_token_has_is_global_flag(self, client, admin_session_headers, access_token):
        resp = await client.get("/api/v1/admin/tokens", headers=admin_session_headers)
        tok = next((t for t in resp.json() if t["name"] == "test-token"), None)
        assert tok is not None
        assert tok["is_global"] is True

    async def test_token_includes_owner_username(self, client, admin_session_headers, access_token):
        resp = await client.get("/api/v1/admin/tokens", headers=admin_session_headers)
        tok = next((t for t in resp.json() if t["name"] == "test-token"), None)
        assert tok is not None
        assert tok["owner_username"] == "admin"


# ---------------------------------------------------------------------------
# POST /admin/tokens
# ---------------------------------------------------------------------------


class TestAdminCreateToken:
    async def test_requires_auth(self, client):
        resp = await client.post("/api/v1/admin/tokens", json={"name": "tok"})
        assert resp.status_code == 401

    async def test_viewer_is_forbidden(self, client, viewer_session_headers):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "tok"},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 403

    async def test_creates_global_token(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "new-global"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "new-global"
        assert data["is_global"] is True

    async def test_raw_token_present_exactly_once(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "raw-check"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "raw_token" in data
        assert len(data["raw_token"]) > 10

    async def test_auto_assigns_to_creating_admin(self, client, admin_session_headers):
        """When no user_id is given the token is assigned to the creating admin."""
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "auto-assign"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["owner_username"] == "admin"

    async def test_new_token_usable_on_ingest(self, client, admin_session_headers):
        """A freshly-created admin token must authenticate on POST /shoutrrr."""
        create_resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "ingest-test"},
            headers=admin_session_headers,
        )
        raw = create_resp.json()["raw_token"]
        ingest_resp = await client.post(
            "/api/v1/shoutrrr",
            content=json.dumps({"message": "test"}),
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "application/json"},
        )
        assert ingest_resp.status_code == 202

    async def test_rejects_unknown_user_id(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "tok", "user_id": "00000000-0000-0000-0000-000000000000"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 404

    async def test_rate_limit_override_defaults_to_none(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "no-override"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["rate_limit_override"] is None

    async def test_rate_limit_override_persisted(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "with-override", "rate_limit_override": 15},
            headers=admin_session_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["rate_limit_override"] == 15

    async def test_rejects_negative_rate_limit_override(self, client, admin_session_headers):
        resp = await client.post(
            "/api/v1/admin/tokens",
            json={"name": "bad-override", "rate_limit_override": -1},
            headers=admin_session_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# PATCH /admin/tokens/{token_id}
# ---------------------------------------------------------------------------


class TestAdminUpdateToken:
    async def test_requires_auth(self, client, access_token):
        _, tok = access_token
        resp = await client.patch(f"/api/v1/admin/tokens/{tok.id}", json={"name": "x"})
        assert resp.status_code == 401

    async def test_viewer_is_forbidden(self, client, viewer_session_headers, access_token):
        _, tok = access_token
        resp = await client.patch(
            f"/api/v1/admin/tokens/{tok.id}",
            json={"is_active": False},
            headers=viewer_session_headers,
        )
        assert resp.status_code == 403

    async def test_rename_token(self, client, admin_session_headers, extra_global_token):
        _, tok = extra_global_token
        resp = await client.patch(
            f"/api/v1/admin/tokens/{tok.id}",
            json={"name": "renamed"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "renamed"

    async def test_deactivate_token(self, client, admin_session_headers, extra_global_token):
        _, tok = extra_global_token
        resp = await client.patch(
            f"/api/v1/admin/tokens/{tok.id}",
            json={"is_active": False},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

    async def test_nonexistent_returns_404(self, client, admin_session_headers):
        resp = await client.patch(
            "/api/v1/admin/tokens/00000000-0000-0000-0000-000000000000",
            json={"name": "x"},
            headers=admin_session_headers,
        )
        assert resp.status_code == 404

    async def test_set_rate_limit_override(self, client, admin_session_headers, extra_global_token):
        _, tok = extra_global_token
        resp = await client.patch(
            f"/api/v1/admin/tokens/{tok.id}",
            json={"rate_limit_override": 7},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["rate_limit_override"] == 7

    async def test_clear_rate_limit_override(
        self, client, admin_session_headers, extra_global_token
    ):
        _, tok = extra_global_token
        # First set an override...
        resp = await client.patch(
            f"/api/v1/admin/tokens/{tok.id}",
            json={"rate_limit_override": 7},
            headers=admin_session_headers,
        )
        assert resp.json()["rate_limit_override"] == 7

        # ...then clear it back to "inherit global default".
        resp = await client.patch(
            f"/api/v1/admin/tokens/{tok.id}",
            json={"clear_rate_limit_override": True},
            headers=admin_session_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["rate_limit_override"] is None

    async def test_rejects_negative_rate_limit_override(
        self, client, admin_session_headers, extra_global_token
    ):
        _, tok = extra_global_token
        resp = await client.patch(
            f"/api/v1/admin/tokens/{tok.id}",
            json={"rate_limit_override": -1},
            headers=admin_session_headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# DELETE /admin/tokens/{token_id}
# ---------------------------------------------------------------------------


class TestAdminDeleteToken:
    async def test_requires_auth(self, client, extra_global_token):
        _, tok = extra_global_token
        resp = await client.delete(f"/api/v1/admin/tokens/{tok.id}")
        assert resp.status_code == 401

    async def test_viewer_is_forbidden(self, client, viewer_session_headers, extra_global_token):
        _, tok = extra_global_token
        resp = await client.delete(f"/api/v1/admin/tokens/{tok.id}", headers=viewer_session_headers)
        assert resp.status_code == 403

    async def test_deletes_token(self, client, admin_session_headers, extra_global_token):
        _, tok = extra_global_token
        resp = await client.delete(f"/api/v1/admin/tokens/{tok.id}", headers=admin_session_headers)
        assert resp.status_code == 204

    async def test_nonexistent_returns_404(self, client, admin_session_headers):
        resp = await client.delete(
            "/api/v1/admin/tokens/00000000-0000-0000-0000-000000000000",
            headers=admin_session_headers,
        )
        assert resp.status_code == 404
