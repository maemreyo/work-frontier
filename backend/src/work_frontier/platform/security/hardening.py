"""Deterministic browser, egress, upload, rate, and redaction controls."""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from pathlib import PurePath
from typing import Final, cast
from urllib.parse import urlsplit

_ALLOWED_UPLOAD_TYPES: Final = frozenset(
    {"application/json", "text/csv", "text/markdown", "text/plain"}
)
_SECRET_KEY_PATTERN: Final = re.compile(
    r"(?i)(authorization|password|token|secret|private[_-]?key|credential)"
)
_SECRET_VALUE_PATTERN: Final = re.compile(r"(?i)bearer\s+[a-z0-9._-]+")


class SecurityControlError(ValueError):
    """Signal a rejected security-sensitive input."""


@dataclass(frozen=True, slots=True)
class EgressPolicy:
    """HTTPS-only allowlist for server-side outbound requests."""

    allowed_hosts: frozenset[str]

    def validate(self, url: str) -> str:
        """Return a canonical allowed URL or fail closed."""
        parsed = urlsplit(url)
        host = (parsed.hostname or "").casefold()
        if parsed.scheme != "https" or not host or parsed.username or parsed.password:
            msg = "egress URL must use HTTPS without user info"
            raise SecurityControlError(msg)
        if host not in {item.casefold() for item in self.allowed_hosts}:
            msg = "egress host is not allowlisted"
            raise SecurityControlError(msg)
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and (
            address.is_private
            or address.is_loopback
            or address.is_link_local
            or address.is_multicast
            or address.is_reserved
        ):
            msg = "egress target resolves to a prohibited address class"
            raise SecurityControlError(msg)
        if parsed.port not in {None, 443}:
            msg = "egress URL must use the default TLS port"
            raise SecurityControlError(msg)
        return parsed.geturl()


def validate_upload(
    *,
    filename: str,
    content_type: str,
    size_bytes: int,
    max_size_bytes: int = 5_000_000,
) -> str:
    """Validate filename, media type, and bounded size."""
    name = PurePath(filename).name
    if name != filename or name in {"", ".", ".."} or "\x00" in filename:
        msg = "upload filename is unsafe"
        raise SecurityControlError(msg)
    if content_type not in _ALLOWED_UPLOAD_TYPES:
        msg = "upload media type is not allowlisted"
        raise SecurityControlError(msg)
    if size_bytes < 0 or size_bytes > max_size_bytes:
        msg = "upload size exceeds the configured limit"
        raise SecurityControlError(msg)
    return name


def redact(value: object) -> object:
    """Recursively redact secret-bearing keys and bearer-like values."""
    if isinstance(value, dict):
        mapping = cast("dict[object, object]", value)
        return {
            str(key): (
                "[REDACTED]" if _SECRET_KEY_PATTERN.search(str(key)) else redact(item)
            )
            for key, item in mapping.items()
        }
    if isinstance(value, list):
        items = cast("list[object]", value)
        return [redact(item) for item in items]
    if isinstance(value, tuple):
        items = cast("tuple[object, ...]", value)
        return tuple(redact(item) for item in items)
    if isinstance(value, str) and _SECRET_VALUE_PATTERN.search(value):
        return "[REDACTED]"
    return value


def require_tls_configuration(
    *,
    public_base_url: str,
    database_url: str,
    object_store_url: str,
) -> None:
    """Reject production configuration with plaintext transports."""
    if not public_base_url.startswith("https://"):
        msg = "public base URL must use HTTPS"
        raise SecurityControlError(msg)
    tls_modes = ("sslmode=require", "sslmode=verify-full")
    if not any(mode in database_url for mode in tls_modes):
        msg = "database URL must require TLS"
        raise SecurityControlError(msg)
    if not object_store_url.startswith("https://"):
        msg = "object store URL must use HTTPS"
        raise SecurityControlError(msg)
