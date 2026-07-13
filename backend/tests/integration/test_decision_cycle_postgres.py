from __future__ import annotations

import asyncio
import os
from dataclasses import replace
from datetime import UTC, datetime
from typing import Final

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from work_frontier.application.decision_cycles import execute_decision_cycle
from work_frontier.application.ports.decision_cycles import (
    DecisionCycleCommand,
    NormalizedSnapshotDocument,
    SourceVersionDocument,
    StaleSourceCursorError,
)
from work_frontier.domain.frontier import (
    Comparator,
    EngineEnvelope,
    FrontierItemInput,
    FrontierSnapshot,
    RankingPipeline,
    WorkClass,
)
from work_frontier.platform.persistence.database import workspace_session
from work_frontier.platform.persistence.decision_cycles import (
    DecisionWriteBoundary,
    PostgresDecisionCycleRepository,
)
from work_frontier.platform.persistence.scope import WorkspaceScope

_DATABASE_ENV: Final = "DATABASE_URL"
_HASH: Final = "a" * 64
_COUNT_STATEMENTS: Final = (
    (
        "source_item_versions",
        sa.text(
            "SELECT count(*) FROM source_item_versions "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
    (
        "normalized_snapshots",
        sa.text(
            "SELECT count(*) FROM normalized_snapshots "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
    (
        "source_cursors",
        sa.text(
            "SELECT count(*) FROM source_cursors "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
    (
        "decision_cycles",
        sa.text(
            "SELECT count(*) FROM decision_cycles "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
    (
        "decision_records",
        sa.text(
            "SELECT count(*) FROM decision_records "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
    (
        "current_projections",
        sa.text(
            "SELECT count(*) FROM current_projections "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
    (
        "audit_segments",
        sa.text(
            "SELECT count(*) FROM audit_segments "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
    (
        "audit_events",
        sa.text(
            "SELECT count(*) FROM audit_events "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
    (
        "transactional_outbox",
        sa.text(
            "SELECT count(*) FROM transactional_outbox "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
    (
        "workspace_frontiers",
        sa.text(
            "SELECT count(*) FROM workspace_frontiers "
            "WHERE tenant_id = :tenant AND workspace_id = :workspace"
        ),
    ),
)


def _database_url() -> str:
    value = os.environ.get(_DATABASE_ENV)
    if value is None:
        pytest.skip("PostgreSQL integration environment is not configured")
    return value


def _command(
    *,
    tenant: str,
    workspace: str,
    cycle: str,
    expected_revision: str | None = None,
    new_revision: str = "revision-1",
) -> DecisionCycleCommand:
    return DecisionCycleCommand(
        tenant_id=tenant,
        workspace_id=workspace,
        connection_id="connection-1",
        cycle_id=cycle,
        expected_source_revision=expected_revision,
        new_source_revision=new_revision,
        snapshot_id=f"snapshot-{cycle}",
        snapshot_hash=_HASH,
        graph_revision="graph-1",
        policy_bundle_hash=_HASH,
        causation_id=f"cause-{cycle}",
        correlation_id="correlation-1",
        outbox_id=f"outbox-{cycle}",
        outbox_idempotency_key=f"cycle:{cycle}",
    )


def _snapshot(command: DecisionCycleCommand) -> FrontierSnapshot:
    return FrontierSnapshot(
        envelope=EngineEnvelope(
            workspace_id=command.workspace_id,
            normalized_snapshot_id=command.snapshot_id,
            normalized_snapshot_hash=command.snapshot_hash,
            source_revision_set=(("github", command.new_source_revision),),
            graph_revision=command.graph_revision,
            policy_bundle_id="policy-1",
            policy_bundle_hash=command.policy_bundle_hash,
            ranking_pipeline_hash="b" * 64,
            engine_version="engine-1",
            normalization_profile_version="profile-1",
            computed_at=datetime(2026, 7, 13, tzinfo=UTC),
            causation_id=command.causation_id,
            correlation_id=command.correlation_id,
        ),
        items=(
            FrontierItemInput(
                item_id="item-1",
                program_id=None,
                title="Item one",
                description=None,
                work_type="issue",
                labels=(),
                lifecycle="planned",
                completion="incomplete",
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


def _source_documents(
    command: DecisionCycleCommand,
) -> tuple[SourceVersionDocument, ...]:
    return (
        SourceVersionDocument(
            source_version_id=f"source-version-{command.cycle_id}",
            item_id="item-1",
            source_id="github",
            revision=command.new_source_revision,
            payload={"title": "Item one"},
            payload_hash=_HASH,
        ),
    )


def _normalized_document(command: DecisionCycleCommand) -> NormalizedSnapshotDocument:
    return NormalizedSnapshotDocument(
        snapshot_id=command.snapshot_id,
        payload={"items": [{"item_id": "item-1"}]},
        payload_hash=command.snapshot_hash,
        source_revision_set=(("github", command.new_source_revision),),
        graph_revision=command.graph_revision,
        profile_version="profile-1",
    )


async def _seed_scope(url: str, tenant: str, workspace: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as connection:
            _ = await connection.execute(
                sa.text(
                    "INSERT INTO tenants (tenant_id, name) VALUES (:tenant, :name) "
                    "ON CONFLICT (tenant_id) DO NOTHING"
                ),
                {"tenant": tenant, "name": tenant},
            )
            _ = await connection.execute(
                sa.text(
                    "INSERT INTO organizations "
                    "(tenant_id, organization_id, name) "
                    "VALUES (:tenant, :organization, :name) "
                    "ON CONFLICT (tenant_id, organization_id) DO NOTHING"
                ),
                {
                    "tenant": tenant,
                    "organization": "organization-1",
                    "name": "organization",
                },
            )
            _ = await connection.execute(
                sa.text(
                    "INSERT INTO workspaces "
                    "(tenant_id, workspace_id, organization_id, name) "
                    "VALUES (:tenant, :workspace, :organization, :name) "
                    "ON CONFLICT (tenant_id, workspace_id) DO NOTHING"
                ),
                {
                    "tenant": tenant,
                    "workspace": workspace,
                    "organization": "organization-1",
                    "name": workspace,
                },
            )
            _ = await connection.execute(
                sa.text(
                    "INSERT INTO work_items "
                    "(tenant_id, workspace_id, item_id, title, lifecycle, "
                    "version, payload) "
                    "VALUES (:tenant, :workspace, 'item-1', 'Item one', "
                    "'planned', 1, '{}'::jsonb) "
                    "ON CONFLICT (tenant_id, workspace_id, item_id) DO NOTHING"
                ),
                {"tenant": tenant, "workspace": workspace},
            )
    finally:
        await engine.dispose()


async def _persist(
    url: str,
    command: DecisionCycleCommand,
    *,
    failure_boundary: DecisionWriteBoundary | None = None,
) -> None:
    engine = create_async_engine(url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    def failure_probe(boundary: DecisionWriteBoundary) -> None:
        if boundary is failure_boundary:
            msg = f"injected failure at {boundary.value}"
            raise RuntimeError(msg)

    try:
        async with workspace_session(
            factory,
            WorkspaceScope(command.tenant_id, command.workspace_id),
        ) as session:
            repository = PostgresDecisionCycleRepository(
                session,
                actor="system:test",
                created_at=datetime(2026, 7, 13, tzinfo=UTC),
                failure_probe=None if failure_boundary is None else failure_probe,
            )
            _ = await execute_decision_cycle(
                command,
                _snapshot(command),
                repository,
                source_versions=_source_documents(command),
                normalized_snapshot=_normalized_document(command),
            )
    finally:
        await engine.dispose()


async def _counts(url: str, tenant: str, workspace: str) -> dict[str, int]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            output: dict[str, int] = {}
            for table, statement in _COUNT_STATEMENTS:
                value = await connection.scalar(
                    statement,
                    {"tenant": tenant, "workspace": workspace},
                )
                output[table] = int(value or 0)
            return output
    finally:
        await engine.dispose()


async def _active_cycle(url: str, tenant: str, workspace: str) -> tuple[str, int]:
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                sa.text(
                    "SELECT active_cycle_id, version FROM workspace_frontiers "
                    "WHERE tenant_id = :tenant AND workspace_id = :workspace"
                ),
                {"tenant": tenant, "workspace": workspace},
            )
            row = result.one()
            return str(row[0]), int(row[1])
    finally:
        await engine.dispose()


def test_decision_cycle_publishes_one_complete_frontier() -> None:
    url = _database_url()
    tenant = "tenant-decision-publish"
    workspace = "workspace-decision-publish"
    command = _command(tenant=tenant, workspace=workspace, cycle="cycle-1")
    asyncio.run(_seed_scope(url, tenant, workspace))
    asyncio.run(_persist(url, command))

    counts = asyncio.run(_counts(url, tenant, workspace))
    assert counts == {
        "audit_events": 1,
        "audit_segments": 1,
        "current_projections": 1,
        "decision_cycles": 1,
        "decision_records": 1,
        "normalized_snapshots": 1,
        "source_cursors": 1,
        "source_item_versions": 1,
        "transactional_outbox": 1,
        "workspace_frontiers": 1,
    }
    assert asyncio.run(_active_cycle(url, tenant, workspace)) == ("cycle-1", 1)


@pytest.mark.parametrize("boundary", tuple(DecisionWriteBoundary))
def test_injected_boundary_failure_rolls_back_the_complete_cycle(
    boundary: DecisionWriteBoundary,
) -> None:
    url = _database_url()
    tenant = f"tenant-rollback-{boundary.value}"
    workspace = f"workspace-rollback-{boundary.value}"
    command = _command(tenant=tenant, workspace=workspace, cycle="cycle-1")
    asyncio.run(_seed_scope(url, tenant, workspace))

    with pytest.raises(RuntimeError, match="injected failure"):
        asyncio.run(_persist(url, command, failure_boundary=boundary))

    assert all(
        count == 0 for count in asyncio.run(_counts(url, tenant, workspace)).values()
    )


def test_stale_source_cursor_rejects_the_second_cycle_without_partial_rows() -> None:
    url = _database_url()
    tenant = "tenant-stale-cursor"
    workspace = "workspace-stale-cursor"
    first = _command(tenant=tenant, workspace=workspace, cycle="cycle-1")
    asyncio.run(_seed_scope(url, tenant, workspace))
    asyncio.run(_persist(url, first))

    stale = replace(
        _command(
            tenant=tenant,
            workspace=workspace,
            cycle="cycle-2",
            expected_revision="wrong-revision",
            new_revision="revision-2",
        ),
        snapshot_id="snapshot-cycle-2",
    )
    with pytest.raises(StaleSourceCursorError, match="source cursor changed"):
        asyncio.run(_persist(url, stale))

    counts = asyncio.run(_counts(url, tenant, workspace))
    assert counts["decision_cycles"] == 1
    assert counts["decision_records"] == 1
    assert counts["transactional_outbox"] == 1
    assert asyncio.run(_active_cycle(url, tenant, workspace)) == ("cycle-1", 1)
