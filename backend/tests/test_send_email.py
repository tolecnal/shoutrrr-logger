"""
Tests for `services.trigger_engine.send_email_async` TLS behavior.

Credentials must never be sent over an unencrypted connection: if the SMTP
server does not advertise STARTTLS and credentials are configured, the send
is refused rather than silently downgrading to plaintext auth.
"""

import smtplib
from unittest.mock import MagicMock, patch

import pytest

from services.trigger_engine import send_email_async


def _smtp_server_mock(*, supports_starttls: bool) -> MagicMock:
    server = MagicMock()
    server.has_extn.side_effect = lambda ext: supports_starttls and ext == "starttls"
    cm = MagicMock()
    cm.__enter__.return_value = server
    cm.__exit__.return_value = False
    return server, cm


async def test_starttls_is_used_when_advertised():
    server, cm = _smtp_server_mock(supports_starttls=True)
    with patch("services.trigger_engine.smtplib.SMTP", return_value=cm):
        await send_email_async(
            host="smtp.example.com",
            port=587,
            user="alerts",
            password="hunter2",
            from_addr="alerts@example.com",
            to_addr="user@example.com",
            subject="s",
            body="b",
            raise_errors=True,
        )
    server.starttls.assert_called_once()
    server.login.assert_called_once_with("alerts", "hunter2")
    server.send_message.assert_called_once()


async def test_credentials_refused_without_starttls():
    server, cm = _smtp_server_mock(supports_starttls=False)
    with (
        patch("services.trigger_engine.smtplib.SMTP", return_value=cm),
        pytest.raises(smtplib.SMTPException, match="refusing to send credentials"),
    ):
        await send_email_async(
            host="smtp.example.com",
            port=587,
            user="alerts",
            password="hunter2",
            from_addr="alerts@example.com",
            to_addr="user@example.com",
            subject="s",
            body="b",
            raise_errors=True,
        )
    server.starttls.assert_not_called()
    server.login.assert_not_called()
    server.send_message.assert_not_called()


async def test_plaintext_allowed_without_credentials():
    """Unauthenticated internal relays without TLS keep working (with a warning)."""
    server, cm = _smtp_server_mock(supports_starttls=False)
    with patch("services.trigger_engine.smtplib.SMTP", return_value=cm):
        await send_email_async(
            host="relay.internal",
            port=25,
            user="",
            password="",
            from_addr="alerts@example.com",
            to_addr="user@example.com",
            subject="s",
            body="b",
            raise_errors=True,
        )
    server.starttls.assert_not_called()
    server.login.assert_not_called()
    server.send_message.assert_called_once()


async def test_implicit_tls_on_port_465():
    server, cm = _smtp_server_mock(supports_starttls=False)
    with patch("services.trigger_engine.smtplib.SMTP_SSL", return_value=cm) as smtp_ssl:
        await send_email_async(
            host="smtp.example.com",
            port=465,
            user="alerts",
            password="hunter2",
            from_addr="alerts@example.com",
            to_addr="user@example.com",
            subject="s",
            body="b",
            raise_errors=True,
        )
    assert smtp_ssl.call_args.kwargs.get("context") is not None
    server.login.assert_called_once_with("alerts", "hunter2")
    server.send_message.assert_called_once()
