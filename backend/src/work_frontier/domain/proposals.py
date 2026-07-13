"""Immutable proposed-change, approval, override, and recompute invariants."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


_MIN_REASON_LENGTH = 20


class ProposalError(ValueError):
    """Signal an invalid or unsafe proposal lifecycle transition."""


@dataclass(frozen=True, slots=True, order=True)
class FieldChange:
    """One immutable proposed field mutation."""

    field: str
    old_value: str | None
    new_value: str | None

    def __post_init__(self) -> None:
        """Require a named field and an actual value change."""
        if not self.field.strip() or self.old_value == self.new_value:
            msg = "field changes require a name and distinct values"
            raise ProposalError(msg)


@dataclass(frozen=True, slots=True)
class ProposedChange:
    """Immutable proposal anchored to a decision and source revision."""

    proposal_id: str
    item_id: str
    proposer: str
    base_decision_id: str
    expected_source_revision: str
    changes: tuple[FieldChange, ...]
    created_at: datetime

    @classmethod
    def create(  # noqa: PLR0913 - explicit proposal identity inputs are auditable
        cls,
        *,
        proposal_id: str,
        item_id: str,
        proposer: str,
        base_decision_id: str,
        expected_source_revision: str,
        changes: tuple[FieldChange, ...],
        created_at: datetime,
    ) -> ProposedChange:
        """Create a canonical proposal with unique ordered fields."""
        _require_aware(created_at, "created_at")
        ordered = tuple(sorted(changes, key=lambda change: change.field))
        if not ordered or len({change.field for change in ordered}) != len(ordered):
            msg = "proposal changes must be non-empty with unique fields"
            raise ProposalError(msg)
        required = (
            proposal_id,
            item_id,
            proposer,
            base_decision_id,
            expected_source_revision,
        )
        if any(not value.strip() for value in required):
            msg = "proposal identities and source revision are required"
            raise ProposalError(msg)
        return cls(
            proposal_id=proposal_id,
            item_id=item_id,
            proposer=proposer,
            base_decision_id=base_decision_id,
            expected_source_revision=expected_source_revision,
            changes=ordered,
            created_at=created_at,
        )


@dataclass(frozen=True, slots=True)
class Approval:
    """Immutable approval anchored to the proposal's current authority inputs."""

    proposal_id: str
    approver: str
    approved_at: datetime
    base_decision_id: str
    source_revision: str

    def __post_init__(self) -> None:
        """Validate approval identity and timestamp."""
        _require_aware(self.approved_at, "approved_at")
        required = (
            self.proposal_id,
            self.approver,
            self.base_decision_id,
            self.source_revision,
        )
        if any(not value.strip() for value in required):
            msg = "approval identities and authority inputs are required"
            raise ProposalError(msg)


@dataclass(frozen=True, slots=True)
class OverrideRecord:
    """Time-bounded non-weakening override record."""

    override_id: str
    actor: str
    item_id: str
    reason: str
    expires_at: datetime
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AppliedMutation:
    """Immutable disposition and newly derived decision identity."""

    proposal_id: str
    disposition: str
    derived_from_decision_id: str
    new_decision_id: str
    applied_at: datetime
    changes: tuple[FieldChange, ...]


def create_override(  # noqa: PLR0913 - explicit override safety inputs are auditable
    *,
    override_id: str,
    actor: str,
    item_id: str,
    reason: str,
    expires_at: datetime,
    safety_weakening: bool,
    completion_weakening: bool,
    created_at: datetime,
) -> OverrideRecord:
    """Create only scoped, time-bounded, non-weakening overrides."""
    _require_aware(created_at, "created_at")
    _require_aware(expires_at, "expires_at")
    if expires_at <= created_at:
        msg = "override expiry must be after creation"
        raise ProposalError(msg)
    if safety_weakening or completion_weakening:
        msg = "overrides cannot weaken safety or completion semantics"
        raise ProposalError(msg)
    if len(reason.strip()) < _MIN_REASON_LENGTH:
        msg = "override reason must contain at least 20 characters"
        raise ProposalError(msg)
    return OverrideRecord(
        override_id=override_id,
        actor=actor,
        item_id=item_id,
        reason=reason.strip(),
        expires_at=expires_at,
        created_at=created_at,
    )


def apply_approved_change(  # noqa: PLR0913 - approval fences are explicit
    *,
    proposal: ProposedChange,
    approval: Approval | None,
    claimant: str,
    current_decision_id: str,
    current_source_revision: str,
    applied_at: datetime,
) -> AppliedMutation:
    """Validate approval/SoD/staleness and derive a new immutable decision ID."""
    _require_aware(applied_at, "applied_at")
    if approval is None:
        msg = "approval is required before an authoritative mutation"
        raise ProposalError(msg)
    if approval.proposal_id != proposal.proposal_id:
        msg = "approval does not reference this proposal"
        raise ProposalError(msg)
    if approval.approver in {proposal.proposer, claimant}:
        msg = "separation of duties forbids proposer or claimant self-approval"
        raise ProposalError(msg)
    anchored = (
        proposal.base_decision_id,
        approval.base_decision_id,
        current_decision_id,
    )
    revisions = (
        proposal.expected_source_revision,
        approval.source_revision,
        current_source_revision,
    )
    if len(set(anchored)) != 1 or len(set(revisions)) != 1:
        msg = "stale approval must be refreshed before mutation"
        raise ProposalError(msg)
    payload = {
        "applied_at": applied_at.isoformat(),
        "base_decision_id": current_decision_id,
        "changes": [
            {
                "field": change.field,
                "new": change.new_value,
                "old": change.old_value,
            }
            for change in proposal.changes
        ],
        "proposal_id": proposal.proposal_id,
        "source_revision": current_source_revision,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    new_decision_id = hashlib.sha256(canonical.encode()).hexdigest()[:32]
    return AppliedMutation(
        proposal_id=proposal.proposal_id,
        disposition="accepted",
        derived_from_decision_id=current_decision_id,
        new_decision_id=new_decision_id,
        applied_at=applied_at,
        changes=proposal.changes,
    )


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = f"{field} must be timezone-aware"
        raise ProposalError(msg)
