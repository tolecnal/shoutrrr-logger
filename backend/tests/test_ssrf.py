"""Tests for utils.ssrf.validate_url_for_ssrf and its disable flag.

The full test suite runs with SSRF_VALIDATION_DISABLED=true (set in
conftest.py) so that plugin dispatch tests can target loopback addresses.
These tests temporarily flip `settings.ssrf_validation_disabled` to exercise
the actual validation logic, and confirm the bypass is gated on a dedicated
flag rather than `ENVIRONMENT`.
"""

import pytest

from config import settings
from utils.ssrf import validate_url_for_ssrf


@pytest.fixture
def ssrf_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ssrf_validation_disabled", False)


def test_loopback_url_rejected(ssrf_enabled):
    with pytest.raises(ValueError, match="restricted IP address"):
        validate_url_for_ssrf("http://127.0.0.1:8080/webhook")


def test_private_ip_url_rejected(ssrf_enabled):
    with pytest.raises(ValueError, match="restricted IP address"):
        validate_url_for_ssrf("http://10.0.0.5/webhook")


def test_link_local_metadata_url_rejected(ssrf_enabled):
    with pytest.raises(ValueError, match="restricted IP address"):
        validate_url_for_ssrf("http://169.254.169.254/latest/meta-data/")


def test_public_ip_url_allowed(ssrf_enabled):
    validate_url_for_ssrf("http://8.8.8.8/webhook")


def test_disabled_flag_skips_validation(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ssrf_validation_disabled", True)
    with caplog.at_level("WARNING"):
        validate_url_for_ssrf("http://127.0.0.1:8080/webhook")
    assert "SSRF validation is DISABLED" in caplog.text
