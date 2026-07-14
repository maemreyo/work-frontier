"""HTTP-bound browser security controls owned by the API interface."""

from __future__ import annotations

import hashlib
import hmac
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from types import MappingProxyType
from typing import Final

_MIN_SECRET_BYTES: Final = 32
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


class BrowserSecurityError(ValueError):
    """Signal invalid input to an API-bound browser security control."""


@dataclass(slots=True)
class SlidingWindowRateLimiter:
    """Clock-controlled per-key sliding-window limiter."""

    limit: int
    window: timedelta
    _events: dict[str, deque[datetime]] = field(default_factory=dict)

    def allow(self, key: str, now: datetime) -> bool:
        """Record one allowed request or reject when the window is full."""
        if now.tzinfo is None or now.utcoffset() is None:
            message = "rate limiter clock must be timezone-aware"
            raise BrowserSecurityError(message)
        if self.limit < 1 or self.window <= timedelta(0):
            message = "rate limiter configuration must be positive"
            raise BrowserSecurityError(message)
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
            message = "CSRF secret and session identity are required"
            raise BrowserSecurityError(message)
        return hmac.new(self.secret, session_id.encode(), hashlib.sha256).hexdigest()

    def verify(self, session_id: str, token: str) -> bool:
        """Compare a submitted token in constant time."""
        return hmac.compare_digest(self.issue(session_id), token)


def security_headers() -> MappingProxyType[str, str]:
    """Return immutable production browser headers."""
    return _SECURITY_HEADERS
