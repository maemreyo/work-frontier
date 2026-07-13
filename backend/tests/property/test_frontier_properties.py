from __future__ import annotations

from dataclasses import replace
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

_CASES = 10_000


def _envelope() -> EngineEnvelope:
    return EngineEnvelope(
        workspace_id="ws-1",
        normalized_snapshot_id="snapshot-1",
        normalized_snapshot_hash="a" * 64,
        source_revision_set=(("github", "revision-1"),),
        graph_revision="graph-1",
        policy_bundle_id="policy-1",
        policy_bundle_hash="b" * 64,
        ranking_pipeline_hash="c" * 64,
        engine_version="engine-1",
        normalization_profile_version="profile-1",
        computed_at=datetime(2026, 7, 13, tzinfo=UTC),
        causation_id="cause-1",
        correlation_id="correlation-1",
    )


def _pipeline() -> RankingPipeline:
    return RankingPipeline(
        (
            Comparator.PROGRAM_PRIORITY,
            Comparator.WORK_CLASS,
            Comparator.DOWNSTREAM_UNLOCK_COUNT_DESC,
            Comparator.AGE_DESC,
            Comparator.STABLE_ID,
        )
    )


def _item(index: int, *, blocked: bool = False) -> FrontierItemInput:
    return FrontierItemInput(
        item_id=f"item-{index:05d}",
        program_id=f"program-{index % 7}",
        title=f"Item {index}",
        description=None,
        work_type="feature",
        labels=(f"label-{index % 3}",),
        lifecycle="planned",
        completion="incomplete",
        program_priority=index % 11,
        work_class=(
            WorkClass.FOUNDATION,
            WorkClass.IMPLEMENTATION,
            WorkClass.CERTIFICATION,
        )[index % 3],
        downstream_unlock_count=index % 17,
        age_seconds=index * 3,
        hard_blockers_complete=not blocked,
        entry_gates_pass=True,
        authority_safe=True,
        field_authority=(("title", "authoritative"),),
        gate_states=(),
        incomplete_hard_blockers=("blocker",) if blocked else (),
        gate_dependencies=(),
        active_attention_items=(),
    )


def test_ten_thousand_inputs_are_ordering_invariant() -> None:
    items = tuple(_item(index) for index in range(_CASES))
    forward = solve_frontier(FrontierSnapshot(_envelope(), items, _pipeline()))
    reverse = solve_frontier(
        FrontierSnapshot(_envelope(), tuple(reversed(items)), _pipeline())
    )
    assert forward.payload_hash == reverse.payload_hash
    assert forward.ready_item_ids == reverse.ready_item_ids


def test_ten_thousand_open_blocker_mutations_never_grow_frontier() -> None:
    base_items = tuple(_item(index) for index in range(_CASES))
    blocked_items = tuple(
        replace(item, hard_blockers_complete=False, incomplete_hard_blockers=("x",))
        if index % 5 == 0
        else item
        for index, item in enumerate(base_items)
    )
    base = solve_frontier(FrontierSnapshot(_envelope(), base_items, _pipeline()))
    mutated = solve_frontier(FrontierSnapshot(_envelope(), blocked_items, _pipeline()))
    assert set(mutated.ready_item_ids) < set(base.ready_item_ids)


def test_reproducibility_identity_mutation_changes_hash() -> None:
    snapshot = FrontierSnapshot(_envelope(), (_item(1),), _pipeline())
    first = solve_frontier(snapshot)
    second = solve_frontier(
        replace(snapshot, envelope=replace(_envelope(), graph_revision="graph-2"))
    )
    assert first.payload_hash != second.payload_hash
