"""FastAPI application factory with mandatory scope and session middleware."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from fastapi import FastAPI, Path, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, PlainTextResponse

from work_frontier.interfaces.api.errors import ControlPlaneError
from work_frontier.interfaces.api.models import (
    ApprovalResponse,
    AttentionResponse,
    ClaimBody,
    ErrorBody,
    ErrorEnvelope,
    FrontierItem,
    FrontierPage,
    HealthResponse,
    LeaseResponse,
    ProposalBody,
    ProposalResponse,
    SyncResponse,
    WriterStateResponse,
)
from work_frontier.interfaces.api.security import install_security_middleware

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.responses import Response

    from work_frontier.interfaces.api.services import (
        ControlPlaneService,
        RequestContext,
    )

_ItemId = Annotated[str, Path(pattern=r"^[A-Za-z0-9._:-]{1,128}$")]
_ProposalId = Annotated[str, Path(pattern=r"^[A-Fa-f0-9]{16,64}$")]
_PUBLIC_PATHS = frozenset({"/healthz", "/metrics", "/openapi.json", "/docs", "/redoc"})


def create_app(service: ControlPlaneService) -> FastAPI:
    """Create the web process with injected application services."""
    app = FastAPI(
        title="Work Frontier Control Plane",
        version="0.1.0",
        openapi_version="3.1.0",
    )
    app.state.control_plane_service = service
    install_security_middleware(app)
    _install_error_handlers(app)
    _install_scope_middleware(app, service)
    _install_routes(app, service)
    return app


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ControlPlaneError)
    async def control_plane_error(
        _request: Request,
        exc: ControlPlaneError,
    ) -> JSONResponse:
        payload = ErrorEnvelope(error=ErrorBody(code=exc.code, message=exc.message))
        return JSONResponse(status_code=exc.status_code, content=payload.model_dump())

    @app.exception_handler(RequestValidationError)
    async def validation_error(
        _request: Request,
        _exc: RequestValidationError,
    ) -> JSONResponse:
        payload = ErrorEnvelope(
            error=ErrorBody(
                code="invalid_request",
                message="request validation failed",
            )
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=payload.model_dump(),
        )

    _ = control_plane_error, validation_error


def _install_scope_middleware(
    app: FastAPI,
    service: ControlPlaneService,
) -> None:
    @app.middleware("http")
    async def scoped_session(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if request.url.path in _PUBLIC_PATHS:
            return await call_next(request)
        authorization = request.headers.get("Authorization", "")
        tenant_id = request.headers.get("X-Tenant-ID", "")
        workspace_id = request.headers.get("X-Workspace-ID", "")
        actor_hint = request.headers.get("X-Actor-ID")
        if not authorization.startswith("Bearer ") or not tenant_id or not workspace_id:
            error = ErrorEnvelope(
                error=ErrorBody(
                    code="invalid_session",
                    message="authentication required",
                )
            )
            return JSONResponse(status_code=401, content=error.model_dump())
        token = authorization.removeprefix("Bearer ").strip()
        try:
            context = service.validate_session(
                token=token,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                actor_hint=actor_hint,
            )
        except ControlPlaneError as exc:
            payload = ErrorEnvelope(error=ErrorBody(code=exc.code, message=exc.message))
            return JSONResponse(
                status_code=exc.status_code,
                content=payload.model_dump(),
            )
        request.state.context = context
        return await call_next(request)

    _ = scoped_session


def _request_context(request: Request) -> RequestContext:
    """Return the middleware-authenticated request context."""
    return cast("RequestContext", request.state.context)


def _install_routes(app: FastAPI, service: ControlPlaneService) -> None:
    _install_read_routes(app, service)
    _install_write_routes(app, service)


def _install_read_routes(app: FastAPI, service: ControlPlaneService) -> None:
    @app.get("/healthz", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", process="web")

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        return (
            "# HELP work_frontier_up Process health\n"
            "# TYPE work_frontier_up gauge\n"
            'work_frontier_up{process="web"} 1\n'
        )

    @app.get("/frontier", response_model=FrontierPage)
    def frontier(
        request: Request,
        cursor: str | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
    ) -> FrontierPage:
        return service.frontier(_request_context(request), cursor=cursor, limit=limit)

    @app.get("/frontier/{item_id}", response_model=FrontierItem)
    def item(request: Request, item_id: _ItemId) -> FrontierItem:
        return service.item(_request_context(request), item_id)

    @app.get("/writer-state", response_model=WriterStateResponse)
    def writer_state(request: Request) -> WriterStateResponse:
        return service.writer_state(_request_context(request))

    @app.get("/attention", response_model=tuple[AttentionResponse, ...])
    def attention(request: Request) -> tuple[AttentionResponse, ...]:
        return service.attention(_request_context(request))

    _ = health, metrics, frontier, item, writer_state, attention


def _install_write_routes(app: FastAPI, service: ControlPlaneService) -> None:
    @app.post(
        "/leases/{item_id}/claim",
        response_model=LeaseResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def claim(request: Request, item_id: _ItemId, body: ClaimBody) -> LeaseResponse:
        return service.claim(_request_context(request), item_id, body)

    @app.post(
        "/proposals",
        response_model=ProposalResponse,
        status_code=status.HTTP_201_CREATED,
    )
    def create_proposal(request: Request, body: ProposalBody) -> ProposalResponse:
        return service.create_proposal(_request_context(request), body)

    @app.post(
        "/proposals/{proposal_id}/approve",
        response_model=ApprovalResponse,
    )
    def approve_proposal(
        request: Request,
        proposal_id: _ProposalId,
    ) -> ApprovalResponse:
        return service.approve_proposal(_request_context(request), proposal_id)

    @app.post(
        "/sync",
        response_model=SyncResponse,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def sync(request: Request) -> SyncResponse:
        return service.schedule_sync(_request_context(request))

    _ = claim, create_proposal, approve_proposal, sync
