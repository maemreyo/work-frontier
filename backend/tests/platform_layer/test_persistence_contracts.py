from __future__ import annotations

import inspect

import pytest
from sqlalchemy import insert

from work_frontier.platform.persistence.schema import (
    WORKSPACE_TABLES,
    decision_records,
    metadata,
    work_items,
)
from work_frontier.platform.persistence.scope import (
    ScopedResourceId,
    WorkspaceScope,
    workspace_predicate,
)


def test_all_workspace_tables_have_tenant_and_workspace_columns() -> None:
    assert WORKSPACE_TABLES
    for table in WORKSPACE_TABLES:
        assert "tenant_id" in table.c
        assert "workspace_id" in table.c


def test_scoped_resource_rejects_blank_scope() -> None:
    with pytest.raises(ValueError, match="tenant_id and workspace_id are required"):
        _ = WorkspaceScope(tenant_id="", workspace_id="ws")
    with pytest.raises(ValueError, match="resource_id is required"):
        _ = ScopedResourceId(scope=WorkspaceScope("t", "ws"), resource_id="")


def test_repository_contract_cannot_accept_bare_resource_id() -> None:
    from work_frontier.platform.persistence.repositories import ScopedRepository

    signature = inspect.signature(ScopedRepository.get)
    assert tuple(signature.parameters) == ("self", "key")
    assert signature.parameters["key"].annotation is not str


def test_workspace_predicate_binds_both_scope_dimensions() -> None:
    scope = WorkspaceScope("tenant-a", "workspace-a")
    expression = workspace_predicate(work_items, scope)
    rendered = str(expression.compile(compile_kwargs={"literal_binds": True}))
    assert "tenant-a" in rendered
    assert "workspace-a" in rendered


def test_decision_records_are_append_only_by_schema_contract() -> None:
    assert decision_records.info["append_only"] is True
    statement = insert(decision_records).values(
        tenant_id="t",
        workspace_id="w",
        decision_id="d",
        item_id="i",
        payload={},
        payload_hash="a" * 64,
    )
    assert "INSERT INTO decision_records" in str(statement)


def test_metadata_contains_required_platform_tables() -> None:
    required = {
        "tenants",
        "organizations",
        "workspaces",
        "programs",
        "work_items",
        "source_item_versions",
        "normalized_snapshots",
        "edges",
        "policy_bundles",
        "decision_records",
        "current_projections",
        "gates",
        "evidence_records",
        "approvals",
        "overrides",
        "work_leases",
        "attention_items",
        "connections",
        "webhook_inbox",
        "transactional_outbox",
        "job_queue",
        "audit_segments",
        "audit_events",
        "scheduler_leases",
    }
    assert required <= set(metadata.tables)
