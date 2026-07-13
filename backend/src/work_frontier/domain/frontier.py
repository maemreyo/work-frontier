"""Pure deterministic readiness, ranking, and DecisionRecord-set engine."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from functools import cached_property
from typing import Final

_HASH_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")
_READY_LIFECYCLES: Final = frozenset({"planned", "active"})
_CROCKFORD: Final = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


class WorkClass(StrEnum):
    """Canonical ranking work classes in descending priority order."""

    FOUNDATION = "foundation"
    IMPLEMENTATION = "implementation"
    CERTIFICATION = "certification"


class Comparator(StrEnum):
    """Supported deterministic lexicographic comparators."""

    PROGRAM_PRIORITY = "program_priority"
    WORK_CLASS = "work_class"
    DOWNSTREAM_UNLOCK_COUNT_DESC = "downstream_unlock_count_desc"
    AGE_DESC = "age_desc"
    STABLE_ID = "stable_id"


_WORK_CLASS_ORDER: Final = {
    WorkClass.FOUNDATION: 0,
    WorkClass.IMPLEMENTATION: 1,
    WorkClass.CERTIFICATION: 2,
}


@dataclass(frozen=True, slots=True)
class EngineEnvelope:
    """Complete immutable reproducibility identity for one engine cycle."""

    workspace_id: str
    normalized_snapshot_id: str
    normalized_snapshot_hash: str
    source_revision_set: tuple[tuple[str, str], ...]
    graph_revision: str
    policy_bundle_id: str
    policy_bundle_hash: str
    ranking_pipeline_hash: str
    engine_version: str
    normalization_profile_version: str
    computed_at: datetime
    causation_id: str
    correlation_id: str

    def __post_init__(self) -> None:
        """Validate and canonicalize the reproducibility envelope."""
        required = (
            self.workspace_id,
            self.normalized_snapshot_id,
            self.graph_revision,
            self.policy_bundle_id,
            self.engine_version,
            self.normalization_profile_version,
            self.causation_id,
            self.correlation_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("engine envelope identities must not be blank")
        if self.computed_at.tzinfo is None or self.computed_at.utcoffset() is None:
            raise ValueError("computed_at must be timezone-aware")
        for value in (
            self.normalized_snapshot_hash,
            self.policy_bundle_hash,
            self.ranking_pipeline_hash,
        ):
            if _HASH_PATTERN.fullmatch(value) is None:
                raise ValueError("engine envelope hashes must be lowercase SHA-256")
        revisions = tuple(sorted(self.source_revision_set))
        if not revisions or len(revisions) != len(set(revisions)):
            raise ValueError("source_revision_set must be non-empty and unique")
        if any(
            not source.strip() or not revision.strip() for source, revision in revisions
        ):
            raise ValueError("source revisions must contain non-blank identities")
        object.__setattr__(self, "source_revision_set", revisions)

    def canonical(self) -> dict[str, object]:
        """Return a JSON-compatible canonical envelope."""
        return {
            "causation_id": self.causation_id,
            "computed_at": self.computed_at.isoformat(),
            "correlation_id": self.correlation_id,
            "engine_version": self.engine_version,
            "graph_revision": self.graph_revision,
            "normalization_profile_version": self.normalization_profile_version,
            "normalized_snapshot_hash": self.normalized_snapshot_hash,
            "normalized_snapshot_id": self.normalized_snapshot_id,
            "policy_bundle_hash": self.policy_bundle_hash,
            "policy_bundle_id": self.policy_bundle_id,
            "ranking_pipeline_hash": self.ranking_pipeline_hash,
            "source_revision_set": dict(self.source_revision_set),
            "workspace_id": self.workspace_id,
        }


@dataclass(frozen=True, slots=True)
class RankingPipeline:
    """Ordered deterministic comparator configuration."""

    comparators: tuple[Comparator, ...]

    def __post_init__(self) -> None:
        """Require a unique total-order pipeline with stable ID last."""
        if not self.comparators:
            raise ValueError("ranking pipeline must not be empty")
        if len(self.comparators) != len(set(self.comparators)):
            raise ValueError("ranking comparators must be unique")
        if self.comparators[-1] is not Comparator.STABLE_ID:
            raise ValueError("stable_id must be the final comparator")


@dataclass(frozen=True, slots=True)
class FrontierItemInput:
    """Item-local immutable engine input; no global lookups are permitted."""

    item_id: str
    program_id: str | None
    title: str
    description: str | None
    work_type: str
    labels: tuple[str, ...]
    lifecycle: str
    completion: str
    program_priority: int
    work_class: WorkClass
    downstream_unlock_count: int
    age_seconds: int
    hard_blockers_complete: bool
    entry_gates_pass: bool
    authority_safe: bool
    field_authority: tuple[tuple[str, str], ...]
    gate_states: tuple[tuple[str, str], ...]
    incomplete_hard_blockers: tuple[str, ...]
    gate_dependencies: tuple[str, ...]
    active_attention_items: tuple[str, ...]

    def __post_init__(self) -> None:
        """Validate and canonicalize item-local inputs."""
        if (
            not self.item_id.strip()
            or not self.title.strip()
            or not self.work_type.strip()
        ):
            raise ValueError("item identity, title, and work_type are required")
        if self.program_priority < 0:
            raise ValueError("program_priority must be non-negative")
        if self.downstream_unlock_count < 0 or self.age_seconds < 0:
            raise ValueError("fan-out and age must be non-negative")
        object.__setattr__(self, "labels", tuple(sorted(set(self.labels))))
        object.__setattr__(self, "field_authority", tuple(sorted(self.field_authority)))
        object.__setattr__(self, "gate_states", tuple(sorted(self.gate_states)))
        object.__setattr__(
            self,
            "incomplete_hard_blockers",
            tuple(sorted(set(self.incomplete_hard_blockers))),
        )
        object.__setattr__(
            self,
            "gate_dependencies",
            tuple(sorted(set(self.gate_dependencies))),
        )
        object.__setattr__(
            self,
            "active_attention_items",
            tuple(sorted(set(self.active_attention_items))),
        )


@dataclass(frozen=True, slots=True)
class FrontierSnapshot:
    """Pure solve input containing the full identified cycle."""

    envelope: EngineEnvelope
    items: tuple[FrontierItemInput, ...]
    pipeline: RankingPipeline

    def __post_init__(self) -> None:
        """Require unique item identities and canonical item ordering."""
        ordered = tuple(sorted(self.items, key=lambda item: item.item_id))
        ids = tuple(item.item_id for item in ordered)
        if len(ids) != len(set(ids)):
            raise ValueError("frontier item IDs must be unique")
        object.__setattr__(self, "items", ordered)


@dataclass(frozen=True, slots=True)
class ComparatorTrace:
    """Canonical item-local comparator input and tie-break position."""

    comparator: Comparator
    input_value: str | int
    outcome: str
    tie_break_position: int
    detail: str

    def canonical(self) -> dict[str, object]:
        """Return JSON-compatible comparator trace data."""
        return {
            "comparator": self.comparator.value,
            "detail": self.detail,
            "input": self.input_value,
            "outcome": self.outcome,
            "tie_break_position": self.tie_break_position,
        }


@dataclass(frozen=True, slots=True)
class DecisionRecordOutput:
    """Immutable per-item engine decision with complete reproducibility context."""

    decision_id: str
    envelope: EngineEnvelope
    item_id: str
    program_id: str | None
    title: str
    description: str | None
    work_type: str
    labels: tuple[str, ...]
    lifecycle: str
    completion: str
    ready: bool
    ranking_position: int | None
    ranking_rationale: tuple[ComparatorTrace, ...]
    readiness_reasons: tuple[str, ...]
    gates: tuple[tuple[str, str], ...]
    blocked_by: tuple[str, ...]
    gate_dependencies: tuple[str, ...]
    blocks_count: int
    active_attention_items: tuple[str, ...]
    field_authority: tuple[tuple[str, str], ...]

    def canonical(self) -> dict[str, object]:
        """Return the complete canonical decision payload."""
        return {
            **self.envelope.canonical(),
            "active_attention_items": list(self.active_attention_items),
            "blocked_by": list(self.blocked_by),
            "blocks_count": self.blocks_count,
            "completion": self.completion,
            "decision_id": self.decision_id,
            "description": self.description,
            "field_authority": dict(self.field_authority),
            "gate_dependencies": list(self.gate_dependencies),
            "gates": [
                {"gate_id": gate_id, "state": state} for gate_id, state in self.gates
            ],
            "item_id": self.item_id,
            "labels": list(self.labels),
            "lifecycle": self.lifecycle,
            "program_id": self.program_id,
            "ranking_position": self.ranking_position,
            "ranking_rationale": [
                trace.canonical() for trace in self.ranking_rationale
            ],
            "readiness_reasons": list(self.readiness_reasons),
            "ready": self.ready,
            "title": self.title,
            "work_type": self.work_type,
        }


@dataclass(frozen=True, slots=True)
class RecommendedNext:
    """Live projection of the top authoritative ready decision."""

    item_id: str
    decision_id: str
    ranking_position: int
    rationale: tuple[ComparatorTrace, ...]

    def canonical(self) -> dict[str, object]:
        """Return JSON-compatible projection data."""
        return {
            "decision_id": self.decision_id,
            "item_id": self.item_id,
            "ranking_position": self.ranking_position,
            "rationale": [trace.canonical() for trace in self.rationale],
        }


@dataclass(frozen=True)
class DecisionRecordSet:
    """Atomic immutable output for all evaluated items in one engine cycle."""

    records: tuple[DecisionRecordOutput, ...]
    recommended_next: RecommendedNext | None

    @cached_property
    def payload_hash(self) -> str:
        """Return SHA-256 of the canonical output set."""
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @property
    def ready_item_ids(self) -> tuple[str, ...]:
        """Return ranked ready item IDs."""
        return tuple(record.item_id for record in self.records if record.ready)

    def canonical_json(self) -> str:
        """Return stable UTF-8 JSON for replay and hashing."""
        payload = {
            "recommended_next": (
                None
                if self.recommended_next is None
                else self.recommended_next.canonical()
            ),
            "records": [record.canonical() for record in self.records],
        }
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )


def solve_frontier(snapshot: FrontierSnapshot) -> DecisionRecordSet:
    """Solve readiness and ranking without clock, I/O, randomness, global state, or AI."""
    ready_items: list[FrontierItemInput] = []
    reasons_by_item: dict[str, tuple[str, ...]] = {}
    for item in snapshot.items:
        reasons = _readiness_reasons(item)
        reasons_by_item[item.item_id] = reasons
        if reasons == ("ready",):
            ready_items.append(item)

    ranked = tuple(
        sorted(ready_items, key=lambda item: _ranking_key(item, snapshot.pipeline))
    )
    positions = {item.item_id: index for index, item in enumerate(ranked, start=1)}
    record_items = (
        *ranked,
        *(item for item in snapshot.items if item.item_id not in positions),
    )
    records = tuple(
        _decision_record(
            snapshot.envelope,
            snapshot.pipeline,
            item,
            reasons_by_item[item.item_id],
            positions.get(item.item_id),
        )
        for item in record_items
    )
    recommended = None
    if records and records[0].ready:
        top = records[0]
        recommended = RecommendedNext(
            item_id=top.item_id,
            decision_id=top.decision_id,
            ranking_position=1,
            rationale=top.ranking_rationale,
        )
    return DecisionRecordSet(records=records, recommended_next=recommended)


def _readiness_reasons(item: FrontierItemInput) -> tuple[str, ...]:
    reasons: list[str] = []
    if item.lifecycle not in _READY_LIFECYCLES:
        reasons.append("lifecycle_not_actionable")
    if not item.hard_blockers_complete:
        reasons.append("incomplete_hard_blocker")
    if not item.entry_gates_pass:
        reasons.append("entry_gate_blocked")
    if not item.authority_safe:
        reasons.append("unsafe_authority")
    return tuple(reasons) if reasons else ("ready",)


def _ranking_key(
    item: FrontierItemInput, pipeline: RankingPipeline
) -> tuple[object, ...]:
    values: list[object] = []
    for comparator in pipeline.comparators:
        if comparator is Comparator.PROGRAM_PRIORITY:
            values.append(-item.program_priority)
        elif comparator is Comparator.WORK_CLASS:
            values.append(_WORK_CLASS_ORDER[item.work_class])
        elif comparator is Comparator.DOWNSTREAM_UNLOCK_COUNT_DESC:
            values.append(-item.downstream_unlock_count)
        elif comparator is Comparator.AGE_DESC:
            values.append(-item.age_seconds)
        else:
            values.append(item.item_id)
    return tuple(values)


def _decision_record(
    envelope: EngineEnvelope,
    pipeline: RankingPipeline,
    item: FrontierItemInput,
    reasons: tuple[str, ...],
    ranking_position: int | None,
) -> DecisionRecordOutput:
    identity_payload = json.dumps(
        {**envelope.canonical(), "item_id": item.item_id},
        sort_keys=True,
        separators=(",", ":"),
    )
    decision_id = _deterministic_ulid(identity_payload)
    traces = tuple(
        _comparator_trace(item, comparator, index)
        for index, comparator in enumerate(pipeline.comparators, start=1)
    )
    return DecisionRecordOutput(
        decision_id=decision_id,
        envelope=envelope,
        item_id=item.item_id,
        program_id=item.program_id,
        title=item.title,
        description=item.description,
        work_type=item.work_type,
        labels=item.labels,
        lifecycle=item.lifecycle,
        completion=item.completion,
        ready=reasons == ("ready",),
        ranking_position=ranking_position,
        ranking_rationale=traces,
        readiness_reasons=reasons,
        gates=item.gate_states,
        blocked_by=item.incomplete_hard_blockers,
        gate_dependencies=item.gate_dependencies,
        blocks_count=item.downstream_unlock_count,
        active_attention_items=item.active_attention_items,
        field_authority=item.field_authority,
    )


def _comparator_trace(
    item: FrontierItemInput,
    comparator: Comparator,
    position: int,
) -> ComparatorTrace:
    if comparator is Comparator.PROGRAM_PRIORITY:
        value: str | int = item.program_priority
    elif comparator is Comparator.WORK_CLASS:
        value = item.work_class.value
    elif comparator is Comparator.DOWNSTREAM_UNLOCK_COUNT_DESC:
        value = item.downstream_unlock_count
    elif comparator is Comparator.AGE_DESC:
        value = item.age_seconds
    else:
        value = item.item_id
    return ComparatorTrace(
        comparator=comparator,
        input_value=value,
        outcome="selected",
        tie_break_position=position,
        detail=f"{comparator.value}={value}",
    )


def _deterministic_ulid(value: str) -> str:
    """Derive a canonical ULID-shaped immutable ID from identified inputs."""
    numeric = int.from_bytes(hashlib.sha256(value.encode()).digest()[:16], "big")
    return "".join(_CROCKFORD[(numeric >> shift) & 31] for shift in range(125, -1, -5))
