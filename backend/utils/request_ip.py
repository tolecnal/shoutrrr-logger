"""Client IP extraction that resists X-Forwarded-For spoofing.

The bundled nginx reverse proxy sets:

    proxy_set_header X-Real-IP       $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

``X-Real-IP`` is overwritten by nginx with the actual peer address, so it
cannot be influenced by the client. ``X-Forwarded-For`` is *appended to*:
a client sending ``X-Forwarded-For: 1.2.3.4`` arrives as
``1.2.3.4, <real-ip>`` — so the left-most entry is attacker-controlled and
only the right-most entry (the hop added by our own proxy) is trustworthy.
"""

from fastapi import Request


def get_client_ip(request: Request) -> str | None:
    """Best-effort real client IP for logging/audit purposes.

    Precedence: ``X-Real-IP`` (authoritative from our nginx) → right-most
    ``X-Forwarded-For`` entry → socket peer address.
    """
    real_ip = request.headers.get("X-Real-IP", "").strip()
    if real_ip:
        return real_ip

    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        last_hop = forwarded_for.rsplit(",", 1)[-1].strip()
        if last_hop:
            return last_hop

    return request.client.host if request.client else None
