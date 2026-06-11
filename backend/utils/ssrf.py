import ipaddress
import os
import socket
from urllib.parse import urlparse


def validate_url_for_ssrf(url: str) -> None:
    """
    Validates a URL to prevent Server-Side Request Forgery (SSRF).
    Raises ValueError if the URL points to a local, private, or reserved IP address.
    """
    if os.environ.get("ENVIRONMENT") == "test":
        return

    parsed = urlparse(url)
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: missing hostname")

    # Resolve all IPs for the hostname
    try:
        # getaddrinfo returns a list of 5-tuples: (family, type, proto, canonname, sockaddr)
        # sockaddr is a tuple like (IP, port) for IPv4 or (IP, port, flowinfo, scopeid) for IPv6
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve hostname {hostname}: {e}")

    for addr in addresses:
        ip_str = addr[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or str(ip) == "0.0.0.0"
        ):
            raise ValueError(f"URL resolves to a restricted IP address: {ip_str}")
