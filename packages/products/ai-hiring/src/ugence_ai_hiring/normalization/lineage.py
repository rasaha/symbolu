"""Evidence lineage DAG.

Lineage nodes are immutable and store only their parent ids; children are
derived when a graph is materialized (a node's children are the nodes that name
it as a parent). This keeps nodes append-only while still exposing a full DAG
for reconstruction.

The Phase-2 lineage covers the ingestion operations:

    UPLOAD -> INTEGRITY -> PROVENANCE -> HASH -> EXTRACT -> NORMALIZE ->
    QUARANTINE -> CHUNK(s) -> EVIDENCE -> INDEX

Downstream phases (extraction, layer scores) will attach as further children of
the EVIDENCE node — no scoring is implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..errors import LineageError
from .models import LineageNode


@dataclass(frozen=True)
class LineageGraph:
    """A materialized, read-only view over a set of lineage nodes."""

    nodes: tuple[LineageNode, ...]

    def _by_id(self) -> dict[str, LineageNode]:
        return {n.node_id: n for n in self.nodes}

    def children_of(self, node_id: str) -> tuple[LineageNode, ...]:
        return tuple(n for n in self.nodes if node_id in n.parent_ids)

    def parents_of(self, node_id: str) -> tuple[LineageNode, ...]:
        by_id = self._by_id()
        node = by_id.get(node_id)
        if node is None:
            raise LineageError(f"lineage node '{node_id}' not found")
        return tuple(by_id[p] for p in node.parent_ids if p in by_id)

    def roots(self) -> tuple[LineageNode, ...]:
        return tuple(n for n in self.nodes if not n.parent_ids)

    def topological(self) -> tuple[LineageNode, ...]:
        """Return nodes in a deterministic dependency order (parents first)."""
        by_id = self._by_id()
        visited: dict[str, bool] = {}
        order: list[LineageNode] = []

        def visit(node: LineageNode, stack: frozenset[str]) -> None:
            if node.node_id in visited:
                return
            if node.node_id in stack:
                raise LineageError(f"cycle detected at lineage node '{node.node_id}'")
            for parent_id in node.parent_ids:
                parent = by_id.get(parent_id)
                if parent is not None:
                    visit(parent, stack | {node.node_id})
            visited[node.node_id] = True
            order.append(node)

        for node in sorted(self.nodes, key=lambda n: n.timestamp):
            visit(node, frozenset())
        return tuple(order)

    def as_edges(self) -> tuple[tuple[str, str], ...]:
        """Return (parent_id, child_id) edges for diagram/serialization."""
        edges: list[tuple[str, str]] = []
        for node in self.nodes:
            for parent_id in node.parent_ids:
                edges.append((parent_id, node.node_id))
        return tuple(edges)
