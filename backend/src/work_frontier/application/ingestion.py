"""Durable refetch, normalization, affected solve, and atomic decision pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from work_frontier.application.decision_cycles import execute_decision_cycle
from work_frontier.application.ports.decision_cycles import (
    DecisionCycleCommand,
    DecisionCycleRepository,
    NormalizedSnapshotDocument,
    SourceVersionDocument,
)
from work_frontier.application.ports.ingestion import (
    IngestionCommand,
    IngestionReceipt,
    IngestionStateReader,
)
from work_frontier.domain.frontier import (
    Comparator,
    EngineEnvelope,
    FrontierItemInput,
    FrontierSnapshot,
    RankingPipeline,
    WorkClass,
)

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from work_frontier.application.ports.connections import (
        ConnectionAdapter,
        SourceItem,
    )

_BLOCKED_SECTION = re.compile(
    r"^## Blocked by\s*$\n(?P<body>.*?)(?=^##\s|\Z)",
    re.MULTILINE | re.DOTALL,
)
_ISSUE_REFERENCE = re.compile(r"(?<!\w)#(?P<number>\d+)")
_HASH_LENGTH = 64


@dataclass(frozen=True, slots=True)
class NormalizedItem:
    """Canonical source item and dependency facts consumed by the engine."""

    source: SourceItem
    blocker_ids: tuple[str, ...]
    lifecycle: str

    def canonical(self) -> dict[str, object]:
        """Return deterministic normalized JSON data."""
        return {
            "blocker_ids": list(self.blocker_ids),
            "body": self.source.body,
            "item_id": self.source.item_id,
            "labels": list(self.source.labels),
            "lifecycle": self.lifecycle,
            "revision": self.source.revision,
            "source_id": self.source.source_id,
            "state": self.source.state,
            "title": self.source.title,
            "updated_at": self.source.updated_at,
        }


@dataclass(frozen=True, slots=True)
class IngestionBuild:
    """Pure source-to-snapshot build reused by full and incremental solves."""

    snapshot: FrontierSnapshot
    source_versions: tuple[SourceVersionDocument, ...]
    normalized_snapshot: NormalizedSnapshotDocument
    affected_item_ids: tuple[str, ...]


async def ingest_connection(
    command: IngestionCommand,
    adapter: ConnectionAdapter,
    state: IngestionStateReader,
    repository: DecisionCycleRepository,
    *,
    page_size: int = 100,
) -> IngestionReceipt:
    """Run one idempotent full or incremental ingestion through atomic persistence."""
    expected_revision = await state.current_source_revision(
        tenant_id=command.tenant_id,
        workspace_id=command.workspace_id,
        connection_id=command.connection_id,
    )
    source_revision = adapter.current_revision()
    if expected_revision == source_revision:
        return IngestionReceipt(
            cycle_id=command.cycle_id,
            source_revision=source_revision,
            decision_set_hash="",
            affected_item_ids=(),
            idempotent_replay=True,
        )

    if command.changed_item_ids:
        previous = await state.load_source_items(
            tenant_id=command.tenant_id,
            workspace_id=command.workspace_id,
            connection_id=command.connection_id,
        )
        merged = {item.item_id: item for item in previous}
        for item_id in command.changed_item_ids:
            merged[item_id] = adapter.get_item(item_id)
        source_items = tuple(sorted(merged.values(), key=lambda item: item.item_id))
    else:
        source_items = _read_all_items(adapter, page_size=page_size)

    build = build_ingestion_snapshot(
        command,
        source_items,
        source_revision=source_revision,
    )
    cycle_command = DecisionCycleCommand(
        tenant_id=command.tenant_id,
        workspace_id=command.workspace_id,
        connection_id=command.connection_id,
        cycle_id=command.cycle_id,
        expected_source_revision=expected_revision,
        new_source_revision=source_revision,
        snapshot_id=command.snapshot_id,
        snapshot_hash=build.normalized_snapshot.payload_hash,
        graph_revision=command.graph_revision,
        policy_bundle_hash=command.policy_bundle_hash,
        causation_id=command.causation_id,
        correlation_id=command.correlation_id,
        outbox_id=command.outbox_id,
        outbox_idempotency_key=command.outbox_idempotency_key,
    )
    receipt = await execute_decision_cycle(
        cycle_command,
        build.snapshot,
        repository,
        source_versions=build.source_versions,
        normalized_snapshot=build.normalized_snapshot,
    )
    return IngestionReceipt(
        cycle_id=receipt.cycle_id,
        source_revision=receipt.source_revision,
        decision_set_hash=receipt.decision_set_hash,
        affected_item_ids=build.affected_item_ids,
        idempotent_replay=False,
    )


def build_ingestion_snapshot(
    command: IngestionCommand,
    source_items: tuple[SourceItem, ...],
    *,
    source_revision: str,
) -> IngestionBuild:
    """Purely normalize one source corpus into an identified frontier snapshot."""
    ordered_source_items = tuple(sorted(source_items, key=_source_item_key))
    normalized = tuple(normalize_source_item(item) for item in ordered_source_items)
    affected = affected_item_ids(normalized, command.changed_item_ids)
    snapshot_payload: dict[str, object] = {
        "items": [item.canonical() for item in normalized],
        "profile_version": command.normalization_profile_version,
        "source_revision": source_revision,
    }
    snapshot_hash = _canonical_hash(snapshot_payload)
    computed_at = datetime.fromisoformat(command.computed_at_iso)
    if computed_at.tzinfo is None or computed_at.utcoffset() is None:
        msg = "ingestion computed_at_iso must include a timezone"
        raise ValueError(msg)
    source_revisions = tuple(
        sorted({(item.source_id, item.revision) for item in ordered_source_items})
    )
    snapshot = FrontierSnapshot(
        envelope=EngineEnvelope(
            workspace_id=command.workspace_id,
            normalized_snapshot_id=command.snapshot_id,
            normalized_snapshot_hash=snapshot_hash,
            source_revision_set=source_revisions,
            graph_revision=command.graph_revision,
            policy_bundle_id=command.policy_bundle_id,
            policy_bundle_hash=command.policy_bundle_hash,
            ranking_pipeline_hash=command.ranking_pipeline_hash,
            engine_version=command.engine_version,
            normalization_profile_version=command.normalization_profile_version,
            computed_at=computed_at,
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
        ),
        items=frontier_inputs(normalized, computed_at),
        pipeline=RankingPipeline(
            (
                Comparator.PROGRAM_PRIORITY,
                Comparator.WORK_CLASS,
                Comparator.DOWNSTREAM_UNLOCK_COUNT_DESC,
                Comparator.AGE_DESC,
                Comparator.STABLE_ID,
            )
        ),
    )
    normalized_document = NormalizedSnapshotDocument(
        snapshot_id=command.snapshot_id,
        payload=snapshot_payload,
        payload_hash=snapshot_hash,
        source_revision_set=source_revisions,
        graph_revision=command.graph_revision,
        profile_version=command.normalization_profile_version,
    )
    return IngestionBuild(
        snapshot=snapshot,
        source_versions=tuple(_source_version_document(item) for item in source_items),
        normalized_snapshot=normalized_document,
        affected_item_ids=affected,
    )


def _read_all_items(
    adapter: ConnectionAdapter,
    *,
    page_size: int,
) -> tuple[SourceItem, ...]:
    cursor: str | None = None
    items: list[SourceItem] = []
    source_revision: str | None = None
    while True:
        page = adapter.list_items(cursor=cursor, page_size=page_size)
        if source_revision is None:
            source_revision = page.source_revision
        elif source_revision != page.source_revision:
            msg = "source revision changed while pagination was in progress"
            raise ValueError(msg)
        items.extend(page.items)
        cursor = page.next_cursor
        if cursor is None:
            break
    ordered = tuple(sorted(items, key=lambda item: item.item_id))
    if len({item.item_id for item in ordered}) != len(ordered):
        msg = "paginated source items contain duplicate identities"
        raise ValueError(msg)
    return ordered


def normalize_source_item(item: SourceItem) -> NormalizedItem:
    """Normalize one source item and preserve blocker provenance."""
    blocker_ids = tuple(sorted({*_body_blockers(item.body), *item.policy_blockers}))
    lifecycle = "completed" if item.state.lower() == "closed" else "planned"
    return NormalizedItem(item, blocker_ids, lifecycle)


def _body_blockers(body: str) -> Iterable[str]:
    section = _BLOCKED_SECTION.search(body)
    if section is None:
        return ()
    return tuple(
        match.group("number")
        for match in _ISSUE_REFERENCE.finditer(section.group("body"))
    )


def affected_item_ids(
    items: tuple[NormalizedItem, ...],
    changed_item_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Return changed roots plus deterministic downstream dependency closure."""
    if not changed_item_ids:
        return tuple(item.source.item_id for item in items)
    downstream: dict[str, set[str]] = {}
    for item in items:
        for blocker in item.blocker_ids:
            downstream.setdefault(blocker, set()).add(item.source.item_id)
    affected = set(changed_item_ids)
    queue = list(changed_item_ids)
    while queue:
        current = queue.pop(0)
        for target in sorted(downstream.get(current, ())):
            if target not in affected:
                affected.add(target)
                queue.append(target)
    return tuple(sorted(affected, key=_item_id_key))


