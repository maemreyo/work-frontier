from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import TypeVar

import pytest

from work_frontier.domain.edges import BlockSubtype, Edge, EdgeOrigin, EdgeType
from work_frontier.domain.entities import (
    Actor,
    ActorKind,
    Lifecycle,
    Program,
    ProgramStatus,
    WorkItem,
    WorkType,
)
from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError
from work_frontier.domain.identifiers import (
    ActorId,
    DecisionId,
    EdgeId,
    GateId,
    MonotonicUlidFactory,
    ProgramId,
    ResourceKind,
    ResourceRef,
    TenantId,
    WorkItemId,
    WorkspaceId,
    Ulid,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)
FACTORY = MonotonicUlidFactory()


TId = TypeVar("TId", bound=Ulid)


def new_id(id_type: type[TId], entropy: int) -> TId:
    return FACTORY.generate(id_type, timestamp_ms=1_720_000_000_000, entropy=entropy)


def scope():
    return new_id(TenantId, 1), new_id(WorkspaceId, 2)


def actor_id():
    return new_id(ActorId, 3)


def test_monotonic_ulid_generation_is_canonical_and_branded() -> None:
    factory = MonotonicUlidFactory()
    first = factory.generate(WorkItemId, timestamp_ms=1000, entropy=7)
    second = factory.generate(WorkItemId, timestamp_ms=999, entropy=1)
    assert isinstance(first, WorkItemId)
    assert str(first) < str(second)
    assert len(str(first)) == 26
    assert WorkItemId(str(first)) == first


def test_work_item_derived_caches_require_decision_identity() -> None:
    tenant_id, workspace_id = scope()
    with pytest.raises(DomainInvariantError) as exc:
        _ = WorkItem(
            item_id=new_id(WorkItemId, 10),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            title="Implement authority merge",
            work_type=WorkType.FEATURE,
            lifecycle=Lifecycle.PLANNED,
            created_at=NOW,
            updated_at=NOW,
            created_by=actor_id(),
            readiness=True,
        )
    assert exc.value.code is DomainErrorCode.DERIVED_WITHOUT_DECISION


def test_work_item_is_immutable_and_canonicalizes_collections() -> None:
    tenant_id, workspace_id = scope()
    item = WorkItem(
        item_id=new_id(WorkItemId, 11),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        title="Implement core entities",
        work_type=WorkType.FEATURE,
        lifecycle=Lifecycle.ACTIVE,
        created_at=NOW,
        updated_at=NOW,
        created_by=actor_id(),
        labels=("zeta", "alpha"),
        derived_from_decision_id=new_id(DecisionId, 12),
        readiness=True,
    )
    assert item.labels == ("alpha", "zeta")
    with pytest.raises(FrozenInstanceError):
        setattr(item, "title", "mutated")


def test_program_supports_multiple_parents_and_archives_when_empty() -> None:
    tenant_id, workspace_id = scope()
    program_id = new_id(ProgramId, 20)
    parent_a = new_id(ProgramId, 21)
    parent_b = new_id(ProgramId, 22)
    program = Program(
        program_id=program_id,
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        name="Authority rollout",
        status=ProgramStatus.ACTIVE,
        member_ids=(),
        contained_by=(parent_b, parent_a),
        contains=(),
        created_at=NOW,
        updated_at=NOW,
        created_by=actor_id(),
    )
    assert program.contained_by == (parent_a, parent_b)
    assert program.status is ProgramStatus.ARCHIVED


def test_actor_is_workspace_scoped() -> None:
    tenant_id, workspace_id = scope()
    actor = Actor(
        actor_id=actor_id(),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        kind=ActorKind.HUMAN,
        display_name="Ada",
    )
    assert actor.workspace_id == workspace_id


def test_edge_endpoint_matrix_accepts_valid_and_rejects_invalid() -> None:
    tenant_id, workspace_id = scope()
    source_item = ResourceRef(ResourceKind.WORK_ITEM, new_id(WorkItemId, 30))
    target_item = ResourceRef(ResourceKind.WORK_ITEM, new_id(WorkItemId, 31))
    edge = Edge(
        edge_id=new_id(EdgeId, 32),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        edge_type=EdgeType.BLOCKS,
        source=source_item,
        target=target_item,
        subtype=BlockSubtype.HARD,
        created_at=NOW,
        origin=EdgeOrigin.USER,
        provenance="Explicit dependency",
    )
    assert edge.subtype is BlockSubtype.HARD

    gate = ResourceRef(ResourceKind.GATE, new_id(GateId, 33))
    program = ResourceRef(ResourceKind.PROGRAM, new_id(ProgramId, 34))
    with pytest.raises(DomainInvariantError) as exc:
        _ = Edge(
            edge_id=new_id(EdgeId, 35),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            edge_type=EdgeType.REQUIRES_GATE,
            source=program,
            target=target_item,
            created_at=NOW,
            origin=EdgeOrigin.TRACKER,
            provenance="Invalid gate endpoint",
        )
    assert exc.value.code is DomainErrorCode.INVALID_EDGE

    valid_gate = Edge(
        edge_id=new_id(EdgeId, 36),
        tenant_id=tenant_id,
        workspace_id=workspace_id,
        edge_type=EdgeType.REQUIRES_GATE,
        source=gate,
        target=target_item,
        created_at=NOW,
        origin=EdgeOrigin.TRACKER,
        provenance="Required entry gate",
    )
    assert valid_gate.source.kind is ResourceKind.GATE
