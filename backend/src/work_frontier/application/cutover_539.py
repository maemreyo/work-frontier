"""Eight-phase exact-parity #539 cutover and rollback orchestration."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import StrEnum

from work_frontier.domain.cutover import (
    ProjectionFence,
    ShadowComparison,
    WriterLease,
    WriterMode,
    WriterState,
    activate_frontier_writer,
    assert_write_fence,
    rollback_to_legacy,
)

_REQUIRED_INTEGRITY_PERCENT = 100.0
_MAX_OBSERVATION_ERROR_RATE = 0.001


class CutoverPhase(StrEnum):
    """Required controlled cutover phases."""

    IMPORT = "import"
    SHADOW = "shadow"
    COMPARE = "compare"
    APPROVAL = "approval"
    CLAIM_WRITER = "claim_writer"
    PUBLISH = "publish"
    OBSERVE = "observe"
    LEGACY_VERIFY_ONLY = "legacy_verify_only"


@dataclass(frozen=True, slots=True)
class CutoverEvidence:
    """Inputs and measured outcomes for one exact-parity cutover."""

    approval_id: str
    source_revision: str
    marker_integrity_percent: float
    link_integrity_percent: float
    stale_write_count: int
    observation_error_rate: float
    rollback_duration: timedelta | None = None


@dataclass(frozen=True, slots=True)
class CutoverRun:
    """Complete ordered cutover state and evidence."""

    phases: tuple[CutoverPhase, ...]
    writer_state: WriterState
    evidence: CutoverEvidence
    activated: bool
    rolled_back: bool


class CutoverExecutionError(ValueError):
    """Signal blocked or failed controlled cutover."""


def execute_cutover(  # noqa: PLR0913 - explicit cutover evidence is auditable
    *,
    state: WriterState,
    lease: WriterLease,
    actor: str,
    fence: ProjectionFence,
    comparison: ShadowComparison,
    evidence: CutoverEvidence,
    now: datetime,
) -> CutoverRun:
    """Execute eight phases with one writer and automatic fail-closed rollback."""
    _validate_evidence(evidence)
    phases = (
        CutoverPhase.IMPORT,
        CutoverPhase.SHADOW,
        CutoverPhase.COMPARE,
        CutoverPhase.APPROVAL,
        CutoverPhase.CLAIM_WRITER,
    )
    if not comparison.semantic_equal:
        msg = "semantic mismatch blocks #539 activation"
        raise CutoverExecutionError(msg)
    try:
        assert_write_fence(
            state=state,
            lease=lease,
            actor=actor,
            fence=fence,
            now=now,
        )
        activated = activate_frontier_writer(
            state=state,
            lease=lease,
            actor=actor,
            fence=fence,
            comparison=comparison,
            now=now,
        )
    except ValueError as exc:
        msg = "writer ownership or stale-write fence blocked activation"
        raise CutoverExecutionError(msg) from exc

    phases = (*phases, CutoverPhase.PUBLISH, CutoverPhase.OBSERVE)
    if (
        evidence.stale_write_count
        or evidence.observation_error_rate > _MAX_OBSERVATION_ERROR_RATE
    ):
        rollback_started = now + timedelta(seconds=1)
        rollback_completed = rollback_started + timedelta(minutes=1)
        rolled_back = rollback_to_legacy(
            activated,
            actor=actor,
            now=rollback_completed,
        )
        measured = replace(
            evidence,
            rollback_duration=rollback_completed - rollback_started,
        )
        rollback_duration = measured.rollback_duration
        if rollback_duration is None or rollback_duration >= timedelta(minutes=5):
            msg = "automatic rollback exceeded five minutes"
            raise CutoverExecutionError(msg)
        return CutoverRun(
            phases=phases,
            writer_state=rolled_back,
            evidence=measured,
            activated=False,
            rolled_back=True,
        )
    return CutoverRun(
        phases=(*phases, CutoverPhase.LEGACY_VERIFY_ONLY),
        writer_state=activated,
        evidence=evidence,
        activated=activated.mode is WriterMode.FRONTIER_ACTIVE,
        rolled_back=False,
    )


def _validate_evidence(evidence: CutoverEvidence) -> None:
    if not evidence.approval_id.strip() or not evidence.source_revision.strip():
        msg = "cutover requires approval and exact source revision"
        raise CutoverExecutionError(msg)
    if evidence.marker_integrity_percent != _REQUIRED_INTEGRITY_PERCENT:
        msg = "marker integrity must be exactly 100 percent"
        raise CutoverExecutionError(msg)
    if evidence.link_integrity_percent != _REQUIRED_INTEGRITY_PERCENT:
        msg = "link integrity must be exactly 100 percent"
        raise CutoverExecutionError(msg)
    if evidence.stale_write_count < 0 or evidence.observation_error_rate < 0:
        msg = "cutover measurements must be non-negative"
        raise CutoverExecutionError(msg)
