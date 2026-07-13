"""Exclusive projection-writer cutover and rollback invariants."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping
    from datetime import datetime


class CutoverError(ValueError):
    """Signal a fail-closed writer ownership or parity violation."""


class WriterMode(StrEnum):
    """Exclusive external projection writer states."""

    LEGACY_ACTIVE = "legacy_active"
    SHADOW = "shadow"
    FRONTIER_ACTIVE = "frontier_active"


@dataclass(frozen=True, slots=True)
class WriterState:
    """Versioned exclusive writer state for one workspace."""

    mode: WriterMode
    active_writer: str
    version: int
    updated_at: datetime

    def __post_init__(self) -> None:
        """Validate state identity, version, timestamp, and exclusivity."""
        _require_aware(self.updated_at, "updated_at")
        if self.version < 0:
            msg = "writer state version must be non-negative"
            raise CutoverError(msg)
        expected_writer = (
            "frontier" if self.mode is WriterMode.FRONTIER_ACTIVE else "legacy"
        )
        if self.active_writer != expected_writer:
            msg = "writer mode must name exactly one matching active writer"
            raise CutoverError(msg)


@dataclass(frozen=True, slots=True)
class WriterLease:
    """Short-lived exclusive authority to change or use writer state."""

    owner: str
    version: int
    expires_at: datetime

    def __post_init__(self) -> None:
        """Validate lease owner, version, and expiry timestamp."""
        _require_aware(self.expires_at, "expires_at")
        if not self.owner.strip() or self.version < 1:
            msg = "writer lease requires an owner and positive version"
            raise CutoverError(msg)


@dataclass(frozen=True, slots=True)
class ProjectionFence:
    """Local projection and exact source-revision compare-and-swap fence."""

    expected_local_version: int
    current_local_version: int
    expected_source_revision: str
    current_source_revision: str


@dataclass(frozen=True, slots=True)
class ShadowComparison:
    """Canonical semantic parity result produced without external writes."""

    semantic_equal: bool
    semantic_differences: tuple[str, ...]
    approved_presentation_differences: tuple[str, ...]
    legacy_canonical: str
    frontier_canonical: str


def compare_shadow(
    legacy: Mapping[str, object],
    frontier: Mapping[str, object],
    *,
    presentation_only_fields: frozenset[str] | None = None,
) -> ShadowComparison:
    """Compare canonical semantics while recording approved presentation drift."""
    presentation_fields = presentation_only_fields or frozenset()
    all_keys = tuple(sorted(set(legacy) | set(frontier)))
    presentation_differences = tuple(
        key
        for key in all_keys
        if key in presentation_fields and legacy.get(key) != frontier.get(key)
    )
    semantic_differences = tuple(
        key
        for key in all_keys
        if key not in presentation_fields and legacy.get(key) != frontier.get(key)
    )
    semantic_legacy = {
        key: legacy[key] for key in sorted(legacy) if key not in presentation_fields
    }
    semantic_frontier = {
        key: frontier[key] for key in sorted(frontier) if key not in presentation_fields
    }
    return ShadowComparison(
        semantic_equal=not semantic_differences,
        semantic_differences=semantic_differences,
        approved_presentation_differences=presentation_differences,
        legacy_canonical=_canonical_json(semantic_legacy),
        frontier_canonical=_canonical_json(semantic_frontier),
    )


def assert_write_fence(
    *,
    state: WriterState,
    lease: WriterLease | None,
    actor: str,
    fence: ProjectionFence,
    now: datetime,
) -> None:
    """Reject absent ownership, stale local state, and stale source input."""
    _require_aware(now, "now")
    if lease is None or lease.owner != actor or now >= lease.expires_at:
        msg = "valid exclusive writer lease is required"
        raise CutoverError(msg)
    if fence.expected_local_version != state.version:
        msg = "expected local projection version does not match writer state"
        raise CutoverError(msg)
    if fence.current_local_version != fence.expected_local_version:
        msg = "local projection version changed before write"
        raise CutoverError(msg)
    if fence.expected_source_revision != fence.current_source_revision:
        msg = "exact source revision changed before write"
        raise CutoverError(msg)


def activate_frontier_writer(  # noqa: PLR0913 - explicit cutover fences are auditable
    *,
    state: WriterState,
    lease: WriterLease | None,
    actor: str,
    fence: ProjectionFence,
    comparison: ShadowComparison,
    now: datetime,
) -> WriterState:
    """Activate Work Frontier only after exact shadow parity and fencing."""
    if state.mode is not WriterMode.SHADOW:
        msg = "frontier activation requires shadow mode"
        raise CutoverError(msg)
    if not comparison.semantic_equal:
        msg = "semantic parity is required before frontier activation"
        raise CutoverError(msg)
    assert_write_fence(state=state, lease=lease, actor=actor, fence=fence, now=now)
    return WriterState(
        mode=WriterMode.FRONTIER_ACTIVE,
        active_writer="frontier",
        version=state.version + 1,
        updated_at=now,
    )


def rollback_to_legacy(
    state: WriterState,
    *,
    actor: str,
    now: datetime,
) -> WriterState:
    """Restore the sole legacy writer through an explicit audited command."""
    _require_aware(now, "now")
    if not actor.strip():
        msg = "rollback actor is required"
        raise CutoverError(msg)
    if state.mode is WriterMode.LEGACY_ACTIVE:
        return replace(state, updated_at=now)
    return WriterState(
        mode=WriterMode.LEGACY_ACTIVE,
        active_writer="legacy",
        version=state.version + 1,
        updated_at=now,
    )


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        msg = f"{field} must be timezone-aware"
        raise CutoverError(msg)
