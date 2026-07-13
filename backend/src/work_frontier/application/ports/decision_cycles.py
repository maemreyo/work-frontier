"""Port for atomically persisting one immutable DecisionRecord set."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class DecisionCycleError(RuntimeError):
    """Base failure for one atomic decision cycle."""


class StaleSourceCursorError(DecisionCycleError):
    """Signal an optimistic source-cursor fencing failure."""


@dataclass(frozen=True, slots=True)
class DecisionCycleCommand:
    """Identities and fences required for one atomic decision cycle."""

    tenant_id: str
    workspace_id: str
    connection_id: str
    cycle_id: str
    expected_source_revision: str | None
    new_source_revision: str
    snapshot_id: str
    snapshot_hash: str
    graph_revision: str
    policy_bundle_hash: str
    causation_id: str
    correlation_id: str
    outbox_id: str
    outbox_idempotency_key: str

    def __post_init__(self) -> None:
        """Reject blank scope, identity, hash, and source fence fields."""
        required = (
            self.tenant_id,
            self.workspace_id,
            self.connection_id,
            self.cycle_id,
            self.new_source_revision,
            self.snapshot_id,
            self.snapshot_hash,
            self.graph_revision,
            self.policy_bundle_hash,
            self.causation_id,
            self.correlation_id,
            self.outbox_id,
            self.outbox_idempotency_key,
        )
        if any(not value.strip() for value in required):
            msg = "decision cycle identities and hashes must not be blank"
            raise ValueError(msg)
        if self.expected_source_revision == self.new_source_revision:
            msg = "decision cycle must advance the source revision"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DecisionRecordDocument:
    """Canonical immutable decision payload ready for persistence."""

    decision_id: str
    item_id: str
    payload: dict[str, object]
    payload_hash: str

    def __post_init__(self) -> None:
        """Reject blank decision/item/hash identities."""
        if any(
            not value.strip()
            for value in (self.decision_id, self.item_id, self.payload_hash)
        ):
            msg = "decision record identity, item, and payload hash are required"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class SourceVersionDocument:
    """Immutable authoritative source version included in one atomic cycle."""

    source_version_id: str
    item_id: str
    source_id: str
    revision: str
    payload: dict[str, object]
    payload_hash: str

    def __post_init__(self) -> None:
        """Reject blank source identities and payload hashes."""
        required = (
            self.source_version_id,
            self.item_id,
            self.source_id,
            self.revision,
            self.payload_hash,
        )
        if any(not value.strip() for value in required):
            msg = "source version identity, revision, and hash are required"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class NormalizedSnapshotDocument:
    """Canonical normalized snapshot persisted before its decision set."""

    snapshot_id: str
    payload: dict[str, object]
    payload_hash: str
    source_revision_set: tuple[tuple[str, str], ...]
    graph_revision: str
    profile_version: str

    def __post_init__(self) -> None:
        """Reject blank identity/hash/version fields and empty revisions."""
        required = (
            self.snapshot_id,
            self.payload_hash,
            self.graph_revision,
            self.profile_version,
        )
        if any(not value.strip() for value in required) or not self.source_revision_set:
            msg = (
                "normalized snapshot identity, hash, revisions, and versions "
                "are required"
            )
            raise ValueError(msg)
        object.__setattr__(
            self,
            "source_revision_set",
            tuple(sorted(self.source_revision_set)),
        )


@dataclass(frozen=True, slots=True)
class DecisionCycleWrite:
    """Complete immutable write set for one atomic cycle."""

    command: DecisionCycleCommand
    source_versions: tuple[SourceVersionDocument, ...]
    normalized_snapshot: NormalizedSnapshotDocument
    decisions: tuple[DecisionRecordDocument, ...]
    decision_set_hash: str
    recommended_item_id: str | None

    def __post_init__(self) -> None:
        """Require unique item and decision identities in one non-empty cycle."""
        if (
            not self.decisions
            or not self.source_versions
            or not self.decision_set_hash.strip()
        ):
            msg = "decision cycle requires source versions, records, and a set hash"
            raise ValueError(msg)
        if self.normalized_snapshot.snapshot_id != self.command.snapshot_id:
            msg = "normalized snapshot identity must match the decision command"
            raise ValueError(msg)
        if self.normalized_snapshot.payload_hash != self.command.snapshot_hash:
            msg = "normalized snapshot hash must match the decision command"
            raise ValueError(msg)
        decision_ids = {item.decision_id for item in self.decisions}
        item_ids = {item.item_id for item in self.decisions}
        if len(decision_ids) != len(self.decisions) or len(item_ids) != len(
            self.decisions
        ):
            msg = "decision cycle record and item identities must be unique"
            raise ValueError(msg)
        source_ids = {item.source_version_id for item in self.source_versions}
        if len(source_ids) != len(self.source_versions):
            msg = "decision cycle source-version identities must be unique"
            raise ValueError(msg)
        if (
            self.recommended_item_id is not None
            and self.recommended_item_id not in item_ids
        ):
            msg = "recommended item must belong to the decision cycle"
            raise ValueError(msg)


@dataclass(frozen=True, slots=True)
class DecisionCycleReceipt:
    """Result proving one cycle became the only visible workspace frontier."""

    cycle_id: str
    source_revision: str
    decision_count: int
    active_frontier_version: int
    decision_set_hash: str


class DecisionCycleRepository(Protocol):
    """Atomic persistence boundary for one complete decision cycle."""

    async def persist(self, write: DecisionCycleWrite) -> DecisionCycleReceipt:
        """Persist all records/projections/audit/outbox/cursor or none of them."""
        ...
