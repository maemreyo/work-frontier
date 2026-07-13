"""Application service port and deterministic in-memory control-plane adapter."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Final, NoReturn, Protocol

from work_frontier.interfaces.api.errors import ControlPlaneError
from work_frontier.interfaces.api.models import (
    ApprovalResponse,
    AttentionResponse,
    ClaimBody,
    FrontierItem,
    FrontierPage,
    LeaseResponse,
    ProposalBody,
    ProposalResponse,
    SyncResponse,
    WriterStateResponse,
)

_MAX_PAGE_SIZE: Final = 100
_HTTP_UNAUTHORIZED: Final = 401
_HTTP_FORBIDDEN: Final = 403
_HTTP_NOT_FOUND: Final = 404
_HTTP_CONFLICT: Final = 409
_HTTP_UNPROCESSABLE: Final = 422


def _raise_control_plane_error(
    code: str,
    message: str,
    status_code: int,
    *,
    cause: BaseException | None = None,
) -> NoReturn:
    """Raise one typed control-plane error with an optional cause."""
    error = ControlPlaneError(code, message, status_code)
    if cause is None:
        raise error
    raise error from cause


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Authenticated tenant/workspace/actor context for one API request."""

    tenant_id: str
    workspace_id: str
    actor_id: str
    session_token: str


class ControlPlaneService(Protocol):
    """Application operations consumed by HTTP, worker, scheduler, and CLI."""

    def validate_session(
        self,
        *,
        token: str,
        tenant_id: str,
        workspace_id: str,
        actor_hint: str | None,
    ) -> RequestContext:
        """Resolve an opaque session into current scoped authorization."""
        ...

    def frontier(
        self, context: RequestContext, *, cursor: str | None, limit: int
    ) -> FrontierPage:
        """Return a current authoritative frontier page."""
        ...

    def item(self, context: RequestContext, item_id: str) -> FrontierItem:
        """Return one scoped current item projection."""
        ...

    def claim(
        self, context: RequestContext, item_id: str, body: ClaimBody
    ) -> LeaseResponse:
        """Atomically claim one authoritative-ready item."""
        ...

    def create_proposal(
        self, context: RequestContext, body: ProposalBody
    ) -> ProposalResponse:
        """Create one immutable proposal."""
        ...

    def approve_proposal(
        self, context: RequestContext, proposal_id: str
    ) -> ApprovalResponse:
        """Approve and recompute one current proposal."""
        ...

    def writer_state(self, context: RequestContext) -> WriterStateResponse:
        """Return exclusive external writer state."""
        ...

    def schedule_sync(self, context: RequestContext) -> SyncResponse:
        """Schedule a durable workspace sync."""
        ...

    def attention(self, context: RequestContext) -> tuple[AttentionResponse, ...]:
        """Return current scoped attention items."""
        ...

    def worker_once(self) -> str:
        """Process one durable unit of work."""
        ...

    def scheduler_once(self) -> str:
        """Schedule due work once under fencing."""
        ...


@dataclass(slots=True)
class _Proposal:
    proposal_id: str
    actor_id: str
    body: ProposalBody