def _source_item_key(item: SourceItem) -> tuple[int, int | str]:
    return _item_id_key(item.item_id)


def _item_id_key(item_id: str) -> tuple[int, int | str]:
    return (0, int(item_id)) if item_id.isdecimal() else (1, item_id)


def frontier_inputs(
    items: tuple[NormalizedItem, ...],
    computed_at: datetime,
) -> tuple[FrontierItemInput, ...]:
    """Adapt normalized source values into pure frontier-engine inputs."""
    state_by_id = {item.source.item_id: item.lifecycle for item in items}
    fan_out: dict[str, int] = {}
    for item in items:
        for blocker in item.blocker_ids:
            fan_out[blocker] = fan_out.get(blocker, 0) + 1
    output: list[FrontierItemInput] = []
    for item in items:
        incomplete = tuple(
            blocker
            for blocker in item.blocker_ids
            if state_by_id.get(blocker) != "completed"
        )
        updated_at = datetime.fromisoformat(item.source.updated_at)
        if updated_at.tzinfo is None or updated_at.utcoffset() is None:
            msg = "source item updated_at must be timezone-aware"
            raise ValueError(msg)
        age_seconds = max(0, int((computed_at - updated_at).total_seconds()))
        output.append(
            FrontierItemInput(
                item_id=item.source.item_id,
                program_id=None,
                title=item.source.title,
                description=item.source.body,
                work_type="issue",
                labels=item.source.labels,
                lifecycle=item.lifecycle,
                completion="source_lifecycle",
                program_priority=0,
                work_class=WorkClass.IMPLEMENTATION,
                downstream_unlock_count=fan_out.get(item.source.item_id, 0),
                age_seconds=age_seconds,
                hard_blockers_complete=not incomplete,
                entry_gates_pass=True,
                authority_safe=True,
                field_authority=(
                    ("lifecycle", "authoritative"),
                    ("title", "authoritative"),
                ),
                gate_states=(),
                incomplete_hard_blockers=incomplete,
                gate_dependencies=(),
                active_attention_items=(),
            )
        )
    return tuple(output)


def _source_version_document(item: SourceItem) -> SourceVersionDocument:
    payload: dict[str, object] = {
        "body": item.body,
        "labels": list(item.labels),
        "policy_blockers": list(item.policy_blockers),
        "raw": dict(item.raw),
        "state": item.state,
        "title": item.title,
        "updated_at": item.updated_at,
    }
    return SourceVersionDocument(
        source_version_id=_stable_id(
            "source-version",
            item.source_id,
            item.item_id,
            item.revision,
        ),
        item_id=item.item_id,
        source_id=item.source_id,
        revision=item.revision,
        payload=payload,
        payload_hash=_canonical_hash(payload),
    )


def _stable_id(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def _canonical_hash(value: Mapping[str, object]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    digest = hashlib.sha256(encoded).hexdigest()
    if len(digest) != _HASH_LENGTH:
        msg = "SHA-256 digest length invariant failed"
        raise AssertionError(msg)
    return digest
