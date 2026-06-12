"""Tests for utils.ssrf.validate_url_for_ssrf and its disable flag.

The full test suite runs with SSRF_VALIDATION_DISABLED=true (set in
conftest.py) so that plugin dispatch tests can target loopback addresses.
These tests temporarily flip `settings.ssrf_validation_disabled` to exercise
the actual validation logic, and confirm the bypass is gated on a dedicated
flag rather than `ENVIRONMENT`.
"""

import socket

import httpcore
import httpx
import pytest

from config import settings
from utils.ssrf import (
    SSRFSafeAsyncNetworkBackend,
    _resolve_and_pin,
    create_ssrf_safe_async_client,
    validate_url_for_ssrf,
)


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


def test_whitelisted_hostname_allowed(ssrf_enabled, monkeypatch):
    monkeypatch.setattr(settings, "ssrf_allowed_hostnames", "internal.corp,vm-splunk01.xiro.net")
    # Even if it resolves to loopback/private, validation passes
    monkeypatch.setattr("utils.ssrf.socket.getaddrinfo", _fake_getaddrinfo("192.168.1.1"))
    validate_url_for_ssrf("http://vm-splunk01.xiro.net/webhook")


def test_whitelisted_ip_allowed(ssrf_enabled, monkeypatch):
    monkeypatch.setattr(settings, "ssrf_allowed_hostnames", "10.0.0.5")
    validate_url_for_ssrf("http://10.0.0.5/webhook")


def test_disabled_flag_skips_validation(monkeypatch, caplog):
    monkeypatch.setattr(settings, "ssrf_validation_disabled", True)
    with caplog.at_level("WARNING"):
        validate_url_for_ssrf("http://127.0.0.1:8080/webhook")
    assert "SSRF validation is DISABLED" in caplog.text


def _fake_getaddrinfo(ip_str: str):
    """Build a getaddrinfo()-shaped return value resolving to a single IP."""

    def _resolve(host, port):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip_str, 0))]

    return _resolve


class TestResolveAndPin:
    """`_resolve_and_pin` is the connect-time check used by
    SSRFSafeAsyncNetworkBackend to close the TOCTOU/DNS-rebinding gap."""

    def test_public_ip_is_pinned(self, ssrf_enabled, monkeypatch):
        monkeypatch.setattr("utils.ssrf.socket.getaddrinfo", _fake_getaddrinfo("8.8.8.8"))
        assert _resolve_and_pin("example.com") == "8.8.8.8"

    def test_private_ip_is_blocked(self, ssrf_enabled, monkeypatch):
        monkeypatch.setattr("utils.ssrf.socket.getaddrinfo", _fake_getaddrinfo("10.0.0.5"))
        with pytest.raises(httpcore.ConnectError, match="restricted IP address"):
            _resolve_and_pin("attacker.example.com")

    def test_loopback_ip_is_blocked(self, ssrf_enabled, monkeypatch):
        monkeypatch.setattr("utils.ssrf.socket.getaddrinfo", _fake_getaddrinfo("127.0.0.1"))
        with pytest.raises(httpcore.ConnectError, match="restricted IP address"):
            _resolve_and_pin("attacker.example.com")

    def test_whitelisted_host_is_pinned_even_if_restricted(self, ssrf_enabled, monkeypatch):
        monkeypatch.setattr(settings, "ssrf_allowed_hostnames", "splunk.local")
        monkeypatch.setattr("utils.ssrf.socket.getaddrinfo", _fake_getaddrinfo("192.168.1.1"))
        assert _resolve_and_pin("splunk.local") == "192.168.1.1"

    def test_resolution_failure_raises_connect_error(self, ssrf_enabled, monkeypatch):
        def _raise(host, port):
            raise socket.gaierror("Name or service not known")

        monkeypatch.setattr("utils.ssrf.socket.getaddrinfo", _raise)
        with pytest.raises(httpcore.ConnectError, match="Could not resolve"):
            _resolve_and_pin("nonexistent.invalid")


class TestSSRFSafeAsyncNetworkBackend:
    async def test_connects_to_pinned_ip_not_hostname(self, ssrf_enabled, monkeypatch):
        monkeypatch.setattr("utils.ssrf.socket.getaddrinfo", _fake_getaddrinfo("8.8.8.8"))

        captured = {}

        async def fake_connect_tcp(self, host, port, **kwargs):
            captured["host"] = host
            captured["port"] = port
            return "fake-stream"

        monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", fake_connect_tcp)

        backend = SSRFSafeAsyncNetworkBackend()
        result = await backend.connect_tcp("example.com", 443)

        assert result == "fake-stream"
        assert captured["host"] == "8.8.8.8"
        assert captured["port"] == 443

    async def test_passthrough_when_validation_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "ssrf_validation_disabled", True)

        def _boom(*args, **kwargs):
            raise AssertionError("getaddrinfo should not be called when disabled")

        monkeypatch.setattr("utils.ssrf.socket.getaddrinfo", _boom)

        captured = {}

        async def fake_connect_tcp(self, host, port, **kwargs):
            captured["host"] = host
            return "fake-stream"

        monkeypatch.setattr(httpcore.AnyIOBackend, "connect_tcp", fake_connect_tcp)

        backend = SSRFSafeAsyncNetworkBackend()
        result = await backend.connect_tcp("example.com", 443)

        assert result == "fake-stream"
        assert captured["host"] == "example.com"


class TestCreateSSRFSafeAsyncClient:
    """End-to-end: the client's connection attempt is blocked even if a
    prior validate_url_for_ssrf() call against the same hostname passed,
    simulating DNS rebinding."""

    async def test_blocks_dns_rebind_to_private_ip(self, ssrf_enabled, monkeypatch):
        # Pretend the configured webhook hostname now resolves to a private
        # IP at connection time (e.g. an attacker updated their DNS record
        # after passing config-time validation).
        monkeypatch.setattr("utils.ssrf.socket.getaddrinfo", _fake_getaddrinfo("127.0.0.1"))

        async with create_ssrf_safe_async_client(timeout=1.0) as client:
            with pytest.raises(httpx.ConnectError, match="restricted IP address"):
                await client.get("http://attacker.example/webhook")
