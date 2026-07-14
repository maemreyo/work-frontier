"""Authenticated persistent Setup Center routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException, Request, status

from work_frontier.contracts.setup import (
    DetectionSnapshot,
    SetupEnvelope,
    SetupPlan,
    SetupProfile,
)
from work_frontier.interfaces.api.setup_app import (
    ApplyRequest,
    DetectRequest,
    PlanRequest,
    SecretRequest,
    SecretWriter,
    SigningKeyRequest,
    generate_signing_key_payload,
)

if TYPE_CHECKING:
    from work_frontier.application.setup.service import SetupService

_OPERATOR_ROLES = frozenset({"operator", "admin"})


def install_persistent_setup_routes(
    app: FastAPI,
    service: SetupService,
    *,
    secret_store: SecretWriter | None = None,
) -> None:
    """Install operator-scoped setup health, planning, and execution routes."""

    @app.get("/setup/status")
    def setup_status(
        request: Request,
        profile: SetupProfile = SetupProfile.DEVELOPMENT,
    ) -> SetupEnvelope:
        _require_operator(request)
        return service.status(profile)

    @app.post("/setup/detect")
    def detect(request: Request, body: DetectRequest) -> DetectionSnapshot:
        _require_operator(request)
        return service.detect(body.profile)

    @app.post("/setup/plan")
    def plan(request: Request, body: PlanRequest) -> SetupPlan:
        _require_operator(request)
        return service.plan(
            profile=body.profile,
            desired=body.desired,
            expected_snapshot_id=body.expected_snapshot_id,
        )

    @app.post("/setup/apply")
    def apply(request: Request, body: ApplyRequest) -> SetupEnvelope:
        _require_operator(request)
        return service.apply(body.plan_id)

    @app.post("/setup/resume/{session_id}")
    def resume(request: Request, session_id: str) -> SetupEnvelope:
        _require_operator(request)
        return service.resume(session_id)

    @app.post("/setup/secrets", status_code=201)
    def store_secret(
        request: Request,
        body: SecretRequest,
    ) -> dict[str, str]:
        _require_operator(request)
        writer = _require_secret_store(secret_store)
        reference = writer.store(
            namespace=body.namespace,
            name=body.name,
            value=body.value,
        )
        return {"reference": reference.uri}

    @app.post("/setup/signing-key", status_code=201)
    def generate_signing_key(
        request: Request,
        body: SigningKeyRequest,
    ) -> dict[str, str]:
        _require_operator(request)
        writer = _require_secret_store(secret_store)
        return generate_signing_key_payload(writer, body)

    _ = (
        setup_status,
        detect,
        plan,
        apply,
        resume,
        store_secret,
        generate_signing_key,
    )


def _require_operator(request: Request) -> None:
    role = request.headers.get("X-Actor-Role", "")
    if role in _OPERATOR_ROLES:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="operator or admin role required",
    )


def _require_secret_store(
    secret_store: SecretWriter | None,
) -> SecretWriter:
    if secret_store is not None:
        return secret_store
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="no writable secret provider is available",
    )
