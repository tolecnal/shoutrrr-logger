"""
Tests for the post-login redirect target validation used by
`/api/auth/login` (`redirect_after`) and `/api/auth/callback`.

`/api/auth/login` validates `redirect_after` against
`_SAFE_REDIRECT_PATH_RE` and stores it in a short-lived `oidc_redirect`
cookie (falling back to "/log" for anything unsafe). The OIDC `state`
param is an opaque CSRF nonce, decoupled from user-controlled input.

`/api/auth/callback` reads that cookie, re-validates it the same way, and
redirects there after completing the login — clearing the cookie.
"""

import urllib.parse

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
# /api/auth/login — redirect_after is stored in the oidc_redirect cookie
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

    def _redirect_cookie(self, resp) -> str:
        # The cookie value is percent-encoded; SimpleCookie may also quote it.
        raw = (resp.cookies.get("oidc_redirect") or "").strip('"')
        return urllib.parse.unquote(raw)

    async def test_safe_redirect_after_is_stored_in_cookie(self, client):
        resp = await client.get(
            "/api/auth/login", params={"redirect_after": "/admin/users"}, follow_redirects=False
        )
        assert self._redirect_cookie(resp) == "/admin/users"

    async def test_protocol_relative_redirect_after_falls_back_to_log(self, client):
        resp = await client.get(
            "/api/auth/login", params={"redirect_after": "//evil.com"}, follow_redirects=False
        )
        assert self._redirect_cookie(resp) == "/log"

    async def test_tab_smuggled_redirect_after_falls_back_to_log(self, client):
        resp = await client.get(
            "/api/auth/login", params={"redirect_after": "/\t/evil.com"}, follow_redirects=False
        )
        assert self._redirect_cookie(resp) == "/log"


# ---------------------------------------------------------------------------
# /api/auth/callback — redirects based on the oidc_redirect cookie
# ---------------------------------------------------------------------------


class TestOidcCallbackRedirectCookie:
    @pytest.fixture(autouse=True)
    def _mock_oidc_exchange(self, monkeypatch):
        import main as main_module

        async def fake_exchange_code_for_tokens(code, redirect_uri):
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

    async def test_redirect_cookie_is_honored_and_cleared(self, client):
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123"},
            cookies={"oidc_redirect": urllib.parse.quote("/admin/users", safe="")},
            follow_redirects=False,
        )
        assert resp.headers["location"] == "/admin/users"
        cleared = [h for h in resp.headers.get_list("set-cookie") if h.startswith("oidc_redirect=")]
        assert cleared and "Max-Age=0" in cleared[0]

    async def test_protocol_relative_redirect_cookie_falls_back_to_log(self, client):
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123"},
            cookies={"oidc_redirect": urllib.parse.quote("//evil.com", safe="")},
            follow_redirects=False,
        )
        assert resp.headers["location"] == "/log"

    async def test_missing_redirect_cookie_falls_back_to_log(self, client):
        resp = await client.get(
            "/api/auth/callback",
            params={"code": "abc123"},
            follow_redirects=False,
        )
        assert resp.headers["location"] == "/log"
