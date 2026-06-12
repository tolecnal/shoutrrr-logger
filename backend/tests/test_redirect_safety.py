"""
Tests for the post-login redirect target validation used by
`/api/auth/login` (`redirect_after`) and `/api/auth/callback` (`state`).

Both endpoints validate the user-supplied path against
`_SAFE_REDIRECT_PATH_RE`, falling back to "/log" for anything unsafe.
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
# /api/auth/login — redirect_after is echoed back as the OIDC `state` param
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

    def _state_from_location(self, location: str) -> str:
        query = urllib.parse.urlparse(location).query
        return urllib.parse.parse_qs(query)["state"][0]

    async def test_safe_redirect_after_is_preserved(self, client):
        resp = await client.get(
            "/api/auth/login", params={"redirect_after": "/admin/users"}, follow_redirects=False
        )
        assert self._state_from_location(resp.headers["location"]) == "/admin/users"

    async def test_protocol_relative_redirect_after_falls_back_to_log(self, client):
        resp = await client.get(
            "/api/auth/login", params={"redirect_after": "//evil.com"}, follow_redirects=False
        )
        assert self._state_from_location(resp.headers["location"]) == "/log"

    async def test_tab_smuggled_redirect_after_falls_back_to_log(self, client):
        resp = await client.get(
            "/api/auth/login", params={"redirect_after": "/\t/evil.com"}, follow_redirects=False
        )
        assert self._state_from_location(resp.headers["location"]) == "/log"
