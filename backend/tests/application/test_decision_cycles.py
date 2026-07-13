from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime

import pytest

from work_frontier.application.decision_cycles import execute_decision_cycle
from work_frontier.application.ports.decision_cycles import (
    DecisionCycleCommand,
    DecisionCycleReceipt,
    DecisionCycleWrite,
    NormalizedSnapshotDocument,
    SourceVersionDocument,
)
from work_frontier.domain.frontier import (
    Comparator,
    EngineEnvelope,
    FrontierItemInput,
    FrontierSnapshot,
    RankingPipeline,
    WorkClass,
)

_HASH = "a" * 64


class RecordingRepository:
    def __init__(self) -> None:
        self.writes: list[DecisionCycleWrite] = []

    async def persist(self, write: DecisionCycleWrite) -> DecisionCycleReceipt:
        self.writes.append(write)
        return DecisionCycleReceipt(
            cycle_id=write.command.cycle_id,
            source_revision=write.command.new_source_revision,
            decision_count=len(write.decisions),
            active_frontier_version=1,
            decision_set_hash=write.decision_set_hash,
        )


def command() -> DecisionCycleCommand:
    return DecisionCycleCommand(
        tenant_id="tenant",
        workspace_id="workspace",
        connection_id="connection",
        cycle_id="cycle",
        expected_source_revision=None,
        new_source_revision="rev-1",
        snapshot_id="snapshot",
        snapshot_hash=_HASH,
        graph_revision="graph-1",
        policy_bundle_hash=_HASH,
        causation_id="cause",
        correlation_id="correlation",
        outbox_id="outbox",
        outbox_idempotency_key="cycle:cycle",
    )


def snapshot() -> FrontierSnapshot:
    return FrontierSnapshot(
        envelope=EngineEnvelope(
            workspace_id="workspace",
            normalized_snapshot_id="snapshot",
            normalized_snapshot_hash=_HASH,
            source_revision_set=(("source", "rev-1"),),
            graph_revision="graph-1",
            policy_bundle_id="policy",
            policy_bundle_hash=_HASH,
            ranking_pipeline_hash=_HASH,
            engine_version="engine-1",
            normalization_profile_version="profile-1",
            computed_at=datetime(2026, 7, 13, tzinfo=UTC),
            causation_id="cause",
            correlation_id="correlation",
        ),
        items=(
            FrontierItemInput(
                item_id="item-1",
                program_id=None,
                title="First",
                description=None,
                work_type="issue",
                labels=(),
                lifecycle="planned",
                completion="source",
                program_priority=1,
                work_class=WorkClass.IMPLEMENTATION,
                downstream_unlock_count=0,
                age_seconds=1,
                hard_blockers_complete=True,
                entry_gates_pass=True,
                authority_safe=True,
                field_authority=(("title", "authoritative"),),
                gate_states=(),
                incomplete_hard_blockers=(),
                gate_dependencies=(),
                active_attention_items=(),
            ),
        ),
        pipeline=RankingPipeline((Comparator.STABLE_ID,)),
    )


def source_versions() -> tuple[SourceVersionDocument, ...]:
    return (
        SourceVersionDocument(
            source_version_id="source-version",
            item_id="item-1",
            source_id="source",
            revision="rev-1",
            payload={"title": "First"},
            payload_hash=_HASH,
        ),
    )


def normalized_snapshot() -> NormalizedSnapshotDocument:
    return NormalizedSnapshotDocument(
        snapshot_id="snapshot",
        payload={"items": []},
        payload_hash=_HASH,
        source_revision_set=(("source", "rev-1"),),
        graph_revision="graph-1",
        profile_version="profile-1",
    )


def test_execute_decision_cycle_passes_one_complete_atomic_write() -> None:
    repository = RecordingRepository()
    receipt = asyncio.run(
        execute_decision_cycle(
            command(),
            snapshot(),
            repository,
            source_versions=source_versions(),
            normalized_snapshot=normalized_snapshot(),
        )
    )
    assert receipt.decision_count == 1
    assert len(repository.writes) == 1
    write = repository.writes[0]
    assert write.source_versions == source_versions()
    assert write.normalized_snapshot == normalized_snapshot()
    assert write.recommended_item_id == "item-1"
    assert write.decisions[0].payload_hash != ""


def test_execute_decision_cycle_rejects_snapshot_identity_mismatch() -> None:
    repository = RecordingRepository()
    bad = replace(command(), snapshot_hash="b" * 64)
    with pytest.raises(ValueError, match="snapshot hash"):
        _ = asyncio.run(
            execute_decision_cycle(
                bad,
                snapshot(),
                repository,
                source_versions=source_versions(),
                normalized_snapshot=normalized_snapshot(),
            )
        )
    assert repository.writes == []
