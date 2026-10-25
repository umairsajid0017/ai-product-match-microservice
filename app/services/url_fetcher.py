"""
Bounded, allowlisted image fetching for URL-based embedding requests.

Only HTTPS URLs on explicitly allowed hosts are fetched. Every hop (including
redirects) is re-validated, resolved addresses must be public, and the body is
streamed with a hard byte cap before image validation.

Residual risk: the TCP connection is established by httpx after this module
resolves the hostname, so a DNS-rebinding attacker could in theory serve a
different address. The host allowlist is the primary control.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urljoin, urlparse

import httpx

from app.config import settings
from app.services.image_service import MAX_SIZE_BYTES, validate_image_bytes

READ_CHUNK_BYTES = 64 * 1024
REQUEST_TIMEOUT_SECONDS = 30.0


class UnsafeImageURL(ValueError):
    """Raised when a URL is not allowed to be fetched."""


def _validate_hostname(hostname: str | None) -> None:
    if not hostname:
        raise UnsafeImageURL("Image URL has no hostname.")

    allowed = settings.allowed_image_host_set
    if not allowed:
        raise UnsafeImageURL("URL image fetching is disabled; no allowed hosts are configured.")

    if hostname.lower().rstrip(".") not in allowed:
        raise UnsafeImageURL(f"Image host is not allowed: {hostname}")


def _validate_resolved_addresses(hostname: str) -> None:
    try:
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeImageURL(f"Image host could not be resolved: {hostname}") from exc

    for _family, _type, _proto, _canonname, sockaddr in addresses:
        ip = ipaddress.ip_address(sockaddr[0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeImageURL(f"Image host resolves to a non-public address: {ip}")


def validate_image_url(url: str) -> None:
    """Validate scheme, host allowlist and resolved addresses without fetching."""
    parsed = urlparse(url)

    if parsed.scheme != "https":
        raise UnsafeImageURL("Only https image URLs are allowed.")

    _validate_hostname(parsed.hostname)
    _validate_resolved_addresses(parsed.hostname)


def fetch_image_bytes(url: str) -> bytes:
    """Download an allowlisted image with redirect revalidation and a size cap."""
    current = url

    with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=False) as client:
        for _hop in range(settings.max_url_redirects + 1):
            validate_image_url(current)

            with client.stream("GET", current) as response:
                if response.is_redirect:
                    location = response.headers.get("location")
                    if not location:
                        raise UnsafeImageURL("Image redirect had no location.")
                    current = urljoin(str(response.url), location)
                    continue

                response.raise_for_status()

                received = 0
                chunks: list[bytes] = []
                for chunk in response.iter_bytes(READ_CHUNK_BYTES):
                    received += len(chunk)
                    if received > MAX_SIZE_BYTES:
                        raise UnsafeImageURL(
                            f"Image exceeds the maximum download size of {MAX_SIZE_BYTES} bytes."
                        )
                    chunks.append(chunk)

            image_bytes = b"".join(chunks)
            validate_image_bytes(image_bytes)
            return image_bytes

    raise UnsafeImageURL("Too many redirects while fetching the image.")
