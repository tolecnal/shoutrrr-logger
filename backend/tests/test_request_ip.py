"""
Tests for `utils.request_ip.get_client_ip`.

The client-supplied left-most X-Forwarded-For entry must never win: behind
the bundled nginx, X-Real-IP (overwritten by nginx) or the right-most XFF
hop (appended by nginx) is authoritative.
"""

from types import SimpleNamespace

from utils.request_ip import get_client_ip


def _request(headers: dict[str, str] | None = None, peer: str | None = "10.0.0.9"):
    return SimpleNamespace(
        headers=headers or {},
        client=SimpleNamespace(host=peer) if peer else None,
    )


def test_x_real_ip_takes_precedence():
    req = _request({"X-Real-IP": "203.0.113.7", "X-Forwarded-For": "6.6.6.6, 203.0.113.7"})
    assert get_client_ip(req) == "203.0.113.7"


def test_spoofed_left_xff_entry_is_ignored():
    # Client sent "X-Forwarded-For: 6.6.6.6"; nginx appended the real peer.
    req = _request({"X-Forwarded-For": "6.6.6.6, 198.51.100.2"})
    assert get_client_ip(req) == "198.51.100.2"


def test_single_xff_entry_is_used():
    req = _request({"X-Forwarded-For": "198.51.100.2"})
    assert get_client_ip(req) == "198.51.100.2"


def test_falls_back_to_socket_peer():
    assert get_client_ip(_request()) == "10.0.0.9"


def test_no_client_returns_none():
    assert get_client_ip(_request(peer=None)) is None
