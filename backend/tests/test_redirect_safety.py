"""
Tests for `_safe_redirect_path`, which validates the post-login redirect
target passed through the OIDC `state` parameter (and the `redirect_after`
query parameter on `/api/auth/login`).
"""

from main import _safe_redirect_path


class TestSafeRedirectPath:
    def test_allows_plain_relative_path(self):
        assert _safe_redirect_path("/log") == "/log"

    def test_allows_nested_relative_path(self):
        assert _safe_redirect_path("/admin/users") == "/admin/users"

    def test_rejects_protocol_relative_url(self):
        assert _safe_redirect_path("//evil.com") == "/log"

    def test_rejects_backslash_variant(self):
        assert _safe_redirect_path("/\\evil.com") == "/log"

    def test_rejects_absolute_url(self):
        assert _safe_redirect_path("https://evil.com") == "/log"

    def test_rejects_path_without_leading_slash(self):
        assert _safe_redirect_path("evil.com") == "/log"

    def test_rejects_tab_smuggled_protocol_relative_url(self):
        # Browsers strip ASCII control characters (tab, CR, LF, ...) per the
        # WHATWG URL spec, so "/\t/evil.com" would otherwise be interpreted
        # as "//evil.com" — a protocol-relative redirect to evil.com.
        assert _safe_redirect_path("/\t/evil.com") == "/log"

    def test_rejects_newline_smuggled_protocol_relative_url(self):
        assert _safe_redirect_path("/\n/evil.com") == "/log"

    def test_rejects_carriage_return_smuggled_protocol_relative_url(self):
        assert _safe_redirect_path("/\r/evil.com") == "/log"

    def test_custom_default_is_used_for_unsafe_input(self):
        assert _safe_redirect_path("//evil.com", default="/fallback") == "/fallback"