@dataclass(slots=True)
class InMemoryControlPlane:
    """Deterministic application adapter used by tests and local development."""

    tenant_id: str
    workspace_id: str
    sessions: dict[str, str]
    items: dict[str, FrontierItem]
    source_revision: str
    leases: dict[str, LeaseResponse] = field(default_factory=dict)
    proposals: dict[str, _Proposal] = field(default_factory=dict)
    sync_jobs: list[str] = field(default_factory=list)
    attention_items: tuple[AttentionResponse, ...] = ()
    writer: WriterStateResponse = field(
        default_factory=lambda: WriterStateResponse(
            mode="legacy_active",
            active_writer="legacy",
            version=1,
        )
    )

    @classmethod
    def seeded(cls) -> InMemoryControlPlane:
        """Create a stable single-workspace control plane fixture."""
        item = FrontierItem(
            item_id="item-1",
            decision_id="decision-1",
            decision_type="ready",
            title="Recommended work",
            ready=True,
            ranking_position=1,
            authority="authoritative",
            freshness="current",
            why=("program_priority", "stable_id"),
            blocked_by=(),
        )
        return cls(
            tenant_id="tenant-1",
            workspace_id="workspace-1",
            sessions={"session-good": "builder-1"},
            items={item.item_id: item},
            source_revision="rev-1",
        )

    def validate_session(
        self,
        *,
        token: str,
        tenant_id: str,
        workspace_id: str,
        actor_hint: str | None,
    ) -> RequestContext:
        """Validate opaque session and exact scope without leaking other scopes."""
        actor = self.sessions.get(token)
        if actor is None:
            _raise_control_plane_error(
                "invalid_session", "authentication required", _HTTP_UNAUTHORIZED
            )
        if tenant_id != self.tenant_id or workspace_id != self.workspace_id:
            _raise_control_plane_error(
                "not_found", "resource not found", _HTTP_NOT_FOUND
            )
        if actor_hint is not None and actor_hint.strip():
            actor = actor_hint
        return RequestContext(tenant_id, workspace_id, actor, token)

    def frontier(
        self,
        context: RequestContext,
        *,
        cursor: str | None,
        limit: int,
    ) -> FrontierPage:
        """Return deterministic cursor pagination over current items."""
        self._require_scope(context)
        if not 1 <= limit <= _MAX_PAGE_SIZE:
            _raise_control_plane_error(
                "invalid_request",
                f"limit must be 1..{_MAX_PAGE_SIZE}",
                _HTTP_UNPROCESSABLE,
            )
        try:
            start = 0 if cursor is None else int(cursor)
        except ValueError as exc:
            _raise_control_plane_error(
                "invalid_request",
                "cursor is invalid",
                _HTTP_UNPROCESSABLE,
                cause=exc,
            )
        ordered = tuple(sorted(self.items.values(), key=_frontier_sort_key))
        page = ordered[start : start + limit]
        next_index = start + len(page)
        next_cursor = str(next_index) if next_index < len(ordered) else None
        return FrontierPage(items=page, next_cursor=next_cursor)

    def item(self, context: RequestContext, item_id: str) -> FrontierItem:
        """Return one item in scope or a non-leaking not-found response."""
        self._require_scope(context)
        item = self.items.get(item_id)
        if item is None:
            _raise_control_plane_error(
                "not_found", "resource not found", _HTTP_NOT_FOUND
            )
        return item

    def claim(
        self,
        context: RequestContext,
        item_id: str,
        body: ClaimBody,
    ) -> LeaseResponse:
        """Create exactly one active lease anchored to the current decision."""
        item = self.item(context, item_id)
        if body.decision_id != item.decision_id or not item.ready:
            _raise_control_plane_error(
                "stale_decision",
                "item is no longer claimable from this decision",
                _HTTP_CONFLICT,
            )
        existing = self.leases.get(item_id)
        if existing is not None:
            _raise_control_plane_error(
                "lease_conflict", "item is already claimed", _HTTP_CONFLICT
            )
        lease = LeaseResponse(
            lease_id=_short_hash(f"{item_id}|{context.actor_id}|{body.decision_id}"),
            item_id=item_id,
            owner=context.actor_id,
            decision_id=body.decision_id,
            version=1,
        )
        self.leases[item_id] = lease
        return lease

    def create_proposal(
        self,
        context: RequestContext,
        body: ProposalBody,
    ) -> ProposalResponse:
        """Store one immutable proposal anchored to caller-visible authority."""
        self._require_scope(context)
        separator = "|"
        proposal_basis = separator.join(
            (
                context.actor_id,
                body.item_id,
                body.base_decision_id,
                body.expected_source_revision,
                body.field,
                body.new_value,
            )
        )
        proposal_id = _short_hash(proposal_basis)
        self.proposals[proposal_id] = _Proposal(proposal_id, context.actor_id, body)
        return ProposalResponse(
            proposal_id=proposal_id,
            state="pending",
            item_id=body.item_id,
            base_decision_id=body.base_decision_id,
        )

    def approve_proposal(
        self,
        context: RequestContext,
        proposal_id: str,
    ) -> ApprovalResponse:
        """Enforce SoD/staleness and update the current projection atomically."""
        self._require_scope(context)
        proposal = self.proposals.get(proposal_id)
        if proposal is None:
            _raise_control_plane_error(
                "not_found", "proposal not found", _HTTP_NOT_FOUND
            )
        if proposal.actor_id == context.actor_id:
            _raise_control_plane_error(
                "separation_of_duties",
                "proposer cannot be the sole approver",
                _HTTP_FORBIDDEN,
            )
        item = self.items.get(proposal.body.item_id)
        if (
            item is None
            or item.decision_id != proposal.body.base_decision_id
            or proposal.body.expected_source_revision != self.source_revision
        ):
            _raise_control_plane_error(
                "stale_decision",
                "proposal authority changed; refresh required",
                _HTTP_CONFLICT,
            )
        new_decision_id = _short_hash(f"{proposal_id}|{item.decision_id}|accepted")
        self.items[item.item_id] = item.model_copy(
            update={"decision_id": new_decision_id}
        )
        return ApprovalResponse(
            proposal_id=proposal_id,
            state="accepted",
            new_decision_id=new_decision_id,
            derived_from_decision_id=item.decision_id,
        )

    def writer_state(self, context: RequestContext) -> WriterStateResponse:
        """Return current exclusive writer state."""
        self._require_scope(context)
        return self.writer

    def schedule_sync(self, context: RequestContext) -> SyncResponse:
        """Create one deterministic durable sync intent."""
        self._require_scope(context)
        job_id = _short_hash(
            f"{context.tenant_id}|{context.workspace_id}|{len(self.sync_jobs)}"
        )
        self.sync_jobs.append(job_id)
        return SyncResponse(job_id=job_id, state="persisted")

    def attention(self, context: RequestContext) -> tuple[AttentionResponse, ...]:
        """Return current attention items."""
        self._require_scope(context)
        return self.attention_items

    def worker_once(self) -> str:
        """Complete one queued sync or report idle."""
        if not self.sync_jobs:
            return "idle"
        return f"completed:{self.sync_jobs.pop(0)}"

    def scheduler_once(self) -> str:
        """Report how many jobs are currently scheduled."""
        return f"scheduled:{len(self.sync_jobs)}"

    def _require_scope(self, context: RequestContext) -> None:
        if (
            context.tenant_id != self.tenant_id
            or context.workspace_id != self.workspace_id
        ):
            _raise_control_plane_error(
                "not_found", "resource not found", _HTTP_NOT_FOUND
            )


def _frontier_sort_key(item: FrontierItem) -> tuple[int, str]:
    return (
        item.ranking_position if item.ranking_position is not None else 2**31,
        item.item_id,
    )


def _short_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()[:32]
