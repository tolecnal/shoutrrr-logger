"""
Integration tests for POST /api/v1/shoutrrr.

Covers: JSON body, plain-text body, query-param custom fields ($hostname),
missing/invalid token (401), empty body (400), and ingestion rate limiting.
"""

import json

import pytest_asyncio

from auth import generate_raw_token, hash_token
from models import AccessToken, AppSetting
from services.notifications import notification_service


class TestShoutrrrReceive:
    async def test_json_body_accepted(self, client, access_token):
        raw, _ = access_token
        resp = await client.post(
            "/api/v1/shoutrrr",
            content=json.dumps({"message": "hello world", "title": "My Title"}),
            headers={
                "Authorization": f"Bearer {raw}",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["message"] == "hello world"
        assert data["title"] == "My Title"
        assert "id" in data

    async def test_plain_text_body_accepted(self, client, access_token):
        raw, _ = access_token
        resp = await client.post(
            "/api/v1/shoutrrr",
            content=b"Watchtower update report: container foo updated",
            headers={
                "Authorization": f"Bearer {raw}",
                "Content-Type": "text/plain",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "Watchtower" in data["message"]
        assert data["title"] is None

    async def test_query_param_custom_fields(self, client, access_token):
        """$hostname query param should appear in custom_fields."""
        raw, _ = access_token
        resp = await client.post(
            "/api/v1/shoutrrr",
            content=json.dumps({"message": "deploy complete"}),
            headers={
                "Authorization": f"Bearer {raw}",
                "Content-Type": "application/json",
            },
            params={"$hostname": "vm-runner01", "$severity": "info"},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["custom_fields"]["hostname"] == "vm-runner01"
        assert data["custom_fields"]["severity"] == "info"

    async def test_shoutrrr_internal_params_not_in_custom_fields(self, client, access_token):
        """@Authorization and disabletls must not bleed into custom_fields."""
        raw, _ = access_token
        resp = await client.post(
            "/api/v1/shoutrrr",
            content=json.dumps({"message": "test"}),
            headers={
                "Authorization": f"Bearer {raw}",
                "Content-Type": "application/json",
            },
            params={"@Authorization": f"Bearer {raw}", "disabletls": "yes", "$env": "prod"},
        )
        assert resp.status_code == 202
        data = resp.json()
        cf = data["custom_fields"]
        assert "Authorization" not in cf
        assert "disabletls" not in cf
        assert cf.get("env") == "prod"

    async def test_missing_token_returns_401(self, client):
        resp = await client.post(
            "/api/v1/shoutrrr",
            content=json.dumps({"message": "hello"}),
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 401

    async def test_invalid_token_returns_401(self, client):
        resp = await client.post(
            "/api/v1/shoutrrr",
            content=json.dumps({"message": "hello"}),
            headers={
                "Authorization": "Bearer invalid-token-xyz",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401

    async def test_empty_body_returns_400(self, client, access_token):
        raw, _ = access_token
        resp = await client.post(
            "/api/v1/shoutrrr",
            content=b"",
            headers={
                "Authorization": f"Bearer {raw}",
                "Content-Type": "text/plain",
            },
        )
        assert resp.status_code == 400

    async def test_json_extra_fields_stored_in_custom_fields(self, client, access_token):
        """Unknown keys in a JSON body become custom_fields."""
        raw, _ = access_token
        resp = await client.post(
            "/api/v1/shoutrrr",
            content=json.dumps({"message": "deploy", "service": "api", "env": "staging"}),
            headers={
                "Authorization": f"Bearer {raw}",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["custom_fields"]["service"] == "api"
        assert data["custom_fields"]["env"] == "staging"


class TestShoutrrrRateLimiting:
    @pytest_asyncio.fixture(autouse=True)
    async def _disable_plugin_dispatch(self, monkeypatch):
        """Avoid dispatch_plugins' background-task session, which on the shared
        in-memory SQLite connection would roll back the request transaction
        and wipe the token/setting rows these multi-request tests rely on."""

        async def _noop(*args, **kwargs):
            return None

        monkeypatch.setattr(notification_service, "dispatch_plugins", _noop)

    async def _post(self, client, raw):
        return await client.post(
            "/api/v1/shoutrrr",
            content=json.dumps({"message": "ping"}),
            headers={
                "Authorization": f"Bearer {raw}",
                "Content-Type": "application/json",
            },
        )

    async def test_default_is_unlimited(self, client, access_token):
        """With no 'rate_limit_per_minute' setting (default 0), requests are never throttled."""
        raw, _ = access_token
        for _ in range(5):
            resp = await self._post(client, raw)
            assert resp.status_code == 202

    async def test_global_limit_returns_429(self, client, db, access_token):
        raw, _ = access_token
        db.add(AppSetting(key="rate_limit_per_minute", value=2))
        await db.flush()

        assert (await self._post(client, raw)).status_code == 202
        assert (await self._post(client, raw)).status_code == 202

        resp = await self._post(client, raw)
        assert resp.status_code == 429
        assert resp.headers["retry-after"] == "60"

    async def test_per_token_override_zero_bypasses_global_limit(self, client, db, access_token):
        raw, tok = access_token
        db.add(AppSetting(key="rate_limit_per_minute", value=1))
        tok.rate_limit_override = 0
        await db.flush()

        for _ in range(3):
            resp = await self._post(client, raw)
            assert resp.status_code == 202

    async def test_per_token_override_custom_limit(self, client, db, access_token):
        raw, tok = access_token
        db.add(AppSetting(key="rate_limit_per_minute", value=100))
        tok.rate_limit_override = 1
        await db.flush()

        assert (await self._post(client, raw)).status_code == 202

        resp = await self._post(client, raw)
        assert resp.status_code == 429


class TestShoutrrrPrivateTokensToggle:
    @pytest_asyncio.fixture(autouse=True)
    async def _disable_plugin_dispatch(self, monkeypatch):
        async def _noop(*args, **kwargs):
            return None

        monkeypatch.setattr(notification_service, "dispatch_plugins", _noop)

    @pytest_asyncio.fixture
    async def private_token(self, db, admin_user):
        raw = generate_raw_token()
        tok = AccessToken(
            user_id=admin_user.id,
            name="private-test-token",
            token_hash=hash_token(raw),
            is_global=False,
        )
        db.add(tok)
        await db.flush()
        await db.refresh(tok)
        return raw, tok

    async def _post(self, client, raw):
        return await client.post(
            "/api/v1/shoutrrr",
            content=json.dumps({"message": "ping"}),
            headers={
                "Authorization": f"Bearer {raw}",
                "Content-Type": "application/json",
            },
        )

    async def test_private_token_rejected_when_disabled(self, client, db, private_token):
        raw, _ = private_token
        db.add(AppSetting(key="private_tokens_enabled", value=0))
        await db.flush()

        resp = await self._post(client, raw)
        assert resp.status_code == 403

    async def test_global_token_unaffected_when_private_disabled(self, client, db, access_token):
        raw, _ = access_token
        db.add(AppSetting(key="private_tokens_enabled", value=0))
        await db.flush()

        resp = await self._post(client, raw)
        assert resp.status_code == 202

    async def test_private_token_works_after_reenabling(self, client, db, private_token):
        raw, _ = private_token
        db.add(AppSetting(key="private_tokens_enabled", value=0))
        await db.flush()
        assert (await self._post(client, raw)).status_code == 403

        setting = await db.get(AppSetting, "private_tokens_enabled")
        setting.value = 1
        await db.flush()

        resp = await self._post(client, raw)
        assert resp.status_code == 202
