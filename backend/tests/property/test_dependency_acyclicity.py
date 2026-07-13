"""Property coverage for deterministic SCC detection and DAG acceptance."""

from dataclasses import dataclass
from datetime import UTC, datetime

from hypothesis import given, settings
from hypothesis import strategies as st

from work_frontier.domain.edges import BlockSubtype, Edge, EdgeOrigin, EdgeType
from work_frontier.domain.graph import analyze_dependency_graph
from work_frontier.domain.identifiers import (
    EdgeId,
    MonotonicUlidFactory,
    ResourceKind,
    ResourceRef,
    TenantId,
    WorkItemId,
    WorkspaceId,
)


@dataclass(frozen=True, slots=True)
class _GraphFixture:
    factory: MonotonicUlidFactory
    tenant_id: TenantId
    workspace_id: WorkspaceId
    nodes: tuple[ResourceRef, ...]


def _graph_fixture(node_count: int) -> _GraphFixture:
    factory = MonotonicUlidFactory()
    tenant_id = factory.generate(TenantId, timestamp_ms=1, entropy=1)
    workspace_id = factory.generate(WorkspaceId, timestamp_ms=1, entropy=2)
    nodes = tuple(
        ResourceRef(
            ResourceKind.WORK_ITEM,
            factory.generate(
                WorkItemId,
                timestamp_ms=1,
                entropy=index + 3,
            ),
        )
        for index in range(node_count)
    )
    return _GraphFixture(factory, tenant_id, workspace_id, nodes)


def _block_edge(
    fixture: _GraphFixture,
    source: ResourceRef,
    target: ResourceRef,
    entropy: int,
) -> Edge:
    return Edge(
        edge_id=fixture.factory.generate(
            EdgeId,
            timestamp_ms=2,
            entropy=entropy,
        ),
        tenant_id=fixture.tenant_id,
        workspace_id=fixture.workspace_id,
        edge_type=EdgeType.BLOCKS,
        source=source,
        target=target,
        subtype=BlockSubtype.HARD,
        created_at=datetime(2026, 7, 13, tzinfo=UTC),
        origin=EdgeOrigin.USER,
        provenance="generated graph case",
    )


@settings(max_examples=10_000, deadline=None, derandomize=True)
@given(
    node_count=st.integers(min_value=2, max_value=10),
    raw_pairs=st.sets(
        st.tuples(
            st.integers(min_value=0, max_value=9),
            st.integers(min_value=0, max_value=9),
        ),
        max_size=24,
    ),
    inject_cycle=st.booleans(),
)
def test_generated_dependency_graphs_detect_exact_injected_scc(
    node_count: int,
    raw_pairs: set[tuple[int, int]],
    *,
    inject_cycle: bool,
) -> None:
    fixture = _graph_fixture(node_count)
    nodes = fixture.nodes
    pairs = {
        (source % node_count, target % node_count)
        for source, target in raw_pairs
        if source % node_count < target % node_count
    }
    if inject_cycle:
        pairs.update({(0, 1), (1, 0)})
    edges = tuple(
        _block_edge(
            fixture,
            nodes[source],
            nodes[target],
            entropy=index + 100,
        )
        for index, (source, target) in enumerate(sorted(pairs))
    )

    analysis = analyze_dependency_graph(nodes=nodes, edges=edges)

    if inject_cycle:
        assert len(analysis.invalid_components) == 1
        assert analysis.invalid_components[0].members == nodes[:2]
        assert analysis.invalid_components[0].cycle_path[0] == nodes[0]
        assert analysis.invalid_components[0].cycle_path[-1] == nodes[0]
    else:
        assert analysis.invalid_components == ()
        assert analysis.projection.evaluable_nodes == nodes
