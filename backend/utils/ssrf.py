import ipaddress
import logging
import socket
from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

import anyio
import httpcore
import httpx

from config import settings

logger = logging.getLogger(__name__)


def _is_restricted_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Returns True if `ip` must not be reachable from outbound plugin requests."""
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or str(ip) == "0.0.0.0"
    )


def _resolve_addresses(hostname: str) -> list[str]:
    """Resolve `hostname` to a list of IP address strings via getaddrinfo.

    Raises socket.gaierror if resolution fails.
    """
    addresses = socket.getaddrinfo(hostname, None)
    ip_strs = []
    for addr in addresses:
        ip_str = addr[4][0]
        try:
            ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        ip_strs.append(ip_str)
    return ip_strs


def validate_url_for_ssrf(url: str) -> None:
    """
    Validates a URL to prevent Server-Side Request Forgery (SSRF).
    Raises ValueError if the URL points to a local, private, or reserved IP address.
    """
    if settings.ssrf_validation_disabled:
        logger.warning(
            "SSRF validation is DISABLED (SSRF_VALIDATION_DISABLED=true) - "
            "skipping outbound URL check for %s",
            url,
        )
        return

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: missing hostname")

    try:
        ip_strs = _resolve_addresses(hostname)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve hostname {hostname}: {e}") from e

    for ip_str in ip_strs:
        if _is_restricted_ip(ipaddress.ip_address(ip_str)):
            raise ValueError(f"URL resolves to a restricted IP address: {ip_str}")


def _resolve_and_pin(hostname: str) -> str:
    """Resolve `hostname`, validate every candidate address against the SSRF
    denylist, and return a single pinned IP literal to connect to.

    Raises httpcore.ConnectError if resolution fails or any candidate
    address is restricted.
    """
    try:
        ip_strs = _resolve_addresses(hostname)
    except socket.gaierror as e:
        raise httpcore.ConnectError(f"Could not resolve hostname {hostname}: {e}") from e

    if not ip_strs:
        raise httpcore.ConnectError(f"Could not resolve hostname {hostname} to an IP address")

    for ip_str in ip_strs:
        if _is_restricted_ip(ipaddress.ip_address(ip_str)):
            raise httpcore.ConnectError(
                f"Connection to {hostname} blocked by SSRF policy: "
                f"resolves to restricted IP address {ip_str}"
            )

    # All candidates passed; pin to the first one so the address used for
    # validation is the same one the socket actually connects to.
    return ip_strs[0]


class SSRFSafeAsyncNetworkBackend(httpcore.AnyIOBackend):
    """An AnyIOBackend that resolves+validates the hostname at connect time
    and connects to a pinned IP literal.

    `validate_url_for_ssrf` is called when a webhook/HEC URL is configured,
    but httpx/httpcore re-resolve the hostname independently when the actual
    request is made later. Between those two lookups, an attacker controlling
    DNS for the configured hostname could return a public IP for validation
    and a private/loopback IP for the real connection (DNS rebinding/TOCTOU).
    Resolving and validating here, at the point the socket is opened, closes
    that gap.

    TLS verification is unaffected: httpcore performs SNI/certificate checks
    against the original hostname (`server_hostname`) in a separate step,
    independent of which IP address this socket connects to.
    """

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if settings.ssrf_validation_disabled:
            return await super().connect_tcp(
                host,
                port,
                timeout=timeout,
                local_address=local_address,
                socket_options=socket_options,
            )

        pinned_ip = await anyio.to_thread.run_sync(_resolve_and_pin, host)
        return await super().connect_tcp(
            pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


def create_ssrf_safe_async_client(
    *, verify: str | bool = True, **client_kwargs: Any
) -> httpx.AsyncClient:
    """Build an httpx.AsyncClient that re-validates the destination address
    against the SSRF denylist at connect time, using a pinned IP for the
    actual connection (see SSRFSafeAsyncNetworkBackend).

    `verify` is applied to the underlying transport. Any other kwargs
    accepted by httpx.AsyncClient (timeout, follow_redirects, headers, etc.)
    are forwarded as-is.
    """
    transport = httpx.AsyncHTTPTransport(verify=verify)
    transport._pool._network_backend = SSRFSafeAsyncNetworkBackend()
    return httpx.AsyncClient(transport=transport, **client_kwargs)
