"""
Tests for logout (RP-initiated) and forced re-authentication on login.

Regression: logging out only cleared our own session, leaving the IdP's SSO
session alive — so the next login was silently completed as the same user,
making it impossible to switch accounts in one browser. The fix:
  - login sends prompt=login (always re-authenticate at the IdP)
  - logout returns an end_session_endpoint URL (RP-initiated logout) and
    clears the session + id_token cookies.
"""

import urllib.parse

import pytest

from config import settings

_DISCOVERY_URL = "https://idp.example.com/.well-known/openid-configuration"
_END_SESSION = "https://idp.example.com/logout"


@pytest.fixture(autouse=True)
def _discovery(httpx_mock, monkeypatch):
    import auth as auth_module

    monkeypatch.setattr(auth_module, "_oidc_config", None)
    monkeypatch.setattr(settings, "oidc_discovery_url", _DISCOVERY_URL)
    monkeypatch.setattr(settings, "app_base_url", "https://app.example.com")
    # Optional: not every test triggers OIDC discovery (e.g. the 405 check).
    httpx_mock.add_response(
        url=_DISCOVERY_URL,
        is_optional=True,
        json={
            "issuer": "https://idp.example.com",
            "jwks_uri": "https://idp.example.com/jwks",
            "authorization_endpoint": "https://idp.example.com/auth",
            "token_endpoint": "https://idp.example.com/token",
            "userinfo_endpoint": "https://idp.example.com/userinfo",
            "end_session_endpoint": _END_SESSION,
        },
    )


class TestLoginForcesReauth:
    async def test_authorize_request_sends_prompt_login(self, client):
        resp = await client.get("/api/auth/login", follow_redirects=False)
        location = resp.headers["location"]
        params = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
        assert params["prompt"] == ["login"]


class TestLogout:
    async def test_logout_requires_post(self, client):
        # GET must not be a valid logout (CSRF hardening).
        resp = await client.get("/api/auth/logout", follow_redirects=False)
        assert resp.status_code == 405

    async def test_logout_returns_rp_initiated_url_with_id_token_hint(self, client):
        resp = await client.post(
            "/api/auth/logout",
            cookies={"session": "x", "oidc_id_token": "the-id-token"},
        )
        assert resp.status_code == 200
        url = resp.json()["logout_url"]
        assert url.startswith(_END_SESSION + "?")
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        assert params["id_token_hint"] == ["the-id-token"]
        assert params["post_logout_redirect_uri"] == ["https://app.example.com/"]

    async def test_logout_uses_client_id_when_no_id_token(self, client):
        resp = await client.post("/api/auth/logout", cookies={"session": "x"})
        url = resp.json()["logout_url"]
        params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        assert "id_token_hint" not in params
        assert params["client_id"] == [settings.oidc_client_id]

    async def test_logout_clears_session_and_id_token_cookies(self, client):
        resp = await client.post(
            "/api/auth/logout",
            cookies={"session": "x", "oidc_id_token": "y"},
        )
        cleared = {
            h.split("=", 1)[0]
            for h in resp.headers.get_list("set-cookie")
            if "Max-Age=0" in h or "expires=Thu, 01 Jan 1970" in h.lower()
        }
        assert "session" in cleared
        assert "oidc_id_token" in cleared


class TestLogoutNoEndSession:
    async def test_falls_back_to_root_when_no_end_session_endpoint(self, client, monkeypatch):
        # Prime the cached OIDC config without an end_session_endpoint so
        # logout has nothing to redirect to and falls back to "/".
        import auth as auth_module

        monkeypatch.setattr(
            auth_module,
            "_oidc_config",
            {
                "issuer": "https://idp.example.com",
                "authorization_endpoint": "https://idp.example.com/auth",
                "token_endpoint": "https://idp.example.com/token",
                "userinfo_endpoint": "https://idp.example.com/userinfo",
            },
        )
        resp = await client.post("/api/auth/logout", cookies={"session": "x"})
        assert resp.status_code == 200
        assert resp.json()["logout_url"] == "/"
