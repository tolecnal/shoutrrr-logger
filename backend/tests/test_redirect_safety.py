"""
Tests for the OIDC login flow security controls:

- `/api/auth/login` validates `redirect_after` against
  `_SAFE_REDIRECT_PATH_RE` and embeds it in a signed `state` JWT alongside a
  CSRF nonce (mirrored in the `oidc_nonce` cookie) and an expiry. It also
  starts a PKCE S256 exchange, storing the verifier in the
  `oidc_pkce_verifier` cookie.

- `/api/auth/callback` verifies the state signature, requires the state nonce
  to match the browser's `oidc_nonce` cookie (login-CSRF protection), passes
  the PKCE verifier to the token exchange, re-validates the redirect target,
  and redirects there after completing the login.
"""

import urllib.parse
from datetime import UTC, datetime, timedelta

import pytest

from config import settings
from main import _SAFE_REDIRECT_PATH_RE

_DISCOVERY_URL = "https://idp.example.com/.well-known/openid-configuration"


# ---------------------------------------------------------------------------
# _SAFE_REDIRECT_PATH_RE
# ---------------------------------------------------------------------------


class TestSafeRedirectPathRegex:
    def test_allows_plain_relative_path(self):
        assert _SAFE_REDIRECT_PATH_RE.fullmatch("/log")

    def test_allows_nested_relative_path(self):
        assert _SAFE_REDIRECT_PATH_RE.fullmatch("/admin/users")

    def test_allows_root_path(self):
        assert _SAFE_REDIRECT_PATH_RE.fullmatch("/")

    def test_rejects_protocol_relative_url(self):
        assert not _SAFE_REDIRECT_PATH_RE.fullmatch("//evil.com")

    def test_rejects_backslash_variant(self):
        assert not _SAFE_REDIRECT_PATH_RE.fullmatch("/\\evil.com")

    def test_rejects_absolute_url(self):
        assert not _SAFE_REDIRECT_PATH_RE.fullmatch("https://evil.com")

    def test_rejects_path_without_leading_slash(self):
        assert not _SAFE_REDIRECT_PATH_RE.fullmatch("evil.com")

    def test_rejects_tab_smuggled_protocol_relative_url(self):
        # Browsers strip ASCII control characters (tab, CR, LF, ...) per the
        # WHATWG URL spec, so "/\t/evil.com" would otherwise be interpreted
        # as "//evil.com" — a protocol-relative redirect to evil.com.
        assert not _SAFE_REDIRECT_PATH_RE.fullmatch("/\t/evil.com")

    def test_rejects_newline_smuggled_protocol_relative_url(self):
        assert not _SAFE_REDIRECT_PATH_RE.fullmatch("/\n/evil.com")

    def test_rejects_carriage_return_smuggled_protocol_relative_url(self):
        assert not _SAFE_REDIRECT_PATH_RE.fullmatch("/\r/evil.com")


# ---------------------------------------------------------------------------
# /api/auth/login — redirect_after is stored in the OIDC state param
# ---------------------------------------------------------------------------


class TestOidcLoginRedirectAfter:
    @pytest.fixture(autouse=True)
    def _discovery(self, httpx_mock, monkeypatch):
        import auth as auth_module

        monkeypatch.setattr(auth_module, "_oidc_config", None)
        monkeypatch.setattr(settings, "oidc_discovery_url", _DISCOVERY_URL)
        httpx_mock.add_response(
            url=_DISCOVERY_URL,
            json={
                "issuer": "https://idp.example.com",
                "jwks_uri": "https://idp.example.com/jwks",
                "authorization_endpoint": "https://idp.example.com/auth",
                "token_endpoint": "https://idp.example.com/token",
                "userinfo_endpoint": "https://idp.example.com/userinfo",
            },
        )

    def _state_payload(self, resp) -> dict:
        import jwt

        url = resp.headers["location"]
        query = urllib.parse.urlparse(url).query
        params = urllib.parse.parse_qs(query)
        state_jwt = params["state"][0]
        return jwt.decode(state_jwt, settings.secret_key, algorithms=["HS256"])

    def _redirect_from_state(self, resp) -> str:
        return self._state_payload(resp).get("redirect", "/log")

    async def test_safe_redirect_after_is_stored_in_state(self, client):
        resp = await client.get(
            "/api/auth/login", params={"redirect_after": "/admin/users"}, follow_redirects=False
        )
        assert self._redirect_from_state(resp) == "/admin/users"

    async def test_state_nonce_matches_nonce_cookie(self, client):
        resp = await client.get("/api/auth/login", follow_redirects=False)
        assert self._state_payload(resp)["nonce"] == resp.cookies.get("oidc_nonce")

    async def test_pkce_challenge_matches_verifier_cookie(self, client):
        import base64
        import hashlib

        resp = await client.get("/api/auth/login", follow_redirects=False)
        query = urllib.parse.urlparse(resp.headers["location"]).query
        params = urllib.parse.parse_qs(query)
        assert params["code_challenge_method"] == ["S256"]
        verifier = resp.cookies.get("oidc_pkce_verifier")
        expected = (
            base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
            .rstrip(b"=")
            .decode()
        )
        assert params["code_challenge"] == [expected]

    async def test_protocol_relative_redirect_after_falls_back_to_log(self, client):
        resp = await client.get(
            "/api/auth/login", params={"redirect_after": "//evil.com"}, follow_redirects=False
        )
        assert self._redirect_from_state(resp) == "/log"

    async def test_tab_smuggled_redirect_after_falls_back_to_log(self, client):
        resp = await client.get(
            "/api/auth/login", params={"redirect_after": "/\t/evil.com"}, follow_redirects=False
        )
        assert self._redirect_from_state(resp) == "/log"


