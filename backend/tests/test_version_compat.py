"""
Tests for the /api/health, /api/version endpoints and the
backward-compat 308 redirect middleware.
"""

import tomllib
from pathlib import Path


class TestAppVersionSource:
    def test_app_version_matches_pyproject_toml(self):
        """APP_VERSION must be read from pyproject.toml, not a hardcoded string."""
        with open(Path(__file__).parent.parent / "pyproject.toml", "rb") as f:
            expected = tomllib.load(f)["project"]["version"]
        from version import APP_VERSION

        assert APP_VERSION == expected


class TestHealth:
    async def test_health_returns_ok(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


class TestVersionEndpoint:
    async def test_version_fields_present(self, client):
        resp = await client.get("/api/version")
        assert resp.status_code == 200
        data = resp.json()
        assert "version" in data
        assert "api_version" in data
        assert "git_hash" in data
        assert "build_time" in data

    async def test_api_version_is_v1(self, client):
        resp = await client.get("/api/version")
        assert resp.json()["api_version"] == "v1"

    async def test_app_version_is_semver(self, client):
        resp = await client.get("/api/version")
        version = resp.json()["version"]
        parts = version.split(".")
        assert len(parts) == 3
        assert all(p.isdigit() for p in parts)


class TestCompatRedirectMiddleware:
    async def test_old_notifications_path_redirects_308(self, client, viewer_session_headers):
        """Old /api/notifications must 308-redirect to /api/v1/notifications."""
        resp = await client.get(
            "/api/notifications",
            headers=viewer_session_headers,
            follow_redirects=False,
        )
        assert resp.status_code == 308
        assert resp.headers["location"] == "/api/v1/notifications"

    async def test_old_shoutrrr_path_redirects_308(self, client, access_token):
        """Old /api/shoutrrr must 308-redirect to /api/v1/shoutrrr."""
        raw, _ = access_token
        resp = await client.post(
            "/api/shoutrrr",
            headers={"Authorization": f"Bearer {raw}"},
            follow_redirects=False,
        )
        assert resp.status_code == 308
        assert resp.headers["location"] == "/api/v1/shoutrrr"

    async def test_redirect_preserves_query_string(self, client):
        resp = await client.get(
            "/api/notifications?page=2&q=test",
            follow_redirects=False,
        )
        assert resp.status_code == 308
        location = resp.headers["location"]
        assert location == "/api/v1/notifications?page=2&q=test"

    async def test_health_not_redirected(self, client):
        """Unversioned endpoints must pass through without redirect."""
        resp = await client.get("/api/health", follow_redirects=False)
        assert resp.status_code == 200

    async def test_versioned_path_not_double_redirected(self, client, viewer_session_headers):
        """Already-versioned paths must never trigger the middleware."""
        resp = await client.get(
            "/api/v1/notifications",
            headers=viewer_session_headers,
            follow_redirects=False,
        )
        # Should NOT be a redirect
        assert resp.status_code != 308
