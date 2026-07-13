"""FastAPI security middleware for headers, CSRF, and request throttling."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from fastapi.responses import JSONResponse

from work_frontier.platform.security.hardening import (
    CsrfProtector,
    SlidingWindowRateLimiter,
    security_headers,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastapi import FastAPI, Request
    from starlette.responses import Response

_MIN_SECRET_BYTES = 32
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def install_security_middleware(app: FastAPI) -> None:
    """Install browser controls without changing bearer-only API semantics."""
    limiter = SlidingWindowRateLimiter(120, timedelta(minutes=1))

    @app.middleware("http")
    async def hardening(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        client_host = request.client.host if request.client is not None else "unknown"
        actor = request.headers.get("X-Actor-ID", client_host)
        now = datetime.now(UTC)
        if not limiter.allow(actor, now):
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limited",
                        "message": "request rate limit exceeded",
                    }
                },
                headers={"Retry-After": "60"},
            )
        if request.method in _UNSAFE_METHODS and request.headers.get("Cookie"):
            session_id = request.cookies.get("wf_session", "")
            token = request.headers.get("X-CSRF-Token", "")
            secret = os.environ.get("WF_CSRF_SECRET", "").encode()
            if (
                len(secret) < _MIN_SECRET_BYTES
                or not session_id
                or not CsrfProtector(secret).verify(
                    session_id,
                    token,
                )
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "csrf_rejected",
                            "message": "valid CSRF token required",
                        }
                    },
                )
        response = await call_next(request)
        for name, value in security_headers().items():
            response.headers[name] = value
        return response

    _ = hardening
