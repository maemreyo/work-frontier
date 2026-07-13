"""Deterministic graph validation, SCC isolation, and affected traversal."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from work_frontier.domain.authority import AttentionBasis, AttentionSeverity
from work_frontier.domain.edges import BlockSubtype, Edge, EdgeType
from work_frontier.domain.errors import DomainErrorCode, DomainInvariantError
from work_frontier.domain.identifiers import ResourceKind, ResourceRef

if TYPE_CHECKING:
    from collections.abc import Iterable

type BlockerIndex = tuple[
    tuple[ResourceRef, tuple[ResourceRef, ...]],
    ...,
]
type FanOutIndex = tuple[tuple[ResourceRef, int], ...]
type RootCauseIndex = tuple[
    tuple[ResourceRef, tuple[tuple[ResourceRef, ...], ...]],
    ...,
]


@dataclass(frozen=True, slots=True)
class ContainmentAnalysis:
    """Validated containment nodes in deterministic parent-before-child order."""

    nodes: tuple[ResourceRef, ...]
    topological_order: tuple[ResourceRef, ...]


@dataclass(frozen=True, slots=True)
class DependencyComponent:
    """One deterministic strongly connected component of the blocks graph."""

    members: tuple[ResourceRef, ...]
    cyclic: bool
    cycle_path: tuple[ResourceRef, ...] = ()


@dataclass(frozen=True, slots=True)
class DependencyProjection:
    """Evaluable dependency facts after cyclic SCC quarantine."""

    evaluable_nodes: tuple[ResourceRef, ...]
    hard_blockers_by_target: BlockerIndex
    soft_blockers_by_target: BlockerIndex
    downstream_fan_out: FanOutIndex
    root_cause_paths_by_target: RootCauseIndex

    def hard_blockers_for(self, target: ResourceRef) -> tuple[ResourceRef, ...]:
        """Return deterministic hard blockers for one target."""
        return _lookup_node_tuple(self.hard_blockers_by_target, target)

    def soft_blockers_for(self, target: ResourceRef) -> tuple[ResourceRef, ...]:
        """Return deterministic soft blockers for one target."""
        return _lookup_node_tuple(self.soft_blockers_by_target, target)

    def fan_out_for(self, source: ResourceRef) -> int:
        """Return the number of downstream nodes reachable from one source."""
        for node, count in self.downstream_fan_out:
            if node == source:
                return count
        return 0

    def root_cause_paths_for(
        self,
        target: ResourceRef,
    ) -> tuple[tuple[ResourceRef, ...], ...]:
        """Return one lexicographically minimal shortest path per root cause."""
        for node, paths in self.root_cause_paths_by_target:
            if node == target:
                return paths
        return ()


@dataclass(frozen=True, slots=True)
class DependencyAnalysis:
    """Full SCC analysis plus localized valid projection and attention bases."""

    components: tuple[DependencyComponent, ...]
    invalid_components: tuple[DependencyComponent, ...]
    projection: DependencyProjection
    attention: tuple[AttentionBasis, ...]


@dataclass(frozen=True, slots=True)
class AffectedPath:
    """Shortest deterministic path from one changed root to one affected node."""

    root: ResourceRef
    target: ResourceRef
    path: tuple[ResourceRef, ...]


@dataclass(frozen=True, slots=True)
class AffectedRegion:
    """Nodes whose derived state can change after graph-root mutations."""

    roots: tuple[ResourceRef, ...]
    affected_nodes: tuple[ResourceRef, ...]
    paths: tuple[AffectedPath, ...]


def validate_containment_dag(edges: tuple[Edge, ...]) -> ContainmentAnalysis:
    """Reject containment cycles and return deterministic topological order."""
    contains_edges = tuple(
        edge for edge in edges if edge.edge_type is EdgeType.CONTAINS
    )
    nodes = _nodes_from_edges(contains_edges)
    adjacency = _adjacency(nodes, contains_edges)
    cycle_path = _find_directed_cycle(nodes, adjacency)
    if cycle_path:
        rendered = " -> ".join(_node_label(node) for node in cycle_path)
        raise DomainInvariantError(
            DomainErrorCode.CONTAINMENT_CYCLE,
            "contains",
            f"containment cycle detected: {rendered}",
        )

    in_degree: dict[ResourceRef, int] = dict.fromkeys(nodes, 0)
    for targets in adjacency.values():
        for target in targets:
            in_degree[target] += 1

    ready = list(
        _sorted_nodes(node for node, degree in in_degree.items() if degree == 0)
    )
    ordered: list[ResourceRef] = []
    while ready:
        node = ready.pop(0)
        ordered.append(node)
        for target in adjacency[node]:
            in_degree[target] -= 1
            if in_degree[target] == 0:
                ready.append(target)
                ready.sort(key=_node_key)

    return ContainmentAnalysis(nodes=nodes, topological_order=tuple(ordered))


def analyze_dependency_graph(
    *,
    nodes: tuple[ResourceRef, ...] = (),
    edges: tuple[Edge, ...],
) -> DependencyAnalysis:
    """Quarantine cyclic block SCCs and derive deterministic valid graph facts."""
    block_edges = tuple(edge for edge in edges if edge.edge_type is EdgeType.BLOCKS)
    all_nodes = _sorted_nodes({*nodes, *_nodes_from_edges(block_edges)})
    _require_work_items(all_nodes)
    adjacency = _adjacency(all_nodes, block_edges)
    components = _strongly_connected_components(all_nodes, adjacency)

    invalid_components = tuple(
        component for component in components if component.cyclic
    )
    invalid_nodes = {
        member for component in invalid_components for member in component.members
    }
    evaluable_nodes = tuple(node for node in all_nodes if node not in invalid_nodes)
    valid_edges = tuple(
        edge
        for edge in block_edges
        if edge.source not in invalid_nodes and edge.target not in invalid_nodes
    )
    valid_adjacency = _adjacency(evaluable_nodes, valid_edges)

    projection = DependencyProjection(
        evaluable_nodes=evaluable_nodes,
        hard_blockers_by_target=_blocker_index(
            evaluable_nodes,
            valid_edges,
            BlockSubtype.HARD,
        ),
        soft_blockers_by_target=_blocker_index(
            evaluable_nodes,
            valid_edges,
            BlockSubtype.SOFT,
        ),
        downstream_fan_out=_fan_out_index(evaluable_nodes, valid_adjacency),
        root_cause_paths_by_target=_root_cause_index(
            evaluable_nodes,
            valid_adjacency,
        ),
    )
    attention = tuple(
        AttentionBasis(
            category="invalid_dependency_component",
            severity=AttentionSeverity.CRITICAL,
            field="blocks",
            deterministic_basis=(
                "dependency_scc="
                + ",".join(_node_label(member) for member in component.members)
                + ";cycle_path="
                + " -> ".join(_node_label(member) for member in component.cycle_path)
            ),
        )
        for component in invalid_components
    )
    return DependencyAnalysis(
        components=components,
        invalid_components=invalid_components,
        projection=projection,
        attention=attention,
    )


def traverse_affected_region(
    *,
    roots: tuple[ResourceRef, ...],
    edges: tuple[Edge, ...],
    quarantined: tuple[ResourceRef, ...] = (),
) -> AffectedRegion:
    """Traverse only graph relationships that can change derived state."""
    quarantined_set = set(quarantined)
    resolved_roots = tuple(
        node for node in _sorted_nodes(set(roots)) if node not in quarantined_set
    )
    semantic_edges = tuple(
        edge
        for edge in edges
        if edge.edge_type
        in {EdgeType.CONTAINS, EdgeType.BLOCKS, EdgeType.REQUIRES_GATE}
        and edge.source not in quarantined_set
        and edge.target not in quarantined_set
    )
    all_nodes = _sorted_nodes({*resolved_roots, *_nodes_from_edges(semantic_edges)})
    adjacency = _adjacency(all_nodes, semantic_edges)

    affected: set[ResourceRef] = set()
    paths: list[AffectedPath] = []
    for root in resolved_roots:
        shortest = _shortest_paths(root, adjacency)
        affected.update(shortest)
        paths.extend(
            AffectedPath(root=root, target=target, path=path)
            for target, path in shortest.items()
        )

    return AffectedRegion(
        roots=resolved_roots,
        affected_nodes=_sorted_nodes(affected),
        paths=tuple(sorted(paths, key=_affected_path_key)),
    )


def _require_work_items(nodes: tuple[ResourceRef, ...]) -> None:
    for node in nodes:
        if node.kind is not ResourceKind.WORK_ITEM:
            raise DomainInvariantError(
                DomainErrorCode.INVALID_EDGE,
                "nodes",
                "dependency graph accepts WorkItem nodes only",
            )


def _nodes_from_edges(edges: tuple[Edge, ...]) -> tuple[ResourceRef, ...]:
    return _sorted_nodes(
        {endpoint for edge in edges for endpoint in (edge.source, edge.target)}
    )


def _adjacency(
    nodes: tuple[ResourceRef, ...],
    edges: tuple[Edge, ...],
) -> dict[ResourceRef, tuple[ResourceRef, ...]]:
    mutable: dict[ResourceRef, set[ResourceRef]] = {node: set() for node in nodes}
    for edge in edges:
        mutable.setdefault(edge.source, set()).add(edge.target)
        _ = mutable.setdefault(edge.target, set())
    return {
        node: _sorted_nodes(targets)
        for node, targets in sorted(
            mutable.items(),
            key=lambda item: _node_key(item[0]),
        )
    }


@dataclass(slots=True)
class _TarjanState:
    """Mutable traversal state isolated inside one SCC computation."""

    adjacency: dict[ResourceRef, tuple[ResourceRef, ...]]
    next_index: int = 0
    stack: list[ResourceRef] = field(default_factory=list)
    on_stack: set[ResourceRef] = field(default_factory=set)
    indices: dict[ResourceRef, int] = field(default_factory=dict)
    low_links: dict[ResourceRef, int] = field(default_factory=dict)
    components: list[tuple[ResourceRef, ...]] = field(default_factory=list)

    def visit(self, node: ResourceRef) -> None:
        """Visit one node using deterministic Tarjan traversal."""
        self.indices[node] = self.next_index
        self.low_links[node] = self.next_index
        self.next_index += 1
        self.stack.append(node)
        self.on_stack.add(node)

        for target in self.adjacency[node]:
            self._visit_target(node, target)

        if self.low_links[node] == self.indices[node]:
            self.components.append(self._pop_component(node))

    def _visit_target(self, node: ResourceRef, target: ResourceRef) -> None:
        if target not in self.indices:
            self.visit(target)
            self.low_links[node] = min(
                self.low_links[node],
                self.low_links[target],
            )
        elif target in self.on_stack:
            self.low_links[node] = min(
                self.low_links[node],
                self.indices[target],
            )

    def _pop_component(self, root: ResourceRef) -> tuple[ResourceRef, ...]:
        members: list[ResourceRef] = []
        while self.stack:
            member = self.stack.pop()
            self.on_stack.remove(member)
            members.append(member)
            if member == root:
                break
        return _sorted_nodes(members)


def _strongly_connected_components(
    nodes: tuple[ResourceRef, ...],
    adjacency: dict[ResourceRef, tuple[ResourceRef, ...]],
) -> tuple[DependencyComponent, ...]:
    state = _TarjanState(adjacency=adjacency)
    for node in nodes:
        if node not in state.indices:
            state.visit(node)

    components: list[DependencyComponent] = []
    for members in state.components:
        cyclic = len(members) > 1 or (
            len(members) == 1 and members[0] in adjacency[members[0]]
        )
        cycle_path = _find_component_cycle(members, adjacency) if cyclic else ()
        components.append(
            DependencyComponent(
                members=members,
                cyclic=cyclic,
                cycle_path=cycle_path,
            )
        )
    return tuple(
        sorted(
            components,
            key=lambda component: _node_key(component.members[0]),
        )
    )


def _find_component_cycle(
    members: tuple[ResourceRef, ...],
    adjacency: dict[ResourceRef, tuple[ResourceRef, ...]],
) -> tuple[ResourceRef, ...]:
    member_set = set(members)
    start = members[0]

    def search(
        node: ResourceRef,
        path: tuple[ResourceRef, ...],
        visited: frozenset[ResourceRef],
    ) -> tuple[ResourceRef, ...]:
        for target in adjacency[node]:
            if target not in member_set:
                continue
            if target == start:
                return (*path, start)
            if target in visited:
                continue
            found = search(target, (*path, target), visited | {target})
            if found:
                return found
        return ()

    return search(start, (start,), frozenset({start}))


def _find_directed_cycle(
    nodes: tuple[ResourceRef, ...],
    adjacency: dict[ResourceRef, tuple[ResourceRef, ...]],
) -> tuple[ResourceRef, ...]:
    visited: set[ResourceRef] = set()
    active: list[ResourceRef] = []
    active_set: set[ResourceRef] = set()

    def visit(node: ResourceRef) -> tuple[ResourceRef, ...]:
        visited.add(node)
        active.append(node)
        active_set.add(node)
        for target in adjacency[node]:
            if target not in visited:
                found = visit(target)
                if found:
                    return found
            elif target in active_set:
                index = active.index(target)
                return (*active[index:], target)
        _ = active.pop()
        active_set.remove(node)
        return ()

    for node in nodes:
        if node not in visited:
            found = visit(node)
            if found:
                return found
    return ()


def _blocker_index(
    nodes: tuple[ResourceRef, ...],
    edges: tuple[Edge, ...],
    subtype: BlockSubtype,
) -> BlockerIndex:
    blockers: dict[ResourceRef, set[ResourceRef]] = {node: set() for node in nodes}
    for edge in edges:
        if edge.subtype is subtype:
            blockers[edge.target].add(edge.source)
    return tuple(
        (target, _sorted_nodes(sources))
        for target, sources in sorted(
            blockers.items(),
            key=lambda item: _node_key(item[0]),
        )
    )


def _fan_out_index(
    nodes: tuple[ResourceRef, ...],
    adjacency: dict[ResourceRef, tuple[ResourceRef, ...]],
) -> FanOutIndex:
    def reachable(source: ResourceRef) -> set[ResourceRef]:
        found: set[ResourceRef] = set()
        pending = list(adjacency[source])
        while pending:
            target = pending.pop()
            if target in found:
                continue
            found.add(target)
            pending.extend(adjacency[target])
        return found

    return tuple((node, len(reachable(node))) for node in nodes)


def _root_cause_index(
    nodes: tuple[ResourceRef, ...],
    adjacency: dict[ResourceRef, tuple[ResourceRef, ...]],
) -> RootCauseIndex:
    in_degree: dict[ResourceRef, int] = dict.fromkeys(nodes, 0)
    for targets in adjacency.values():
        for target in targets:
            in_degree[target] += 1
    roots = _sorted_nodes(node for node, degree in in_degree.items() if degree == 0)
    paths_by_root = {root: _shortest_paths(root, adjacency) for root in roots}
    return tuple(
        (
            target,
            tuple(
                paths_by_root[root][target]
                for root in roots
                if target in paths_by_root[root]
            ),
        )
        for target in nodes
    )


def _shortest_paths(
    root: ResourceRef,
    adjacency: dict[ResourceRef, tuple[ResourceRef, ...]],
) -> dict[ResourceRef, tuple[ResourceRef, ...]]:
    paths: dict[ResourceRef, tuple[ResourceRef, ...]] = {root: (root,)}
    pending: deque[ResourceRef] = deque([root])
    while pending:
        node = pending.popleft()
        for target in adjacency.get(node, ()):
            candidate = (*paths[node], target)
            current = paths.get(target)
            if current is None or _path_key(candidate) < _path_key(current):
                paths[target] = candidate
                pending.append(target)
    return paths


def _lookup_node_tuple(
    index: BlockerIndex,
    target: ResourceRef,
) -> tuple[ResourceRef, ...]:
    for node, values in index:
        if node == target:
            return values
    return ()


def _sorted_nodes(nodes: Iterable[ResourceRef]) -> tuple[ResourceRef, ...]:
    return tuple(sorted(nodes, key=_node_key))


def _node_key(node: ResourceRef) -> tuple[str, str]:
    return (node.kind.value, str(node.resource_id))


def _node_label(node: ResourceRef) -> str:
    return f"{node.kind.value}:{node.resource_id}"


def _path_key(path: tuple[ResourceRef, ...]) -> tuple[int, tuple[tuple[str, str], ...]]:
    return (len(path), tuple(_node_key(node) for node in path))


def _affected_path_key(
    item: AffectedPath,
) -> tuple[tuple[str, str], tuple[str, str], tuple[int, tuple[tuple[str, str], ...]]]:
    return (_node_key(item.root), _node_key(item.target), _path_key(item.path))
