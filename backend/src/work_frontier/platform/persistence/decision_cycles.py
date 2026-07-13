"""PostgreSQL adapter for atomic DecisionRecord-set persistence."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as postgres_insert

from work_frontier.application.ports.decision_cycles import (
    DecisionCycleReceipt,
    DecisionCycleWrite,
    StaleSourceCursorError,
)
from work_frontier.platform.persistence.schema import (
    audit_events,
    audit_segments,
    current_projections,
    decision_cycles,
    decision_records,
    normalized_snapshots,
    source_cursors,
    source_item_versions,
    transactional_outbox,
    workspace_frontiers,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from datetime import datetime

    from sqlalchemy.ext.asyncio import AsyncSession

_GENESIS = "0" * 64


class DecisionWriteBoundary(StrEnum):
    """Injectable internal boundaries used by atomicity harnesses."""

    CURSOR_FENCED = "cursor_fenced"
    CYCLE_APPENDED = "cycle_appended"
    DECISIONS_APPENDED = "decisions_appended"
    PROJECTIONS_UPDATED = "projections_updated"
    AUDIT_APPENDED = "audit_appended"
    OUTBOX_APPENDED = "outbox_appended"
    FRONTIER_PUBLISHED = "frontier_published"


class PostgresDecisionCycleRepository:
    """Persist one complete cycle and publish it only after every write succeeds."""

    _session: AsyncSession
    _actor: str
    _created_at: datetime
    _failure_probe: Callable[[DecisionWriteBoundary], None] | None

    def __init__(
        self,
        session: AsyncSession,
        *,
        actor: str,
        created_at: datetime,
        failure_probe: Callable[[DecisionWriteBoundary], None] | None = None,
    ) -> None:
        """Bind the repository to one workspace-scoped transaction."""
        if not actor.strip():
            msg = "decision cycle audit actor is required"
            raise ValueError(msg)
        if created_at.tzinfo is None or created_at.utcoffset() is None:
            msg = "decision cycle timestamp must be timezone-aware"
            raise ValueError(msg)
        self._session = session
        self._actor = actor
        self._created_at = created_at
        self._failure_probe = failure_probe

    async def persist(self, write: DecisionCycleWrite) -> DecisionCycleReceipt:
        """Persist all cycle outputs under one savepoint and optimistic cursor fence."""
        command = write.command
        async with self._session.begin_nested():
            await self._fence_source_cursor(write)
            self._probe(DecisionWriteBoundary.CURSOR_FENCED)

            await self._append_source_inputs(write)

            _ = await self._session.execute(
                decision_cycles.insert().values(
                    tenant_id=command.tenant_id,
                    workspace_id=command.workspace_id,
                    cycle_id=command.cycle_id,
                    snapshot_id=command.snapshot_id,
                    snapshot_hash=command.snapshot_hash,
                    graph_revision=command.graph_revision,
                    policy_bundle_hash=command.policy_bundle_hash,
                    source_revision=command.new_source_revision,
                    decision_set_hash=write.decision_set_hash,
                    recommended_item_id=write.recommended_item_id,
                )
            )
            self._probe(DecisionWriteBoundary.CYCLE_APPENDED)

            await self._append_decisions(write)
            self._probe(DecisionWriteBoundary.DECISIONS_APPENDED)

            await self._replace_projections(write)
            self._probe(DecisionWriteBoundary.PROJECTIONS_UPDATED)

            await self._append_audit(write)
            self._probe(DecisionWriteBoundary.AUDIT_APPENDED)

            _ = await self._session.execute(
                transactional_outbox.insert().values(
                    tenant_id=command.tenant_id,
                    workspace_id=command.workspace_id,
                    outbox_id=command.outbox_id,
                    idempotency_key=command.outbox_idempotency_key,
                    state="pending",
                    payload={
                        "cycle_id": command.cycle_id,
                        "decision_set_hash": write.decision_set_hash,
                        "source_revision": command.new_source_revision,
                    },
                )
            )
            self._probe(DecisionWriteBoundary.OUTBOX_APPENDED)

            version = await self._publish_frontier(write)
            self._probe(DecisionWriteBoundary.FRONTIER_PUBLISHED)

        return DecisionCycleReceipt(
            cycle_id=command.cycle_id,
            source_revision=command.new_source_revision,
            decision_count=len(write.decisions),
            active_frontier_version=version,
            decision_set_hash=write.decision_set_hash,
        )

    async def _append_source_inputs(self, write: DecisionCycleWrite) -> None:
        command = write.command
        rows = [
            {
                "tenant_id": command.tenant_id,
                "workspace_id": command.workspace_id,
                "source_version_id": item.source_version_id,
                "item_id": item.item_id,
                "source_id": item.source_id,
                "revision": item.revision,
                "payload": item.payload,
                "payload_hash": item.payload_hash,
                "connection_id": command.connection_id,
            }
            for item in sorted(
                write.source_versions,
                key=lambda value: value.source_version_id,
            )
        ]
        for row in rows:
            statement = postgres_insert(source_item_versions).values(**row)
            statement = statement.on_conflict_do_nothing(
                index_elements=[
                    "tenant_id",
                    "workspace_id",
                    "source_id",
                    "revision",
                ]
            )
            _ = await self._session.execute(statement)
        snapshot = write.normalized_snapshot
        statement = postgres_insert(normalized_snapshots).values(
            tenant_id=command.tenant_id,
            workspace_id=command.workspace_id,
            snapshot_id=snapshot.snapshot_id,
            content_hash=snapshot.payload_hash,
            source_revision_set=dict(snapshot.source_revision_set),
            graph_revision=snapshot.graph_revision,
            profile_version=snapshot.profile_version,
            payload=snapshot.payload,
        )
        statement = statement.on_conflict_do_nothing(
            index_elements=["tenant_id", "workspace_id", "content_hash"]
        )
        _ = await self._session.execute(statement)

    async def _fence_source_cursor(self, write: DecisionCycleWrite) -> None:
        command = write.command
        if command.expected_source_revision is None:
            statement = (
                postgres_insert(source_cursors)
                .values(
                    tenant_id=command.tenant_id,
                    workspace_id=command.workspace_id,
                    connection_id=command.connection_id,
                    revision=command.new_source_revision,
                )
                .on_conflict_do_nothing(
                    index_elements=["tenant_id", "workspace_id", "connection_id"]
                )
                .returning(source_cursors.c.revision)
            )
        else:
            statement = (
                source_cursors.update()
                .where(
                    source_cursors.c.tenant_id == command.tenant_id,
                    source_cursors.c.workspace_id == command.workspace_id,
                    source_cursors.c.connection_id == command.connection_id,
                    source_cursors.c.revision == command.expected_source_revision,
                )
                .values(revision=command.new_source_revision)
                .returning(source_cursors.c.revision)
            )
        result = await self._session.execute(statement)
        if result.scalar_one_or_none() is None:
            msg = "source cursor changed before the decision cycle committed"
            raise StaleSourceCursorError(msg)

    async def _append_decisions(self, write: DecisionCycleWrite) -> None:
        command = write.command
        rows = [
            {
                "tenant_id": command.tenant_id,
                "workspace_id": command.workspace_id,
                "decision_id": item.decision_id,
                "cycle_id": command.cycle_id,
                "item_id": item.item_id,
                "payload": item.payload,
                "payload_hash": item.payload_hash,
            }
            for item in sorted(write.decisions, key=lambda value: value.item_id)
        ]
        _ = await self._session.execute(decision_records.insert(), rows)

    async def _replace_projections(self, write: DecisionCycleWrite) -> None:
        command = write.command
        for item in sorted(write.decisions, key=lambda value: value.item_id):
            statement = postgres_insert(current_projections).values(
                tenant_id=command.tenant_id,
                workspace_id=command.workspace_id,
                item_id=item.item_id,
                cycle_id=command.cycle_id,
                derived_from_decision_id=item.decision_id,
                source_snapshot_hash=command.snapshot_hash,
                graph_revision=command.graph_revision,
                policy_bundle_hash=command.policy_bundle_hash,
                payload=item.payload,
            )
            statement = statement.on_conflict_do_update(
                index_elements=["tenant_id", "workspace_id", "item_id"],
                set_={
                    "cycle_id": statement.excluded.cycle_id,
                    "derived_from_decision_id": (
                        statement.excluded.derived_from_decision_id
                    ),
                    "source_snapshot_hash": statement.excluded.source_snapshot_hash,
                    "graph_revision": statement.excluded.graph_revision,
                    "policy_bundle_hash": statement.excluded.policy_bundle_hash,
                    "payload": statement.excluded.payload,
                },
            )
            _ = await self._session.execute(statement)

    async def _append_audit(self, write: DecisionCycleWrite) -> None:
        command = write.command
        payload = {
            "cycle_id": command.cycle_id,
            "decision_count": len(write.decisions),
            "decision_set_hash": write.decision_set_hash,
            "snapshot_hash": command.snapshot_hash,
            "source_revision": command.new_source_revision,
        }
        payload_json = _canonical_json(payload)
        payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
        segment_id = f"decision-cycle:{command.cycle_id}"
        envelope = {
            "actor": self._actor,
            "causation_id": command.causation_id,
            "correlation_id": command.correlation_id,
            "created_at": self._created_at.isoformat(),
            "event_id": command.cycle_id,
            "event_type": "decision_cycle_committed",
            "segment_id": segment_id,
            "seq": 1,
            "subject_id": command.cycle_id,
            "tenant_id": command.tenant_id,
            "workspace_id": command.workspace_id,
        }
        checksum = hashlib.sha256(
            (_GENESIS + _canonical_json(envelope) + payload_hash).encode()
        ).hexdigest()
        _ = await self._session.execute(
            audit_segments.insert().values(
                tenant_id=command.tenant_id,
                workspace_id=command.workspace_id,
                segment_id=segment_id,
                state="closed",
                final_checksum=checksum,
                external_anchor=None,
            )
        )
        _ = await self._session.execute(
            audit_events.insert().values(
                tenant_id=command.tenant_id,
                workspace_id=command.workspace_id,
                segment_id=segment_id,
                seq=1,
                event_id=command.cycle_id,
                event_type="decision_cycle_committed",
                actor=self._actor,
                subject_id=command.cycle_id,
                causation_id=command.causation_id,
                correlation_id=command.correlation_id,
                payload=payload,
                payload_hash=payload_hash,
                previous_checksum=_GENESIS,
                checksum=checksum,
                created_at=self._created_at,
            )
        )

    async def _publish_frontier(self, write: DecisionCycleWrite) -> int:
        command = write.command
        current = await self._session.execute(
            sa.select(workspace_frontiers.c.version)
            .where(
                workspace_frontiers.c.tenant_id == command.tenant_id,
                workspace_frontiers.c.workspace_id == command.workspace_id,
            )
            .with_for_update()
        )
        current_version = current.scalar_one_or_none()
        version = 1 if current_version is None else int(current_version) + 1
        statement = postgres_insert(workspace_frontiers).values(
            tenant_id=command.tenant_id,
            workspace_id=command.workspace_id,
            active_cycle_id=command.cycle_id,
            version=version,
        )
        statement = statement.on_conflict_do_update(
            index_elements=["tenant_id", "workspace_id"],
            set_={
                "active_cycle_id": statement.excluded.active_cycle_id,
                "version": statement.excluded.version,
            },
        )
        _ = await self._session.execute(statement)
        return version

    def _probe(self, boundary: DecisionWriteBoundary) -> None:
        if self._failure_probe is not None:
            self._failure_probe(boundary)


def _canonical_json(value: Mapping[str, object]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
