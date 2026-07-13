"""Deterministic browser, egress, upload, rate, and redaction controls."""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import re
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import PurePath
from types import MappingProxyType
from typing import Final, cast
from urllib.parse import urlsplit

_MIN_SECRET_BYTES: Final = 32

_ALLOWED_UPLOAD_TYPES: Final = frozenset(
    {"application/json", "text/csv", "text/markdown", "text/plain"}
)
_SECRET_KEY_PATTERN: Final = re.compile(
    r"(?i)(authorization|password|token|secret|private[_-]?key|credential)"
)
_SECRET_VALUE_PATTERN: Final = re.compile(r"(?i)bearer\s+[a-z0-9._-]+")
_SECURITY_HEADERS: Final = MappingProxyType(
    {
        "Cache-Control": "no-store",
        "Content-Security-Policy": (
            "default-src 'self'; base-uri 'none'; frame-ancestors 'none'; "
            "form-action 'self'; object-src 'none'; script-src 'self'; "
            "style-src 'self'; connect-src 'self' https://api.github.com"
        ),
        "Cross-Origin-Opener-Policy": "same-origin",
        "Cross-Origin-Resource-Policy": "same-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Referrer-Policy": "no-referrer",
        "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
    }
)


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


@dataclass(slots=True)
class SlidingWindowRateLimiter:
    """Clock-controlled per-key sliding-window limiter."""

    limit: int
    window: timedelta
    _events: dict[str, deque[datetime]] = field(default_factory=dict)

    def allow(self, key: str, now: datetime) -> bool:
        """Record one allowed request or reject when the window is full."""
        _require_aware(now)
        if self.limit < 1 or self.window <= timedelta(0):
            msg = "rate limiter configuration must be positive"
            raise SecurityControlError(msg)
        events = self._events.setdefault(key, deque())
        threshold = now - self.window
        while events and events[0] <= threshold:
            _ = events.popleft()
        if len(events) >= self.limit:
            return False
        events.append(now)
        return True


@dataclass(frozen=True, slots=True)
class CsrfProtector:
    """Stateless HMAC CSRF token bound to a session identity."""

    secret: bytes

    def issue(self, session_id: str) -> str:
        """Issue one deterministic session-bound CSRF token."""
        if len(self.secret) < _MIN_SECRET_BYTES or not session_id.strip():
            msg = "CSRF secret and session identity are required"
            raise SecurityControlError(msg)
        return hmac.new(self.secret, session_id.encode(), hashlib.sha256).hexdigest()

    def verify(self, session_id: str, token: str) -> bool:
        """Compare a submitted token in constant time."""
        expected = self.issue(session_id)
        return hmac.compare_digest(expected, token)


def security_headers() -> MappingProxyType[str, str]:
    """Return immutable production browser headers."""
    return _SECURITY_HEADERS


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


def _require_aware(now: datetime) -> None:
    if now.tzinfo is None or now.utcoffset() is None:
        msg = "rate limiter clock must be timezone-aware"
        raise SecurityControlError(msg)
