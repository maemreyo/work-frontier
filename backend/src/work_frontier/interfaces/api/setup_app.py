"""Loopback-only bootstrap application for interactive setup."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar, Protocol
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from work_frontier.contracts.setup import (
    DetectionSnapshot,
    SecretReference,
    SetupEnvelope,
    SetupPlan,
    SetupProfile,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from pathlib import Path

    from work_frontier.application.setup.service import SetupService


class SecretWriter(Protocol):
    """Store a submitted secret and return only its reference."""

    def store(self, *, namespace: str, name: str, value: str) -> SecretReference:
        """Store secret material and return an opaque reference."""
        ...


class StrictRequest(BaseModel):
    """Reject unexpected setup request fields."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")


class TokenExchange(StrictRequest):
    """One-time bootstrap token exchange."""

    token: str


class DetectRequest(StrictRequest):
    """Detect request."""

    profile: SetupProfile


class PlanRequest(StrictRequest):
    """Reviewed plan request."""

    profile: SetupProfile
    desired: dict[str, str | int | bool]
    expected_snapshot_id: str


class ApplyRequest(StrictRequest):
    """Apply request."""

    plan_id: str


class SecretRequest(StrictRequest):
    """Secret submission that is never journaled or echoed."""

    namespace: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1, max_length=65536)


class SigningKeyRequest(StrictRequest):
    """Generate one release signing key directly into a secret provider."""

    namespace: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=128)
    key_id: str = Field(min_length=1, max_length=128)


@dataclass(slots=True)
class SetupSessionManager:
    """One-time bootstrap token and cookie-bound setup sessions."""

    bootstrap_token: str
    token_used: bool = False
    sessions: dict[str, str] = field(default_factory=dict)

    def exchange(self, token: str) -> tuple[str, str] | None:
        """Consume the bootstrap token exactly once."""
        if self.token_used or not hmac.compare_digest(token, self.bootstrap_token):
            return None
        self.token_used = True
        session_id = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        self.sessions[session_id] = csrf
        return session_id, csrf

    def authorize(self, request: Request, *, csrf_required: bool) -> bool:
        """Validate the HttpOnly session and synchronizer token."""
        session_id = request.cookies.get("wf_setup_session", "")
        expected = self.sessions.get(session_id)
        if expected is None:
            return False
        if not csrf_required:
            return True
        return hmac.compare_digest(request.headers.get("X-Setup-CSRF", ""), expected)

    def close(self, request: Request) -> None:
        """Invalidate the current setup session."""
        session_id = request.cookies.get("wf_setup_session", "")
        _ = self.sessions.pop(session_id, None)


def create_setup_app(
    service: SetupService,
    *,
    bootstrap_token: str,
    secret_store: SecretWriter | None = None,
    static_directory: Path | None = None,
) -> FastAPI:
    """Create a setup-only FastAPI process with no data-plane routes."""
    app = FastAPI(
        title="Work Frontier Setup",
        version="0.1.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    manager = SetupSessionManager(bootstrap_token)
    _install_loopback_middleware(app)
    _install_static_assets(app, static_directory)
    _install_api_routes(app, manager, service, secret_store)
    _install_page_routes(app, static_directory)
    return app


def _install_loopback_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def loopback_only(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not _request_is_loopback(request):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "error": {
                        "code": "loopback_required",
                        "message": "setup is loopback-only",
                    }
                },
            )
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    _ = loopback_only


def _install_static_assets(app: FastAPI, static_directory: Path | None) -> None:
    if static_directory is None or not (static_directory / "assets").is_dir():
        return
    app.mount(
        "/assets",
        StaticFiles(directory=static_directory / "assets"),
        name="setup-assets",
    )


def _install_api_routes(
    app: FastAPI,
    manager: SetupSessionManager,
    service: SetupService,
    secret_store: SecretWriter | None,
) -> None:
    _install_session_routes(app, manager)
    _install_workflow_routes(app, manager, service)
    _install_secret_routes(app, manager, secret_store)


def _install_session_routes(
    app: FastAPI,
    manager: SetupSessionManager,
) -> None:
    @app.post("/api/setup/session/exchange", status_code=204)
    def exchange(body: TokenExchange, response: Response) -> None:
        session = manager.exchange(body.token)
        if session is None:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return
        session_id, csrf = session
        response.set_cookie(
            "wf_setup_session",
            session_id,
            httponly=True,
            secure=False,
            samesite="strict",
            path="/",
        )
        response.headers["X-Setup-CSRF"] = csrf

    @app.post("/api/setup/session/close", status_code=204)
    def close(request: Request, response: Response) -> None:
        _require_session(manager, request, csrf_required=True)
        manager.close(request)
        response.delete_cookie("wf_setup_session", path="/")

    _ = exchange, close


