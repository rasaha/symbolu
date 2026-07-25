"""Evidence-lineage integrity policy.

Deterministic validation of lineage edges and whole graphs: no self-parenting,
no cycles, existing parents, same-tenant/compatible context, monotonic version
ancestry, no conflicting immediate predecessors, and allowed edge operations.
Persisted nodes are immutable; duplicate edges are idempotent. All failures are
typed.
"""

from __future__ import annotations

from ..errors import (
    LineageConflictingParentError,
    LineageContextMismatchError,
    LineageCycleError,
    LineageError,
    LineageParentNotFoundError,
    LineageVersionRegressionError,
)
from ..normalization.lineage import LineageGraph
from ..normalization.models import LineageNode


def validate_new_node(node: LineageNode, existing: tuple[LineageNode, ...]) -> None:
    """Validate a single new node against the already-persisted nodes."""
    by_id = {n.node_id: n for n in existing}

    if node.node_id in node.parent_ids:
        raise LineageCycleError(f"node {node.node_id} cannot parent itself")

    for parent_id in node.parent_ids:
        parent = by_id.get(parent_id)
        if parent is None:
            raise LineageParentNotFoundError(f"parent {parent_id} not found")
        # context compatibility
        if parent.tenant_id != node.tenant_id:
            raise LineageContextMismatchError(
                f"parent {parent_id} tenant differs from child {node.node_id}"
            )
        if (parent.candidate_id and node.candidate_id
                and parent.candidate_id != node.candidate_id):
            raise LineageContextMismatchError(
                f"parent/child candidate mismatch on {node.node_id}"
            )
        # monotonic version ancestry (a child may not regress below its parent)
        if node.version < parent.version:
            raise LineageVersionRegressionError(
                f"node {node.node_id} v{node.version} regresses below parent v{parent.version}"
            )

    # would this introduce a cycle among existing nodes?
    if _creates_cycle(node, by_id):
        raise LineageCycleError(f"adding {node.node_id} would create a cycle")


def _creates_cycle(node: LineageNode, by_id: dict[str, LineageNode]) -> bool:
    # walk ancestors of each parent; if we reach node.node_id, it's a cycle
    stack = list(node.parent_ids)
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == node.node_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        parent = by_id.get(current)
        if parent is not None:
            stack.extend(parent.parent_ids)
    return False


def validate_graph(graph: LineageGraph) -> None:
    """Validate an entire lineage graph deterministically (raises on any defect)."""
    by_id = {n.node_id: n for n in graph.nodes}

    for node in graph.nodes:
        if node.node_id in node.parent_ids:
            raise LineageCycleError(f"self-parent at {node.node_id}")
        for parent_id in node.parent_ids:
            if parent_id not in by_id:
                raise LineageParentNotFoundError(f"missing parent {parent_id}")
            parent = by_id[parent_id]
            if parent.tenant_id != node.tenant_id:
                raise LineageContextMismatchError(f"tenant mismatch at edge {parent_id}->{node.node_id}")
            if node.version < parent.version:
                raise LineageVersionRegressionError(
                    f"version regression at edge {parent_id}->{node.node_id}"
                )

    # cycle detection over the whole graph (raises on cycle)
    try:
        graph.topological()
    except LineageError as exc:
        raise LineageCycleError(str(exc)) from exc


def check_conflicting_predecessors(
    version: int, immediate_parent_versions: tuple[int, ...]
) -> None:
    """A version must not have two *different* immediate predecessor versions."""
    distinct = set(immediate_parent_versions)
    if len(distinct) > 1:
        raise LineageConflictingParentError(
            f"version {version} has conflicting predecessors {sorted(distinct)}"
        )
