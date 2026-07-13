"""Ports and immutable inputs for deterministic connection ingestion."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from work_frontier.application.ports.connections import SourceItem


@dataclass(frozen=True, slots=True)
class IngestionCommand:
    """All explicit identities and clocks required for one ingestion cycle."""

    tenant_id: str
    workspace_id: str
    connection_id: str
    cycle_id: str
    snapshot_id: str
    graph_revision: str
    policy_bundle_id: str
    policy_bundle_hash: str
    ranking_pipeline_hash: str
    engine_version: str
    normalization_profile_version: str
    causation_id: str
    correlation_id: str
    outbox_id: str
    outbox_idempotency_key: str
    computed_at_iso: str
    changed_item_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Reject blank identities and canonicalize changed-item identities."""
        required = (
            self.tenant_id,
            self.workspace_id,
            self.connection_id,
            self.cycle_id,
            self.snapshot_id,
            self.graph_revision,
            self.policy_bundle_id,
            self.policy_bundle_hash,
            self.ranking_pipeline_hash,
            self.engine_version,
            self.normalization_profile_version,
            self.causation_id,
            self.correlation_id,
            self.outbox_id,
            self.outbox_idempotency_key,
            self.computed_at_iso,
        )
        if any(not value.strip() for value in required):
            msg = "ingestion identities, versions, hashes, and time are required"
            raise ValueError(msg)
        object.__setattr__(
            self,
            "changed_item_ids",
            tuple(sorted(set(self.changed_item_ids))),
        )


@dataclass(frozen=True, slots=True)
class IngestionReceipt:
    """Result of one full or incremental source ingestion cycle."""

    cycle_id: str
    source_revision: str
    decision_set_hash: str
    affected_item_ids: tuple[str, ...]
    idempotent_replay: bool


class IngestionStateReader(Protocol):
    """Read-only state required to merge one incremental source update."""

    async def current_source_revision(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        connection_id: str,
    ) -> str | None:
        """Return the currently committed source revision, if any."""
        ...

    async def load_source_items(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        connection_id: str,
    ) -> tuple[SourceItem, ...]:
        """Return the latest committed source item versions."""
        ...
