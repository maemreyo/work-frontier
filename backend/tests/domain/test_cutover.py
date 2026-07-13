from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from work_frontier.domain.cutover import (
    CutoverError,
    ProjectionFence,
    WriterLease,
    WriterMode,
    WriterState,
    activate_frontier_writer,
    compare_shadow,
    rollback_to_legacy,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)


def _state() -> WriterState:
    return WriterState(
        mode=WriterMode.SHADOW,
        active_writer="legacy",
        version=4,
        updated_at=NOW,
    )


def _lease() -> WriterLease:
    return WriterLease(
        owner="operator-1", version=2, expires_at=NOW + timedelta(minutes=5)
    )


def _fence() -> ProjectionFence:
    return ProjectionFence(
        expected_local_version=4,
        current_local_version=4,
        expected_source_revision="rev-9",
        current_source_revision="rev-9",
    )


def test_shadow_comparison_ignores_only_approved_presentation_fields() -> None:
    comparison = compare_shadow(
        {"ready": True, "label": "legacy-copy"},
        {"ready": True, "label": "frontier-copy"},
        presentation_only_fields=frozenset({"label"}),
    )
    assert comparison.semantic_equal is True
    assert comparison.approved_presentation_differences == ("label",)


def test_semantic_mismatch_blocks_activation() -> None:
    comparison = compare_shadow({"ready": True}, {"ready": False})
    with pytest.raises(CutoverError, match="semantic parity"):
        _ = activate_frontier_writer(
            state=_state(),
            lease=_lease(),
            actor="operator-1",
            fence=_fence(),
            comparison=comparison,
            now=NOW,
        )


def test_stale_source_revision_and_missing_lease_fail_closed() -> None:
    comparison = compare_shadow({"ready": True}, {"ready": True})
    stale = ProjectionFence(4, 4, "rev-8", "rev-9")
    with pytest.raises(CutoverError, match="source revision"):
        _ = activate_frontier_writer(
            state=_state(),
            lease=_lease(),
            actor="operator-1",
            fence=stale,
            comparison=comparison,
            now=NOW,
        )
    with pytest.raises(CutoverError, match="writer lease"):
        _ = activate_frontier_writer(
            state=_state(),
            lease=None,
            actor="operator-1",
            fence=_fence(),
            comparison=comparison,
            now=NOW,
        )


def test_activation_and_rollback_preserve_single_writer() -> None:
    active = activate_frontier_writer(
        state=_state(),
        lease=_lease(),
        actor="operator-1",
        fence=_fence(),
        comparison=compare_shadow({"ready": True}, {"ready": True}),
        now=NOW,
    )
    assert active.mode is WriterMode.FRONTIER_ACTIVE
    assert active.active_writer == "frontier"
    assert active.version == 5

    rolled_back = rollback_to_legacy(active, actor="operator-1", now=NOW)
    assert rolled_back.mode is WriterMode.LEGACY_ACTIVE
    assert rolled_back.active_writer == "legacy"
    assert rolled_back.version == 6
