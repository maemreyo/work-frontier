"""WorkLease coordination and deterministic AttentionItem lifecycle."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

_MIN_REASON_LENGTH = 20


class ClaimError(ValueError):
    """Signal an invalid lease or attention transition."""


class LeaseMode(StrEnum):
    """Supported coordination modes."""

    EXCLUSIVE = "exclusive"
    COLLABORATIVE = "collaborative"


class LeaseState(StrEnum):
    """WorkLease lifecycle states."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    RELEASED = "released"
    EXPIRED = "expired"


class AttentionState(StrEnum):
    """Attention lifecycle states."""

    OPEN = "open"
    RESOLVED = "resolved"


@dataclass(frozen=True, slots=True)
class ClaimRequest:
    """Compare-and-swap request for one item claim."""

    lease_id: str
    item_id: str
    actor: str
    mode: LeaseMode
    decision_id: str
    expected_version: int
    ttl: timedelta


@dataclass(frozen=True, slots=True)
class WorkLease:
    """Versioned claim that preserves readiness while changing claimability."""

    lease_id: str
    item_id: str
    owner: str
    collaborators: tuple[str, ...]
    mode: LeaseMode
    state: LeaseState
    decision_id: str
    version: int
    expires_at: datetime
    heartbeat_at: datetime
    handoff_to: str | None = None


@dataclass(frozen=True, slots=True)
class CoordinationEvent:
    """Audit-facing immutable coordination event."""

    event_type: str
    actor: str
    item_id: str
    reason: str
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class AttentionItem:
    """Deterministic attention record for surfaced operational risk."""

    attention_id: str
    item_id: str | None
    category: str
    severity: str
    deterministic_basis: str
    state: AttentionState
    opened_at: datetime
    resolved_at: datetime | None = None
    resolution: str | None = None


def claim_item(
    existing: WorkLease | None,
    request: ClaimRequest,
    *,
    current_decision_id: str,
    now: datetime,
) -> WorkLease:
    """Claim atomically, releasing expired leases and rejecting stale decisions."""
    _require_aware(now, "now")
    if request.decision_id != current_decision_id:
        msg = "stale DecisionRecord cannot support a lease"
        raise ClaimError(msg)
    if request.ttl <= timedelta(0):
        msg = "claim TTL must be positive"
        raise ClaimError(msg)
    active_lease = (
        existing
        if existing is not None and existing.state is LeaseState.ACTIVE
        else None
    )
    if active_lease is not None and now >= active_lease.expires_at:
        active_lease = None
    if active_lease is not None:
        if (
            active_lease.mode is LeaseMode.EXCLUSIVE
            or request.mode is LeaseMode.EXCLUSIVE
        ):
            msg = "item is already claimed by an active exclusive lease"
            raise ClaimError(msg)
        if active_lease.version != request.expected_version:
            msg = "lease compare-and-swap version changed"
            raise ClaimError(msg)
        members = tuple(
            sorted({active_lease.owner, *active_lease.collaborators, request.actor})
        )
        return replace(
            active_lease,
            collaborators=tuple(
                member for member in members if member != active_lease.owner
            ),
            version=active_lease.version + 1,
            expires_at=now + request.ttl,
            heartbeat_at=now,
        )
    if request.expected_version != 0:
        msg = "new lease requires expected version zero"
        raise ClaimError(msg)
    return WorkLease(
        lease_id=request.lease_id,
        item_id=request.item_id,
        owner=request.actor,
        collaborators=(),
        mode=request.mode,
        state=LeaseState.ACTIVE,
        decision_id=request.decision_id,
        version=1,
        expires_at=now + request.ttl,
        heartbeat_at=now,
    )


def heartbeat(lease: WorkLease, *, actor: str, now: datetime) -> WorkLease:
    """Renew an active lease heartbeat for its owner or collaborator."""
    _require_aware(now, "now")
    if actor not in {lease.owner, *lease.collaborators}:
        msg = "only lease participants may heartbeat"
        raise ClaimError(msg)
    if lease.state is not LeaseState.ACTIVE or now >= lease.expires_at:
        msg = "inactive or expired lease cannot heartbeat"
        raise ClaimError(msg)
    extension = lease.expires_at - lease.heartbeat_at
    return replace(
        lease,
        version=lease.version + 1,
        heartbeat_at=now,
        expires_at=now + extension,
    )


def request_handoff(lease: WorkLease, *, actor: str, target: str) -> WorkLease:
    """Record a visible handoff request instead of silently breaking ownership."""
    if not actor.strip() or not target.strip() or target == lease.owner:
        msg = "handoff requires distinct actor and target identities"
        raise ClaimError(msg)
    if lease.state is not LeaseState.ACTIVE:
        msg = "only active leases accept handoff requests"
        raise ClaimError(msg)
    return replace(lease, handoff_to=target, version=lease.version + 1)


def force_override(
    lease: WorkLease,
    *,
    actor: str,
    new_owner: str,
    reason: str,
    now: datetime,
) -> tuple[WorkLease, CoordinationEvent]:
    """Force an authorized reassignment and emit its immutable audit event."""
    _require_aware(now, "now")
    if len(reason.strip()) < _MIN_REASON_LENGTH:
        msg = "forced override reason must contain at least 20 characters"
        raise ClaimError(msg)
    updated = replace(
        lease,
        owner=new_owner,
        collaborators=(),
        version=lease.version + 1,
        heartbeat_at=now,
        handoff_to=None,
    )
    event = CoordinationEvent(
        event_type="lease_forced_override",
        actor=actor,
        item_id=lease.item_id,
        reason=reason.strip(),
        occurred_at=now,
    )
    return updated, event


def release(lease: WorkLease, *, actor: str, now: datetime) -> WorkLease:
    """Release a lease only by a current participant."""
    _require_aware(now, "now")
    if actor not in {lease.owner, *lease.collaborators}:
        msg = "only lease participants may release"
        raise ClaimError(msg)
    return replace(
        lease,
        state=LeaseState.RELEASED,
        version=lease.version + 1,
        heartbeat_at=now,
    )


def open_attention(
    *,
    item_id: str | None,
    category: str,
    severity: str,
    deterministic_basis: str,
    opened_at: datetime,
) -> AttentionItem:
    """Open a deterministic AttentionItem from its semantic basis."""
    _require_aware(opened_at, "opened_at")
    identity = "|".join((item_id or "workspace", category, deterministic_basis))
    attention_id = hashlib.sha256(identity.encode()).hexdigest()[:32]
    return AttentionItem(
        attention_id=attention_id,
        item_id=item_id,
        category=category,
        severity=severity,
        deterministic_basis=deterministic_basis,
        state=AttentionState.OPEN,
        opened_at=opened_at,
    )


def resolve_attention(
    item: AttentionItem,
    *,
    actor: str,
    resolution: str,
    now: datetime,
) -> AttentionItem:
    """Resolve an open AttentionItem with an explicit actor-facing rationale."""
    del actor
    _require_aware(now, "now")
    if item.state is not AttentionState.OPEN or not resolution.strip():
        msg = "only open attention with a resolution may be closed"
        raise ClaimError(msg)
    return replace(
        item,
        state=AttentionState.RESOLVED,
        resolved_at=now,
        resolution=resolution.strip(),
    )


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = f"{field} must be timezone-aware"
        raise ClaimError(msg)
