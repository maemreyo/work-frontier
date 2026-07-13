"""Application service that solves and atomically persists one decision cycle."""

from __future__ import annotations

import hashlib
import json

from work_frontier.application.ports.decision_cycles import (
    DecisionCycleCommand,
    DecisionCycleReceipt,
    DecisionCycleRepository,
    DecisionCycleWrite,
    DecisionRecordDocument,
    NormalizedSnapshotDocument,
    SourceVersionDocument,
)
from work_frontier.domain.frontier import FrontierSnapshot, solve_frontier


async def execute_decision_cycle(
    command: DecisionCycleCommand,
    snapshot: FrontierSnapshot,
    repository: DecisionCycleRepository,
    *,
    source_versions: tuple[SourceVersionDocument, ...],
    normalized_snapshot: NormalizedSnapshotDocument,
) -> DecisionCycleReceipt:
    """Solve one identified snapshot and persist the immutable set atomically."""
    envelope = snapshot.envelope
    if envelope.workspace_id != command.workspace_id:
        msg = "decision snapshot workspace does not match the persistence command"
        raise ValueError(msg)
    if envelope.normalized_snapshot_id != command.snapshot_id:
        msg = "decision snapshot identity does not match the persistence command"
        raise ValueError(msg)
    if envelope.normalized_snapshot_hash != command.snapshot_hash:
        msg = "decision snapshot hash does not match the persistence command"
        raise ValueError(msg)
    if envelope.graph_revision != command.graph_revision:
        msg = "decision graph revision does not match the persistence command"
        raise ValueError(msg)
    if envelope.policy_bundle_hash != command.policy_bundle_hash:
        msg = "decision policy hash does not match the persistence command"
        raise ValueError(msg)

    solved = solve_frontier(snapshot)
    decisions = tuple(
        DecisionRecordDocument(
            decision_id=record.decision_id,
            item_id=record.item_id,
            payload=record.canonical(),
            payload_hash=_canonical_hash(record.canonical()),
        )
        for record in solved.records
    )
    write = DecisionCycleWrite(
        command=command,
        source_versions=source_versions,
        normalized_snapshot=normalized_snapshot,
        decisions=decisions,
        decision_set_hash=solved.payload_hash,
        recommended_item_id=(
            None if solved.recommended_next is None else solved.recommended_next.item_id
        ),
    )
    return await repository.persist(write)


def _canonical_hash(value: dict[str, object]) -> str:
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    return hashlib.sha256(payload).hexdigest()
