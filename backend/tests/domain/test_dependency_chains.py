"""Deterministic examples for graph validation and affected traversal."""

from datetime import UTC, datetime

import pytest

from work_frontier.domain.authority import AttentionSeverity
from work_frontier.domain.edges import BlockSubtype, Edge, EdgeOrigin, EdgeType
from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError
from work_frontier.domain.graph import (
    analyze_dependency_graph,
    traverse_affected_region,
    validate_containment_dag,
)
from work_frontier.domain.identifiers import (
    EdgeId,
    GateId,
    MonotonicUlidFactory,
    ProgramId,
    ResourceKind,
    ResourceRef,
    TenantId,
    WorkItemId,
    WorkspaceId,
)

type GraphId = TenantId | WorkspaceId | WorkItemId | ProgramId | GateId | EdgeId


class GraphFixtureFactory:
    """Build scoped resources and edges with deterministic identities."""

    __slots__: tuple[str, ...] = (
        "_entropy",
        "_factory",
        "tenant_id",
        "workspace_id",
    )

    _entropy: int
    _factory: MonotonicUlidFactory
    tenant_id: TenantId
    workspace_id: WorkspaceId

    def __init__(self) -> None:
        self._factory = MonotonicUlidFactory()
        self._entropy = 0
        self.tenant_id = self._next_id(TenantId)
        self.workspace_id = self._next_id(WorkspaceId)

    def work_item(self) -> ResourceRef:
        return ResourceRef(ResourceKind.WORK_ITEM, self._next_id(WorkItemId))

    def program(self) -> ResourceRef:
        return ResourceRef(ResourceKind.PROGRAM, self._next_id(ProgramId))

    def edge(
        self,
        source: ResourceRef,
        target: ResourceRef,
        edge_type: EdgeType,
        subtype: BlockSubtype | None = None,
    ) -> Edge:
        return Edge(
            edge_id=self._next_id(EdgeId),
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            edge_type=edge_type,
            source=source,
            target=target,
            subtype=subtype,
            created_at=datetime(2026, 7, 13, tzinfo=UTC),
            origin=EdgeOrigin.USER,
            provenance="graph test fixture",
        )

    def _next_id[TId: GraphId](self, id_type: type[TId]) -> TId:
        self._entropy += 1
        return self._factory.generate(
            id_type,
            timestamp_ms=1_720_000_000_000,
            entropy=self._entropy,
        )


def test_containment_cycle_rejected_with_deterministic_path() -> None:
    factory = GraphFixtureFactory()
    first = factory.program()
    second = factory.program()
    edges = (
        factory.edge(first, second, EdgeType.CONTAINS),
        factory.edge(second, first, EdgeType.CONTAINS),
    )

    with pytest.raises(DomainInvariantError) as exc:
        _ = validate_containment_dag(tuple(reversed(edges)))

    assert exc.value.code is DomainErrorCode.CONTAINMENT_CYCLE
    assert str(first.resource_id) in exc.value.detail
    assert str(second.resource_id) in exc.value.detail


def test_containment_allows_shared_children_and_is_order_invariant() -> None:
    factory = GraphFixtureFactory()
    first_parent = factory.program()
    second_parent = factory.program()
    child = factory.work_item()
    edges = (
        factory.edge(second_parent, child, EdgeType.CONTAINS),
        factory.edge(first_parent, child, EdgeType.CONTAINS),
    )

    forward = validate_containment_dag(edges)
    reverse = validate_containment_dag(tuple(reversed(edges)))

    assert forward == reverse
    assert forward.topological_order[-1] == child
    assert set(forward.topological_order[:-1]) == {first_parent, second_parent}


def test_dependency_scc_quarantines_only_cyclic_component() -> None:
    factory = GraphFixtureFactory()
    cycle_a = factory.work_item()
    cycle_b = factory.work_item()
    unaffected_a = factory.work_item()
    unaffected_b = factory.work_item()
    edges = (
        factory.edge(cycle_a, cycle_b, EdgeType.BLOCKS, BlockSubtype.HARD),
        factory.edge(cycle_b, cycle_a, EdgeType.BLOCKS, BlockSubtype.HARD),
        factory.edge(
            unaffected_a,
            unaffected_b,
            EdgeType.BLOCKS,
            BlockSubtype.SOFT,
        ),
    )

    analysis = analyze_dependency_graph(
        nodes=(cycle_a, cycle_b, unaffected_a, unaffected_b),
        edges=edges,
    )

    assert len(analysis.invalid_components) == 1
    assert analysis.invalid_components[0].members == (cycle_a, cycle_b)
    assert analysis.projection.evaluable_nodes == (unaffected_a, unaffected_b)
    assert analysis.projection.soft_blockers_for(unaffected_b) == (unaffected_a,)
    assert analysis.attention[0].severity is AttentionSeverity.CRITICAL
    assert "cycle_path=" in analysis.attention[0].deterministic_basis


def test_dependency_projection_reports_blockers_fan_out_and_root_paths() -> None:
    factory = GraphFixtureFactory()
    root = factory.work_item()
    middle = factory.work_item()
    leaf = factory.work_item()
    soft_root = factory.work_item()
    edges = (
        factory.edge(root, middle, EdgeType.BLOCKS, BlockSubtype.HARD),
        factory.edge(middle, leaf, EdgeType.BLOCKS, BlockSubtype.HARD),
        factory.edge(soft_root, leaf, EdgeType.BLOCKS, BlockSubtype.SOFT),
    )

    projection = analyze_dependency_graph(
        nodes=(leaf, middle, root, soft_root),
        edges=tuple(reversed(edges)),
    ).projection

    assert projection.hard_blockers_for(middle) == (root,)
    assert projection.hard_blockers_for(leaf) == (middle,)
    assert projection.soft_blockers_for(leaf) == (soft_root,)
    assert projection.fan_out_for(root) == 2
    assert projection.fan_out_for(middle) == 1
    assert projection.root_cause_paths_for(leaf) == (
        (root, middle, leaf),
        (soft_root, leaf),
    )


def test_affected_region_ignores_related_edges_and_quarantined_nodes() -> None:
    factory = GraphFixtureFactory()
    changed = factory.work_item()
    blocked = factory.work_item()
    contained = factory.work_item()
    related = factory.work_item()
    quarantined = factory.work_item()
    edges = (
        factory.edge(changed, blocked, EdgeType.BLOCKS, BlockSubtype.HARD),
        factory.edge(blocked, contained, EdgeType.CONTAINS),
        factory.edge(changed, related, EdgeType.RELATED_TO),
        factory.edge(
            blocked,
            quarantined,
            EdgeType.BLOCKS,
            BlockSubtype.HARD,
        ),
    )

    region = traverse_affected_region(
        roots=(changed,),
        edges=edges,
        quarantined=(quarantined,),
    )

    assert region.affected_nodes == (changed, blocked, contained)
    assert related not in region.affected_nodes
    assert quarantined not in region.affected_nodes
    assert any(path.path == (changed, blocked, contained) for path in region.paths)
