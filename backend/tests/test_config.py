"""Tests for production secret validation in `config.Settings`."""

import pytest

from config import Settings

_VALID_KEY = "a" * 64  # what `openssl rand -hex 32` produces


def _settings(**overrides) -> Settings:
    base = {
        "environment": "production",
        "secret_key": _VALID_KEY,
        "oidc_client_secret": "client-secret",
        # Keep pydantic-settings from picking up the developer's .env file.
        "_env_file": None,
    }
    return Settings(**{**base, **overrides})


class TestProductionSecretValidation:
    def test_valid_production_settings_pass(self):
        assert _settings().secret_key == _VALID_KEY

    def test_default_secret_key_is_rejected(self):
        with pytest.raises(ValueError, match="changed from the default"):
            _settings(secret_key="change-me-in-production")

    def test_short_secret_key_is_rejected(self):
        with pytest.raises(ValueError, match="at least 32 characters"):
            _settings(secret_key="too-short")

    def test_missing_oidc_client_secret_is_rejected(self):
        with pytest.raises(ValueError, match="OIDC_CLIENT_SECRET"):
            _settings(oidc_client_secret="")

    def test_non_production_skips_strict_checks(self):
        s = _settings(environment="test", secret_key="short", oidc_client_secret="")
        assert s.secret_key == "short"
