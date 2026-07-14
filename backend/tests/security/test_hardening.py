from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.interfaces.api.browser_security import (
    BrowserSecurityError,
    CsrfProtector,
    SlidingWindowRateLimiter,
    security_headers,
)
from work_frontier.platform.security.hardening import (
    EgressPolicy,
    SecurityControlError,
    redact,
    require_tls_configuration,
    validate_upload,
)


def test_https_allowlisted_egress_only() -> None:
    policy = EgressPolicy(frozenset({"api.github.com"}))
    assert policy.validate("https://api.github.com/repos") == (
        "https://api.github.com/repos"
    )
    invalid_urls = (
        "http://api.github.com/repos",
        "https://localhost/internal",
        "https://169.254.169.254/latest",
        "https://api.github.com:444/repos",
        "https://user:pass@api.github.com/repos",
    )
    for invalid in invalid_urls:
        with pytest.raises(SecurityControlError):
            _ = policy.validate(invalid)


def test_csrf_tokens_are_session_bound() -> None:
    protector = CsrfProtector(b"x" * 32)
    token = protector.issue("session-a")
    assert protector.verify("session-a", token)
    assert not protector.verify("session-b", token)


def test_csrf_rejects_an_undersized_secret() -> None:
    with pytest.raises(BrowserSecurityError):
        _ = CsrfProtector(b"x").issue("session-a")


def test_rate_limiter_uses_clock_controlled_window() -> None:
    limiter = SlidingWindowRateLimiter(2, timedelta(minutes=1))
    now = datetime(2026, 7, 13, tzinfo=UTC)
    assert limiter.allow("actor", now)
    assert limiter.allow("actor", now + timedelta(seconds=1))
    assert not limiter.allow("actor", now + timedelta(seconds=2))
    assert limiter.allow("actor", now + timedelta(minutes=1, seconds=1))


def test_upload_validation_blocks_traversal_type_and_size() -> None:
    assert (
        validate_upload(
            filename="evidence.json",
            content_type="application/json",
            size_bytes=20,
        )
        == "evidence.json"
    )
    invalid_values: tuple[tuple[str, str, int], ...] = (
        ("../secret", "text/plain", 1),
        ("a.exe", "application/x-msdownload", 1),
        ("a.txt", "text/plain", 6_000_000),
    )
    for filename, content_type, size_bytes in invalid_values:
        with pytest.raises(SecurityControlError):
            _ = validate_upload(
                filename=filename,
                content_type=content_type,
                size_bytes=size_bytes,
            )


def test_redaction_removes_nested_secrets() -> None:
    result = redact(
        {
            "authorization": "Bearer abc",
            "nested": [{"token": "secret"}, "Bearer hidden"],
            "safe": "visible",
        }
    )
    assert result == {
        "authorization": "[REDACTED]",
        "nested": [{"token": "[REDACTED]"}, "[REDACTED]"],
        "safe": "visible",
    }


def test_security_headers_are_complete() -> None:
    headers = security_headers()
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert headers["Strict-Transport-Security"].startswith("max-age=")


def test_tls_configuration_fails_closed() -> None:
    require_tls_configuration(
        public_base_url="https://frontier.example",
        database_url="postgresql://db/app?sslmode=verify-full",
        object_store_url="https://objects.example",
    )
    with pytest.raises(SecurityControlError):
        require_tls_configuration(
            public_base_url="http://frontier.example",
            database_url="postgresql://db/app",
            object_store_url="http://objects.example",
        )
