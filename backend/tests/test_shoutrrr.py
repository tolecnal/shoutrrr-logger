"""
Integration tests for POST /api/v1/shoutrrr.

Covers: JSON body, plain-text body, query-param custom fields ($hostname),
missing/invalid token (401), empty body (400).
"""

import json


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
