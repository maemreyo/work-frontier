from __future__ import annotations

from dataclasses import replace

from work_frontier.application.ingestion import build_ingestion_snapshot
from work_frontier.application.ports.connections import SourceItem
from work_frontier.application.ports.ingestion import IngestionCommand
from work_frontier.domain.frontier import solve_frontier

_HASH = "a" * 64
_CASES = 10_000


def command(*, changed: tuple[str, ...] = ()) -> IngestionCommand:
    return IngestionCommand(
        tenant_id="tenant",
        workspace_id="workspace",
        connection_id="connection",
        cycle_id="cycle",
        snapshot_id="snapshot",
        graph_revision="graph",
        policy_bundle_id="policy",
        policy_bundle_hash=_HASH,
        ranking_pipeline_hash=_HASH,
        engine_version="engine",
        normalization_profile_version="profile",
        causation_id="cause",
        correlation_id="correlation",
        outbox_id="outbox",
        outbox_idempotency_key="cycle",
        computed_at_iso="2026-07-13T00:00:00+00:00",
        changed_item_ids=changed,
    )


def item(number: int, seed: int) -> SourceItem:
    state = "closed" if seed & (1 << number) else "open"
    blockers = () if number == 0 else (str(number - 1),)
    return SourceItem(
        source_id="fixture",
        item_id=str(number),
        revision=f"r-{seed}-{number}",
        title=f"Item {number}",
        body="",
        state=state,
        labels=(),
        updated_at="2026-07-12T00:00:00+00:00",
        raw=(("number", number),),
        policy_blockers=blockers,
    )


def test_incremental_and_full_projection_converge_for_10000_inputs() -> None:
    for seed in range(_CASES):
        values = tuple(item(number, seed) for number in range(4))
        full = build_ingestion_snapshot(
            command(),
            values,
            source_revision=f"revision-{seed}",
        )
        incremental = build_ingestion_snapshot(
            command(changed=(str(seed % 4),)),
            tuple(reversed(values)),
            source_revision=f"revision-{seed}",
        )
        full_result = solve_frontier(full.snapshot)
        incremental_result = solve_frontier(incremental.snapshot)
        assert full.normalized_snapshot.payload_hash == (
            incremental.normalized_snapshot.payload_hash
        )
        assert full_result.canonical_json() == incremental_result.canonical_json()


def test_altered_source_identity_changes_decision_payload() -> None:
    values = tuple(item(number, 0) for number in range(2))
    first = build_ingestion_snapshot(command(), values, source_revision="revision-1")
    changed = tuple(
        replace(value, revision=f"changed-{value.item_id}") for value in values
    )
    second = build_ingestion_snapshot(command(), changed, source_revision="revision-2")
    assert (
        solve_frontier(first.snapshot).payload_hash
        != solve_frontier(second.snapshot).payload_hash
    )
