from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from work_frontier.adapters.reference_539 import (
    load_reference_corpus,
    reference_source_items,
)
from work_frontier.application.ingestion import build_ingestion_snapshot
from work_frontier.application.ports.ingestion import IngestionCommand
from work_frontier.domain.frontier import solve_frontier

ROOT = Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "539"
_HASH = "a" * 64


def command(*, changed: tuple[str, ...] = ()) -> IngestionCommand:
    return IngestionCommand(
        tenant_id="tenant",
        workspace_id="workspace",
        connection_id="github",
        cycle_id="cycle",
        snapshot_id="snapshot",
        graph_revision="graph-539",
        policy_bundle_id="policy-539",
        policy_bundle_hash=_HASH,
        ranking_pipeline_hash=_HASH,
        engine_version="engine-1",
        normalization_profile_version="github-539-v1",
        causation_id="cause",
        correlation_id="correlation",
        outbox_id="outbox",
        outbox_idempotency_key="539-replay",
        computed_at_iso="2026-07-13T00:00:00+00:00",
        changed_item_ids=changed,
    )


def test_539_replay_matches_golden_and_close_reopen_updates_frontier() -> None:
    items = reference_source_items(load_reference_corpus(ROOT))
    initial = build_ingestion_snapshot(command(), items, source_revision="observed")
    first = solve_frontier(initial.snapshot)
    second = solve_frontier(initial.snapshot)
    golden = (ROOT / "decision-set.sha256").read_text(encoding="utf-8").strip()
    assert first.payload_hash == golden
    assert first.canonical_json() == second.canonical_json()

    closed_items = tuple(
        replace(
            item,
            state="closed",
            revision=f"{item.revision}:closed",
        )
        if item.item_id == "538"
        else item
        for item in items
    )
    closed = solve_frontier(
        build_ingestion_snapshot(
            command(changed=("538",)),
            closed_items,
            source_revision="closed-538",
        ).snapshot
    )
    assert closed.payload_hash != first.payload_hash

    reopened_items = tuple(
        replace(
            item,
            state="open",
            revision=f"{item.revision}:reopened",
        )
        if item.item_id == "538"
        else item
        for item in closed_items
    )
    reopened = solve_frontier(
        build_ingestion_snapshot(
            command(changed=("538",)),
            reopened_items,
            source_revision="reopened-538",
        ).snapshot
    )
    first_semantics = tuple((record.item_id, record.ready) for record in first.records)
    reopened_semantics = tuple(
        (record.item_id, record.ready) for record in reopened.records
    )
    assert reopened_semantics == first_semantics
