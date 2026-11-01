"""SSRF protection for user-registered agent endpoints."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from app.core.config import get_settings


class EndpointValidationError(ValueError):
    pass


def validate_endpoint(url: str) -> str:
    """Validate a user-supplied agent endpoint.

    Returns the normalized URL or raises EndpointValidationError. Blocks
    non-HTTP schemes and (unless allow_local_endpoints) private/loopback
    hosts to prevent SSRF against internal infrastructure.
    """
    settings = get_settings()
    parsed = urlparse(url.strip())

    if parsed.scheme not in ("http", "https"):
        raise EndpointValidationError("Endpoint must use http:// or https://")
    if not parsed.hostname:
        raise EndpointValidationError("Endpoint has no hostname")

    if not settings.allow_local_endpoints:
        try:
            infos = socket.getaddrinfo(parsed.hostname, parsed.port or None)
        except socket.gaierror as exc:
            raise EndpointValidationError(f"Cannot resolve host: {parsed.hostname}") from exc
        for info in infos:
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
            ):
                raise EndpointValidationError(
                    "Private/loopback endpoints are not allowed (set ALLOW_LOCAL_ENDPOINTS=true for local development)"
                )

    return url.strip()
