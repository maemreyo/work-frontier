from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.application.cutover_539 import (
    CutoverEvidence,
    CutoverExecutionError,
    CutoverPhase,
    execute_cutover,
)
from work_frontier.domain.cutover import (
    ProjectionFence,
    ShadowComparison,
    WriterLease,
    WriterMode,
    WriterState,
    compare_shadow,
)

type CutoverInputs = tuple[
    datetime,
    WriterState,
    WriterLease,
    ProjectionFence,
    CutoverEvidence,
    ShadowComparison,
]


def inputs() -> CutoverInputs:
    now = datetime(2026, 7, 13, tzinfo=UTC)
    state = WriterState(WriterMode.SHADOW, "legacy", 4, now)
    lease = WriterLease("operator", 1, now + timedelta(minutes=10))
    fence = ProjectionFence(4, 4, "rev-1", "rev-1")
    evidence = CutoverEvidence("approval-1", "rev-1", 100, 100, 0, 0)
    comparison = compare_shadow(
        {"title": "same", "render": "old"},
        {"title": "same", "render": "new"},
        presentation_only_fields=frozenset({"render"}),
    )
    return now, state, lease, fence, evidence, comparison


def test_exact_parity_executes_all_eight_phases() -> None:
    now, state, lease, fence, evidence, comparison = inputs()
    result = execute_cutover(
        state=state,
        lease=lease,
        actor="operator",
        fence=fence,
        comparison=comparison,
        evidence=evidence,
        now=now,
    )
    assert result.activated
    assert not result.rolled_back
    assert result.writer_state.mode is WriterMode.FRONTIER_ACTIVE
    assert result.phases == tuple(CutoverPhase)


def test_semantic_mismatch_blocks_activation() -> None:
    now, state, lease, fence, evidence, _comparison = inputs()
    mismatch = compare_shadow({"title": "old"}, {"title": "new"})
    with pytest.raises(CutoverExecutionError, match="semantic mismatch"):
        _ = execute_cutover(
            state=state,
            lease=lease,
            actor="operator",
            fence=fence,
            comparison=mismatch,
            evidence=evidence,
            now=now,
        )


def test_observation_failure_rolls_back_under_five_minutes() -> None:
    now, state, lease, fence, evidence, comparison = inputs()
    failed = CutoverEvidence(
        evidence.approval_id,
        evidence.source_revision,
        100,
        100,
        stale_write_count=1,
        observation_error_rate=0.002,
    )
    result = execute_cutover(
        state=state,
        lease=lease,
        actor="operator",
        fence=fence,
        comparison=comparison,
        evidence=failed,
        now=now,
    )
    assert result.rolled_back
    assert result.writer_state.mode is WriterMode.LEGACY_ACTIVE
    assert result.evidence.rollback_duration is not None
    assert result.evidence.rollback_duration < timedelta(minutes=5)