# ---------------------------------------------------------------------------
# /api/auth/callback — redirects based on the OIDC state param
# ---------------------------------------------------------------------------


_NONCE = "test-nonce-value"
_VERIFIER = "test-pkce-verifier"
_FLOW_COOKIES = {"oidc_nonce": _NONCE, "oidc_pkce_verifier": _VERIFIER}


class TestOidcCallbackRedirectState:
    @pytest.fixture(autouse=True)
    def _mock_oidc_exchange(self, monkeypatch):
        import main as main_module

        async def fake_exchange_code_for_tokens(code, redirect_uri, code_verifier):
            assert code_verifier == _VERIFIER
            return {"access_token": "fake-access-token"}

        async def fake_get_userinfo(access_token):
            return {
                "sub": "test-user-sub",
                "email": "user@example.com",
                "preferred_username": "testuser",
                "realm_access": {"roles": ["viewer"]},
            }

        async def fake_verify_oidc_jwt(access_token):
            return {}

        monkeypatch.setattr(main_module, "exchange_code_for_tokens", fake_exchange_code_for_tokens)
        monkeypatch.setattr(main_module, "get_userinfo", fake_get_userinfo)
        monkeypatch.setattr(main_module, "verify_oidc_jwt", fake_verify_oidc_jwt)

    def _create_state(self, redirect_after: str, nonce: str = _NONCE) -> str:
        import jwt

        state_payload = {"nonce": nonce, "redirect": redirect_after}
        return jwt.encode(state_payload, settings.secret_key, algorithm="HS256")

    async def test_redirect_state_is_honored(self, client):
        state = self._create_state("/admin/users")
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123", "state": state},
            cookies=_FLOW_COOKIES,
            follow_redirects=False,
        )
        assert resp.headers["location"] == "/admin/users"

    async def test_flow_cookies_are_cleared_after_login(self, client):
        state = self._create_state("/log")
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123", "state": state},
            cookies=_FLOW_COOKIES,
            follow_redirects=False,
        )
        cleared = {
            h.split("=", 1)[0] for h in resp.headers.get_list("set-cookie") if "Max-Age=0" in h
        }
        assert {"oidc_nonce", "oidc_pkce_verifier"} <= cleared

    async def test_protocol_relative_redirect_state_falls_back_to_log(self, client):
        state = self._create_state("//evil.com")
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123", "state": state},
            cookies=_FLOW_COOKIES,
            follow_redirects=False,
        )
        assert resp.headers["location"] == "/log"

    async def test_missing_state_is_rejected(self, client):
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123"},
            cookies=_FLOW_COOKIES,
            follow_redirects=False,
        )
        assert resp.status_code == 400

    async def test_unsigned_state_is_rejected(self, client):
        import jwt

        forged = jwt.encode(
            {"nonce": _NONCE, "redirect": "/log"}, "wrong-secret", algorithm="HS256"
        )
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123", "state": forged},
            cookies=_FLOW_COOKIES,
            follow_redirects=False,
        )
        assert resp.status_code == 400

    async def test_nonce_mismatch_is_rejected(self, client):
        # A valid, server-signed state from a *different* browser session
        # (attacker's own login) must not complete the login here.
        state = self._create_state("/log", nonce="attacker-session-nonce")
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123", "state": state},
            cookies=_FLOW_COOKIES,
            follow_redirects=False,
        )
        assert resp.status_code == 400

    async def test_missing_nonce_cookie_is_rejected(self, client):
        state = self._create_state("/log")
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123", "state": state},
            cookies={"oidc_pkce_verifier": _VERIFIER},
            follow_redirects=False,
        )
        assert resp.status_code == 400

    async def test_missing_pkce_cookie_is_rejected(self, client):
        state = self._create_state("/log")
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123", "state": state},
            cookies={"oidc_nonce": _NONCE},
            follow_redirects=False,
        )
        assert resp.status_code == 400

    async def test_expired_state_is_rejected(self, client):
        import jwt

        expired = jwt.encode(
            {
                "nonce": _NONCE,
                "redirect": "/log",
                "exp": datetime.now(UTC) - timedelta(minutes=1),
            },
            settings.secret_key,
            algorithm="HS256",
        )
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123", "state": expired},
            cookies=_FLOW_COOKIES,
            follow_redirects=False,
        )
        assert resp.status_code == 400
