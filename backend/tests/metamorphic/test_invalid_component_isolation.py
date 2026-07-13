"""Metamorphic proof that disconnected invalid SCCs do not alter valid facts."""

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


@settings(max_examples=500, deadline=None, derandomize=True)
@given(
    node_count=st.integers(min_value=1, max_value=8),
    raw_pairs=st.sets(
        st.tuples(
            st.integers(min_value=0, max_value=7),
            st.integers(min_value=0, max_value=7),
        ),
        max_size=20,
    ),
)
def test_injected_invalid_component_leaves_valid_projection_byte_identical(
    node_count: int,
    raw_pairs: set[tuple[int, int]],
) -> None:
    fixture = _graph_fixture(node_count + 2)
    invalid_a, invalid_b = fixture.nodes[-2:]
    base_nodes = fixture.nodes[:-2]
    pairs = {
        (source % node_count, target % node_count)
        for source, target in raw_pairs
        if source % node_count < target % node_count
    }
    base_edges = tuple(
        _block_edge(
            fixture,
            base_nodes[source],
            base_nodes[target],
            entropy=index + 100,
        )
        for index, (source, target) in enumerate(sorted(pairs))
    )
    base = analyze_dependency_graph(nodes=base_nodes, edges=base_edges)

    injected_edges = (
        *base_edges,
        _block_edge(
            fixture,
            invalid_a,
            invalid_b,
            entropy=10_000,
        ),
        _block_edge(
            fixture,
            invalid_b,
            invalid_a,
            entropy=10_001,
        ),
    )
    injected = analyze_dependency_graph(
        nodes=(*base_nodes, invalid_a, invalid_b),
        edges=injected_edges,
    )

    assert injected.projection == base.projection
    assert len(injected.invalid_components) == 1
    assert injected.invalid_components[0].members == (invalid_a, invalid_b)
    assert len(injected.attention) == 1
