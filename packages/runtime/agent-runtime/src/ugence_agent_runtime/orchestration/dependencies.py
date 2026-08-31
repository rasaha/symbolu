"""Cross-workflow dependency graph for the H22-B portfolio scheduler.

A deterministic DAG over *workflow registrations* (identified by ``instance_id``). It
records edges of the form "the dependent workflow requires something of the predecessor
workflow" and answers three questions the scheduler needs, all deterministically:

* is this edge *satisfied*, still *pending*, or a hard *failure* — given the predecessor's
  current runtime status?
* what is a workflow's *dependency depth* (longest path from a root), a stable ordering
  signal so upstream workflows are preferred?
* is the graph acyclic (a self-dependency, an unknown reference, or any cycle is rejected)?

This module is pure orchestration metadata. It imports only the runtime's neutral
``WorkflowStatus`` enum and never the engine — the dependency direction is
orchestration → runtime, never the reverse. It calls no provider and no governance hook;
it only *reads* a status the runtime already owns.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Mapping, Sequence, Tuple

from ..models.workflow import TERMINAL_WORKFLOW_STATUSES, WorkflowStatus


class DependencyType(str, Enum):
    """The kind of cross-workflow prerequisite one workflow declares on another.

    H22-B implements exactly the two dependency types the packaged Agent Runtime can
    represent *durably and cleanly* from committed runtime state — a workflow's terminal
    status. Richer dependency types (``REQUIRES_OUTPUT`` / ``REQUIRES_MILESTONE`` /
    ``REQUIRES_REVIEW_DECISION``) require a durable public representation of workflow
    outputs / milestones / review decisions that the packaged runtime does not yet expose;
    they are documented as later extensions (H22-C+) rather than invented here.
    """

    #: The dependent may run once the predecessor reaches *any* terminal state (COMPLETED,
    #: FAILED, or CANCELLED). "Wait until it is done, however it ends." A failed or
    #: cancelled predecessor still *satisfies* completion — it never blocks the dependent.
    REQUIRES_COMPLETION = "REQUIRES_COMPLETION"
    #: The dependent may run only if the predecessor reached COMPLETED (success). This is
    #: fail-closed: a predecessor that is terminal but NOT COMPLETED (FAILED or CANCELLED)
    #: turns the dependent into ``BLOCKED_DEPENDENCY`` — a failed success-prerequisite
    #: never silently becomes satisfied.
    REQUIRES_SUCCESS = "REQUIRES_SUCCESS"


class DependencyState(str, Enum):
    """The evaluation of a single dependency edge against live predecessor status."""

    #: The prerequisite is met; this edge does not hold the dependent back.
    SATISFIED = "SATISFIED"
    #: The prerequisite is not met yet, but still could be (predecessor not terminal).
    PENDING = "PENDING"
    #: The prerequisite can never be met (a hard success-requirement whose predecessor
    #: reached a non-success terminal state). Fail-closed — the dependent is blocked.
    FAILED = "FAILED"


@dataclass(frozen=True)
class WorkflowDependency:
    """One immutable directed edge: ``dependent`` requires ``requires_id`` (the predecessor).

    Edge identity is the pair ``(dependent_id, requires_id)`` plus the ``dep_type``. The
    graph rejects a self-edge and treats a duplicate ``(dependent, predecessor)`` pair as a
    conflict when the type differs (ambiguous), and as an idempotent no-op when identical.
    """

    dependent_id: str
    requires_id: str
    dep_type: DependencyType = DependencyType.REQUIRES_COMPLETION

    def evaluate(self, predecessor_status: WorkflowStatus) -> DependencyState:
        """Classify this edge from the predecessor's current runtime status.

        Deterministic and side-effect free: reads status only. See :class:`DependencyType`
        for the exact semantics (SUCCESS is fail-closed; COMPLETION is permissive)."""
        terminal = predecessor_status in TERMINAL_WORKFLOW_STATUSES
        if self.dep_type is DependencyType.REQUIRES_COMPLETION:
            return DependencyState.SATISFIED if terminal else DependencyState.PENDING
        # REQUIRES_SUCCESS
        if predecessor_status is WorkflowStatus.COMPLETED:
            return DependencyState.SATISFIED
        if terminal:  # terminal but not COMPLETED -> can never succeed
            return DependencyState.FAILED
        return DependencyState.PENDING


class DependencyGraph:
    """A validated, acyclic dependency graph over a fixed set of workflow nodes.

    Construction validates the whole graph fail-closed: every edge must reference known
    nodes, no edge may be a self-dependency, and the edge set must be acyclic (direct and
    indirect cycles are both rejected). Traversal (depth, topological order) is
    deterministic — driven by the caller-supplied node order, never dict iteration order.
    """

    def __init__(
        self,
        nodes: Sequence[str],
        edges: Sequence[WorkflowDependency] = (),
    ) -> None:
        self._nodes: Tuple[str, ...] = tuple(nodes)
        node_set = set(self._nodes)
        if len(node_set) != len(self._nodes):
            raise ValueError("DependencyGraph nodes must be unique")

        # Predecessors[dependent] = ordered list of the ids it requires.
        self._requires: Dict[str, List[str]] = {n: [] for n in self._nodes}
        self._edges: List[WorkflowDependency] = []
        seen_pairs: Dict[Tuple[str, str], DependencyType] = {}
        for e in edges:
            if e.dependent_id not in node_set:
                raise ValueError(
                    f"dependency references unknown dependent workflow {e.dependent_id!r}"
                )
            if e.requires_id not in node_set:
                raise ValueError(
                    f"dependency references unknown predecessor workflow {e.requires_id!r}"
                )
            if e.dependent_id == e.requires_id:
                raise ValueError(
                    f"workflow {e.dependent_id!r} cannot depend on itself"
                )
            pair = (e.dependent_id, e.requires_id)
            if pair in seen_pairs:
                if seen_pairs[pair] is not e.dep_type:
                    raise ValueError(
                        f"conflicting dependency types for edge {pair}: "
                        f"{seen_pairs[pair].value} vs {e.dep_type.value}"
                    )
                # Exact duplicate edge — idempotent, keep one.
                continue
            seen_pairs[pair] = e.dep_type
            self._requires[e.dependent_id].append(e.requires_id)
            self._edges.append(e)

        self._assert_acyclic()
        self._depths = self._compute_depths()

    # -- structure ----------------------------------------------------------
    @property
    def nodes(self) -> Tuple[str, ...]:
        return self._nodes

    @property
    def edges(self) -> Tuple[WorkflowDependency, ...]:
        return tuple(self._edges)

    def requires(self, instance_id: str) -> Tuple[str, ...]:
        """The predecessors ``instance_id`` directly requires, in registration order."""
        return tuple(self._requires.get(instance_id, ()))

    def dependencies_of(self, instance_id: str) -> Tuple[WorkflowDependency, ...]:
        """Every edge whose dependent is ``instance_id`` (deterministic order)."""
        return tuple(e for e in self._edges if e.dependent_id == instance_id)

    def depth(self, instance_id: str) -> int:
        """Longest path from a root to ``instance_id`` (a root has depth 0).

        Lower depth = more upstream. Deterministic and well-defined because the graph is
        acyclic."""
        return self._depths[instance_id]

    # -- validation ---------------------------------------------------------
    def _assert_acyclic(self) -> None:
        # Deterministic DFS over nodes in registration order. Colors: 0=unvisited,
        # 1=on-stack, 2=done. An edge to an on-stack node is a back edge -> cycle.
        color: Dict[str, int] = {n: 0 for n in self._nodes}

        def visit(node: str, stack: List[str]) -> None:
            color[node] = 1
            stack.append(node)
            for pred in self._requires[node]:
                if color[pred] == 1:
                    cycle = stack[stack.index(pred):] + [pred]
                    raise ValueError(
                        "dependency cycle detected: " + " -> ".join(cycle)
                    )
                if color[pred] == 0:
                    visit(pred, stack)
            stack.pop()
            color[node] = 2

        for n in self._nodes:
            if color[n] == 0:
                visit(n, [])

    def _compute_depths(self) -> Dict[str, int]:
        # Memoized longest-path-to-root over the acyclic graph, in registration order.
        depths: Dict[str, int] = {}

        def resolve(node: str) -> int:
            if node in depths:
                return depths[node]
            preds = self._requires[node]
            depths[node] = 0 if not preds else 1 + max(resolve(p) for p in preds)
            return depths[node]

        for n in self._nodes:
            resolve(n)
        return depths

    def classify_dependencies(
        self, instance_id: str, statuses: Mapping[str, WorkflowStatus]
    ) -> DependencyState:
        """Fold every edge of ``instance_id`` into a single dependency verdict.

        Fail-closed precedence: any FAILED edge dominates (→ FAILED); else any PENDING edge
        (→ PENDING); else SATISFIED (including the no-dependency case). ``statuses`` maps
        predecessor ids to their current runtime status."""
        verdict = DependencyState.SATISFIED
        for edge in self.dependencies_of(instance_id):
            state = edge.evaluate(statuses[edge.requires_id])
            if state is DependencyState.FAILED:
                return DependencyState.FAILED
            if state is DependencyState.PENDING:
                verdict = DependencyState.PENDING
        return verdict
