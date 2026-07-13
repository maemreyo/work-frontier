from __future__ import annotations

from datetime import UTC, datetime

from work_frontier.domain.frontier import (
    Comparator,
    EngineEnvelope,
    FrontierItemInput,
    FrontierSnapshot,
    RankingPipeline,
    WorkClass,
    solve_frontier,
)


def test_five_hundred_replays_are_bit_for_bit_identical() -> None:
    pipeline = RankingPipeline((Comparator.AGE_DESC, Comparator.STABLE_ID))
    for index in range(500):
        envelope = EngineEnvelope(
            workspace_id="workspace",
            normalized_snapshot_id=f"snapshot-{index}",
            normalized_snapshot_hash=f"{index:064x}",
            source_revision_set=(("source", f"revision-{index}"),),
            graph_revision=f"graph-{index}",
            policy_bundle_id="policy",
            policy_bundle_hash="b" * 64,
            ranking_pipeline_hash="c" * 64,
            engine_version="engine-1",
            normalization_profile_version="profile-1",
            computed_at=datetime(2026, 7, 13, tzinfo=UTC),
            causation_id=f"cause-{index}",
            correlation_id=f"correlation-{index}",
        )
        item = FrontierItemInput(
            item_id=f"item-{index:05d}",
            program_id=None,
            title="Replay",
            description=None,
            work_type="test",
            labels=(),
            lifecycle="planned",
            completion="incomplete",
            program_priority=0,
            work_class=WorkClass.IMPLEMENTATION,
            downstream_unlock_count=0,
            age_seconds=index,
            hard_blockers_complete=True,
            entry_gates_pass=True,
            authority_safe=True,
            field_authority=(("title", "authoritative"),),
            gate_states=(),
            incomplete_hard_blockers=(),
            gate_dependencies=(),
            active_attention_items=(),
        )
        snapshot = FrontierSnapshot(envelope, (item,), pipeline)
        assert (
            solve_frontier(snapshot).canonical_json()
            == solve_frontier(snapshot).canonical_json()
        )
