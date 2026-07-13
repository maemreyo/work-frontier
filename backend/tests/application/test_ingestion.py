from __future__ import annotations

import asyncio
from dataclasses import replace

from work_frontier.adapters.connections.fixture import FixtureAdapter
from work_frontier.application.ingestion import ingest_connection
from work_frontier.application.ports.connections import SourceItem
from work_frontier.application.ports.decision_cycles import (
    DecisionCycleReceipt,
    DecisionCycleWrite,
)
from work_frontier.application.ports.ingestion import IngestionCommand

_HASH = "a" * 64


class State:
    revision: str | None
    items: tuple[SourceItem, ...]

    def __init__(self, revision: str | None, items: tuple[SourceItem, ...]) -> None:
        self.revision = revision
        self.items = items

    async def current_source_revision(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        connection_id: str,
    ) -> str | None:
        del tenant_id, workspace_id, connection_id
        return self.revision

    async def load_source_items(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        connection_id: str,
    ) -> tuple[SourceItem, ...]:
        del tenant_id, workspace_id, connection_id
        return self.items


class Repository:
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


def item(
    number: int,
    *,
    state: str = "open",
    blocked_by: int | None = None,
) -> SourceItem:
    section = "" if blocked_by is None else f"\n## Blocked by\n#{blocked_by}\n"
    return SourceItem(
        source_id="github:owner/repo",
        item_id=str(number),
        revision=f"node-{number}-{state}",
        title=f"Issue {number}",
        body=f"body{section}",
        state=state,
        labels=(),
        updated_at="2026-07-12T00:00:00+00:00",
        raw=(("number", number),),
    )


def command() -> IngestionCommand:
    return IngestionCommand(
        tenant_id="tenant",
        workspace_id="workspace",
        connection_id="connection",
        cycle_id="cycle-1",
        snapshot_id="snapshot-1",
        graph_revision="graph-1",
        policy_bundle_id="policy-1",
        policy_bundle_hash=_HASH,
        ranking_pipeline_hash=_HASH,
        engine_version="engine-1",
        normalization_profile_version="github-v1",
        causation_id="cause",
        correlation_id="correlation",
        outbox_id="outbox",
        outbox_idempotency_key="cycle:1",
        computed_at_iso="2026-07-13T00:00:00+00:00",
    )


def test_full_ingestion_persists_one_atomic_source_to_projection_cycle() -> None:
    items = (item(1), item(2, blocked_by=1))
    repository = Repository()
    receipt = asyncio.run(
        ingest_connection(
            command(),
            FixtureAdapter.from_items(items, "revision-1"),
            State(None, ()),
            repository,
            page_size=1,
        )
    )
    assert not receipt.idempotent_replay
    assert receipt.affected_item_ids == ("1", "2")
    write = repository.writes[0]
    assert len(write.source_versions) == 2
    assert write.normalized_snapshot.payload_hash == write.command.snapshot_hash
    decisions = {document.item_id: document.payload for document in write.decisions}
    assert decisions["1"]["ready"] is True
    assert decisions["2"]["ready"] is False


def test_replayed_revision_is_idempotent_and_does_not_write() -> None:
    repository = Repository()
    receipt = asyncio.run(
        ingest_connection(
            command(),
            FixtureAdapter.from_items((item(1),), "revision-1"),
            State("revision-1", (item(1),)),
            repository,
        )
    )
    assert receipt.idempotent_replay
    assert repository.writes == []


def test_incremental_close_affects_downstream_and_preserves_cursor_fence() -> None:
    previous = (item(1), item(2, blocked_by=1), item(3, blocked_by=2))
    updated = (item(1, state="closed"), item(2, blocked_by=1), item(3, blocked_by=2))
    repository = Repository()
    receipt = asyncio.run(
        ingest_connection(
            replace(command(), changed_item_ids=("1",), cycle_id="cycle-2"),
            FixtureAdapter.from_items(updated, "revision-2"),
            State("revision-1", previous),
            repository,
        )
    )
    assert receipt.affected_item_ids == ("1", "2", "3")
    assert repository.writes[0].command.expected_source_revision == "revision-1"
