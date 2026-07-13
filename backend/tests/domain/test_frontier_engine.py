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


def envelope() -> EngineEnvelope:
    return EngineEnvelope(
        workspace_id="ws-1",
        normalized_snapshot_id="snap-1",
        normalized_snapshot_hash="a" * 64,
        source_revision_set=(("github", "rev-1"),),
        graph_revision="graph-1",
        policy_bundle_id="policy-1",
        policy_bundle_hash="b" * 64,
        ranking_pipeline_hash="c" * 64,
        engine_version="engine-1",
        normalization_profile_version="profile-1",
        computed_at=datetime(2026, 7, 13, tzinfo=UTC),
        causation_id="cause-1",
        correlation_id="corr-1",
    )


def item(
    item_id: str,
    *,
    priority: int = 0,
    work_class: WorkClass = WorkClass.IMPLEMENTATION,
    fan_out: int = 0,
    age_seconds: int = 0,
    blockers_complete: bool = True,
    entry_gates_pass: bool = True,
    authority_safe: bool = True,
    lifecycle: str = "planned",
) -> FrontierItemInput:
    return FrontierItemInput(
        item_id=item_id,
        program_id=None,
        title=item_id,
        description=None,
        work_type="feature",
        labels=(),
        lifecycle=lifecycle,
        completion="incomplete",
        program_priority=priority,
        work_class=work_class,
        downstream_unlock_count=fan_out,
        age_seconds=age_seconds,
        hard_blockers_complete=blockers_complete,
        entry_gates_pass=entry_gates_pass,
        authority_safe=authority_safe,
        field_authority=(("title", "authoritative"),),
        gate_states=(),
        incomplete_hard_blockers=(),
        gate_dependencies=(),
        active_attention_items=(),
    )


def pipeline() -> RankingPipeline:
    return RankingPipeline(
        comparators=(
            Comparator.PROGRAM_PRIORITY,
            Comparator.WORK_CLASS,
            Comparator.DOWNSTREAM_UNLOCK_COUNT_DESC,
            Comparator.AGE_DESC,
            Comparator.STABLE_ID,
        )
    )


def test_frontier_is_deterministic_and_recommended_next_is_top_ranked() -> None:
    snapshot = FrontierSnapshot(
        envelope=envelope(),
        items=(
            item("item-b", priority=1, fan_out=4),
            item("item-a", priority=2, fan_out=1),
        ),
        pipeline=pipeline(),
    )
    first = solve_frontier(snapshot)
    second = solve_frontier(snapshot)
    assert first.canonical_json() == second.canonical_json()
    assert first.payload_hash == second.payload_hash
    assert first.recommended_next is not None
    assert first.recommended_next.item_id == "item-a"
    assert [record.ranking_position for record in first.records] == [1, 2]


def test_input_order_does_not_change_output() -> None:
    values = (item("item-c"), item("item-a"), item("item-b"))
    first = solve_frontier(FrontierSnapshot(envelope(), values, pipeline()))
    second = solve_frontier(
        FrontierSnapshot(envelope(), tuple(reversed(values)), pipeline())
    )
    assert first.canonical_json() == second.canonical_json()


def test_unsafe_authority_is_localized_to_one_item() -> None:
    result = solve_frontier(
        FrontierSnapshot(
            envelope(),
            (item("safe"), item("unsafe", authority_safe=False)),
            pipeline(),
        )
    )
    by_id = {record.item_id: record for record in result.records}
    assert by_id["safe"].ready is True
    assert by_id["unsafe"].ready is False
    assert by_id["unsafe"].ranking_position is None
    assert "unsafe_authority" in by_id["unsafe"].readiness_reasons


def test_adding_open_blocker_never_grows_frontier() -> None:
    base = solve_frontier(
        FrontierSnapshot(envelope(), (item("a"), item("b")), pipeline())
    )
    mutated = solve_frontier(
        FrontierSnapshot(
            envelope(),
            (item("a"), item("b", blockers_complete=False)),
            pipeline(),
        )
    )
    assert set(mutated.ready_item_ids) <= set(base.ready_item_ids)


def test_identity_change_changes_payload_hash() -> None:
    first = solve_frontier(FrontierSnapshot(envelope(), (item("a"),), pipeline()))
    changed_envelope = replace(envelope(), graph_revision="graph-2")
    second = solve_frontier(
        FrontierSnapshot(changed_envelope, (item("a"),), pipeline())
    )
    assert first.payload_hash != second.payload_hash


def test_golden_decision_record_set_hash_is_stable() -> None:
    result = solve_frontier(
        FrontierSnapshot(
            envelope(),
            (
                item("item-b", priority=1, fan_out=4),
                item("item-a", priority=2, fan_out=1),
            ),
            pipeline(),
        )
    )
    assert (
        result.payload_hash
        == "5cf56da89f02f85cce7f5f9cf4a8940abd4397dc2280a729c4e9d40168fc14a7"
    )