def _install_workflow_routes(
    app: FastAPI,
    manager: SetupSessionManager,
    service: SetupService,
) -> None:
    @app.get("/api/setup/status")
    def setup_status(
        request: Request,
        profile: SetupProfile = SetupProfile.DEVELOPMENT,
    ) -> SetupEnvelope:
        _require_session(manager, request, csrf_required=False)
        return service.status(profile)

    @app.post("/api/setup/detect")
    def detect(body: DetectRequest, request: Request) -> DetectionSnapshot:
        _require_session(manager, request, csrf_required=True)
        return service.detect(body.profile)

    @app.post("/api/setup/plan")
    def plan(body: PlanRequest, request: Request) -> SetupPlan:
        _require_session(manager, request, csrf_required=True)
        return service.plan(
            profile=body.profile,
            desired=body.desired,
            expected_snapshot_id=body.expected_snapshot_id,
        )

    @app.post("/api/setup/apply")
    def apply(body: ApplyRequest, request: Request) -> SetupEnvelope:
        _require_session(manager, request, csrf_required=True)
        return service.apply(body.plan_id)

    @app.post("/api/setup/resume/{session_id}")
    def resume(session_id: str, request: Request) -> SetupEnvelope:
        _require_session(manager, request, csrf_required=True)
        return service.resume(session_id)

    _ = setup_status, detect, plan, apply, resume


def _install_secret_routes(
    app: FastAPI,
    manager: SetupSessionManager,
    secret_store: SecretWriter | None,
) -> None:
    @app.post("/api/setup/signing-key", status_code=201, response_model=None)
    def generate_signing_key(
        body: SigningKeyRequest,
        request: Request,
    ) -> dict[str, str] | JSONResponse:
        _require_session(manager, request, csrf_required=True)
        if secret_store is None:
            return _secret_store_unavailable()
        return generate_signing_key_payload(secret_store, body)

    @app.post("/api/setup/secrets", status_code=201, response_model=None)
    def store_secret(
        body: SecretRequest,
        request: Request,
    ) -> dict[str, str] | JSONResponse:
        _require_session(manager, request, csrf_required=True)
        if secret_store is None:
            return _secret_store_unavailable()
        reference = secret_store.store(
            namespace=body.namespace,
            name=body.name,
            value=body.value,
        )
        return {"reference": reference.uri}

    _ = generate_signing_key, store_secret


def _install_page_routes(app: FastAPI, static_directory: Path | None) -> None:
    @app.get("/setup.html", response_class=HTMLResponse)
    def setup_html() -> Response:
        if static_directory is not None:
            candidate = static_directory / "setup.html"
            if candidate.is_file():
                return FileResponse(candidate)
        return HTMLResponse(_FALLBACK_HTML)

    @app.get("/")
    def root() -> Response:
        return Response(status_code=307, headers={"Location": "/setup.html"})

    _ = setup_html, root


def _require_session(
    manager: SetupSessionManager,
    request: Request,
    *,
    csrf_required: bool,
) -> None:
    if manager.authorize(request, csrf_required=csrf_required):
        return
    status_code = (
        status.HTTP_403_FORBIDDEN if csrf_required else status.HTTP_401_UNAUTHORIZED
    )
    raise HTTPException(
        status_code=status_code,
        detail="valid setup session required",
    )


def _request_is_loopback(request: Request) -> bool:
    host = urlparse(f"//{request.headers.get('Host', '')}").hostname
    if host not in {"127.0.0.1", "localhost", "::1", "testserver"}:
        return False
    forwarded = request.headers.get("Forwarded", "")
    if forwarded and not any(
        marker in forwarded for marker in ("for=127.0.0.1", 'for="[::1]"')
    ):
        return False
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for and forwarded_for.split(",", 1)[0].strip() not in {
        "127.0.0.1",
        "::1",
    }:
        return False
    origin = request.headers.get("Origin")
    if origin:
        hostname = urlparse(origin).hostname
        if hostname not in {"127.0.0.1", "localhost", "::1"}:
            return False
    client = request.client.host if request.client is not None else ""
    return client in {"127.0.0.1", "::1", "testclient"}


_FALLBACK_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Work Frontier Setup</title>
</head>
<body>
  <main id="root">
    <h1>Work Frontier Setup</h1>
    <p>The packaged Setup Center assets are not built yet.</p>
  </main>
</body>
</html>"""


def _secret_store_unavailable() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": {
                "code": "secret_store_unavailable",
                "message": "no writable secret provider is available",
            }
        },
    )


def generate_signing_key_payload(
    secret_store: SecretWriter,
    body: SigningKeyRequest,
) -> dict[str, str]:
    """Generate an Ed25519 key directly into a secret provider."""
    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    private_b64 = base64.b64encode(private_raw).decode("ascii")
    reference = secret_store.store(
        namespace=body.namespace,
        name=body.name,
        value=private_b64,
    )
    return {
        "reference": reference.uri,
        "key_id": body.key_id,
        "public_key_b64": base64.b64encode(public_raw).decode("ascii"),
        "fingerprint": hashlib.sha256(public_raw).hexdigest(),
    }
