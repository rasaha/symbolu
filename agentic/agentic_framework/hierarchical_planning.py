"""
Hierarchical Planning & Goal Decomposition (H15)
================================================

Deterministic hierarchical planning that decomposes a mission into an
explicit tree of goals and subgoals, then feeds *ready* leaf goals to the
**unchanged** H16 coordinator for governed execution.

```
Mission → Mission Plan → Goal Tree → Ready Child Goals
       → H16 Coordinator → Workers
```

Planning decides **what** should be executed; H16 decides **who** executes
it.  This phase fills the architectural gap H16 was intentionally designed
to support — H16 is planning-strategy agnostic, so H15 plugs in through its
public API without any change to it.

This layer adds hierarchical planning only.  It does not modify H10 iterative
execution, H11 RunBudget, H12 replanning, H13 plan validity, H14
WorkingMemory, H16 coordination, governance, authorization, ActionGate, TAP,
tool execution, or LLM providers — it composes on their public APIs.  The
whole hierarchy shares one ``WorkingMemory`` and one ``RunBudget``.

Excluded by design: autonomous goal invention, planning search, Monte-Carlo
planning, reinforcement learning, parallel scheduling, negotiation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace as dc_replace
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Protocol, Set, Tuple

from agentic.agentic_framework.working_memory import WorkingMemory
from agentic.agentic_framework.coordination import (
    AgentProfile,  # noqa: F401  (re-exported convenience for callers)
    CapabilityRegistry,
    CoordinationGoal,
    Mission,
    Coordinator,
    AuthorityModel,
    MissionStatus,
)

__all__ = [
    "GoalStatus",
    "HierarchyStatus",
    "Goal",
    "GoalTransition",
    "GoalNode",
    "GoalDependency",
    "GoalTree",
    "MissionPlan",
    "GoalDecomposer",
    "StaticDecomposer",
    "RuleBasedDecomposer",
    "WaveRecord",
    "HierarchyTrace",
    "HierarchyResult",
    "HierarchyExecutor",
    "format_goal_tree",
    "format_hierarchy_trace",
]


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class GoalStatus:
    """Append-only lifecycle of a goal node."""

    CREATED = "CREATED"
    READY = "READY"
    BLOCKED = "BLOCKED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    ABORTED = "ABORTED"


class HierarchyStatus:
    """Terminal status of a hierarchical mission."""

    MISSION_COMPLETED = "MISSION_COMPLETED"
    MISSION_FAILED = "MISSION_FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


# Terminal = never re-executed.  ABORTED means "replaced by a localized
# replan" — it is NOT a failure and does not block dependents or the mission.
_TERMINAL = {GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.ABORTED}
_FAILED = {GoalStatus.FAILED}


# ---------------------------------------------------------------------------
# Goal (declarative, immutable)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Goal:
    """An immutable declaration of a goal in the hierarchy.

    Runtime status lives on :class:`GoalNode`; ``Goal`` is the static spec.
    """

    goal_id: str
    description: str
    parent: Optional[str] = None
    children: Tuple[str, ...] = ()
    priority: int = 0                      # lower runs first within a wave
    dependencies: Tuple[str, ...] = ()     # predecessor goal ids
    assumptions: Tuple[str, ...] = ()
    required_memory: Tuple[str, ...] = ()
    produced_memory: Tuple[str, ...] = ()
    completion_criteria: str = ""
    mandatory: bool = True
    # Execution attributes used when a leaf goal is delegated via H16.
    goal_type: str = ""
    required_capabilities: FrozenSet[str] = frozenset()
    authority_scope: FrozenSet[str] = frozenset()
    expected_outputs: Tuple[str, ...] = ()

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "parent": self.parent,
            "children": list(self.children),
            "priority": self.priority,
            "dependencies": list(self.dependencies),
            "assumptions": list(self.assumptions),
            "required_memory": list(self.required_memory),
            "produced_memory": list(self.produced_memory),
            "completion_criteria": self.completion_criteria,
            "mandatory": self.mandatory,
            "goal_type": self.goal_type,
            "required_capabilities": sorted(self.required_capabilities),
            "authority_scope": sorted(self.authority_scope),
            "expected_outputs": list(self.expected_outputs),
        }


@dataclass
class GoalTransition:
    from_status: str
    to_status: str
    reason: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"from_status": self.from_status, "to_status": self.to_status,
                "reason": self.reason, "timestamp": self.timestamp}


@dataclass
class GoalNode:
    """Runtime node: a goal + its append-only status history."""

    goal: Goal
    status: str = GoalStatus.CREATED
    history: List[GoalTransition] = field(default_factory=list)
    assigned_agent: Optional[str] = None

    def transition(self, new_status: str, *, reason: str = "", timestamp: float = 0.0) -> None:
        if new_status == self.status:
            return
        self.history.append(GoalTransition(self.status, new_status, reason, timestamp))
        self.status = new_status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal.to_dict(),
            "status": self.status,
            "assigned_agent": self.assigned_agent,
            "history": [t.to_dict() for t in self.history],
        }


@dataclass(frozen=True)
class GoalDependency:
    """A declared dependency edge (predecessor → successor)."""

    predecessor: str
    successor: str


# ---------------------------------------------------------------------------
# Goal tree (acyclic)
# ---------------------------------------------------------------------------
class GoalTree:
    """A deterministic, acyclic tree of goals with a dependency graph."""

    def __init__(self) -> None:
        self._nodes: Dict[str, GoalNode] = {}
        self.root_ids: List[str] = []

    # ----- construction -----
    def add_goal(self, goal: Goal) -> GoalNode:
        if goal.goal_id in self._nodes:
            raise ValueError(f"goal '{goal.goal_id}' already in tree")
        node = GoalNode(goal=goal)
        self._nodes[goal.goal_id] = node
        if goal.parent is None:
            if goal.goal_id not in self.root_ids:
                self.root_ids.append(goal.goal_id)
        return node

    def add_child(self, parent_id: str, goal: Goal) -> GoalNode:
        if parent_id not in self._nodes:
            raise KeyError(f"unknown parent '{parent_id}'")
        child = dc_replace(goal, parent=parent_id)
        node = self.add_goal(child)
        parent = self._nodes[parent_id]
        if child.goal_id not in parent.goal.children:
            parent.goal = dc_replace(parent.goal, children=parent.goal.children + (child.goal_id,))
        return node

    def remove_child(self, goal_id: str) -> None:
        node = self._nodes.pop(goal_id, None)
        if node is None:
            return
        if goal_id in self.root_ids:
            self.root_ids.remove(goal_id)
        parent_id = node.goal.parent
        if parent_id and parent_id in self._nodes:
            parent = self._nodes[parent_id]
            parent.goal = dc_replace(
                parent.goal,
                children=tuple(c for c in parent.goal.children if c != goal_id),
            )

    # ----- lookup -----
    def lookup(self, goal_id: str) -> GoalNode:
        return self._nodes[goal_id]

    def has(self, goal_id: str) -> bool:
        return goal_id in self._nodes

    def nodes(self) -> List[GoalNode]:
        return list(self._nodes.values())

    def goal_ids(self) -> List[str]:
        return list(self._nodes)

    def children_of(self, goal_id: str) -> List[GoalNode]:
        return [self._nodes[c] for c in self._nodes[goal_id].goal.children if c in self._nodes]

    def leaves(self) -> List[GoalNode]:
        return [n for n in self._nodes.values() if n.goal.is_leaf]

    def subtree(self, goal_id: str) -> Set[str]:
        """All goal ids in the subtree rooted at *goal_id* (inclusive)."""
        out: Set[str] = set()
        stack = [goal_id]
        while stack:
            cur = stack.pop()
            if cur in out or cur not in self._nodes:
                continue
            out.add(cur)
            stack.extend(self._nodes[cur].goal.children)
        return out

    # ----- dependency graph -----
    def predecessors(self, goal_id: str) -> Tuple[str, ...]:
        return self._nodes[goal_id].goal.dependencies

    def successors(self, goal_id: str) -> List[str]:
        return [nid for nid, n in self._nodes.items() if goal_id in n.goal.dependencies]

    def dependencies(self) -> List[GoalDependency]:
        edges: List[GoalDependency] = []
        for nid, n in self._nodes.items():
            for dep in n.goal.dependencies:
                edges.append(GoalDependency(predecessor=dep, successor=nid))
        return edges

    def validate_acyclic(self) -> None:
        """Raise if the dependency graph (or parent tree) contains a cycle."""
        WHITE, GREY, BLACK = 0, 1, 2
        color = {nid: WHITE for nid in self._nodes}

        def visit(nid: str) -> None:
            color[nid] = GREY
            for dep in self._nodes[nid].goal.dependencies:
                if dep not in self._nodes:
                    continue
                if color[dep] == GREY:
                    raise ValueError(f"dependency cycle detected at '{nid}' → '{dep}'")
                if color[dep] == WHITE:
                    visit(dep)
            color[nid] = BLACK

        for nid in self._nodes:
            if color[nid] == WHITE:
                visit(nid)

    # ----- localized replacement (subtree replan) -----
    def replace_leaf(self, goal_id: str, replacements: List[Goal]) -> List[str]:
        """Replace a failed leaf with *replacements* under the same parent.

        Only this leaf's subtree is affected: the leaf is aborted (history
        kept), the replacements are added, and any successor that depended on
        the failed leaf is rewired to depend on the replacements.  Sibling
        subtrees are untouched.
        """
        node = self._nodes[goal_id]
        node.transition(GoalStatus.ABORTED, reason="replaced by localized replan")
        parent_id = node.goal.parent
        new_ids: List[str] = []
        for g in replacements:
            g = dc_replace(g, parent=parent_id, dependencies=node.goal.dependencies)
            self.add_goal(g)
            new_ids.append(g.goal_id)
            if parent_id and parent_id in self._nodes:
                p = self._nodes[parent_id]
                p.goal = dc_replace(p.goal, children=p.goal.children + (g.goal_id,))
        # Rewire successors of the failed leaf onto the replacements.
        for nid, n in self._nodes.items():
            if goal_id in n.goal.dependencies:
                new_deps = tuple(d for d in n.goal.dependencies if d != goal_id) + tuple(new_ids)
                n.goal = dc_replace(n.goal, dependencies=new_deps)
        return new_ids

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_ids": list(self.root_ids),
            "nodes": {nid: n.to_dict() for nid, n in self._nodes.items()},
        }


@dataclass
class MissionPlan:
    """A decomposed mission: an id + its goal tree."""

    mission_id: str
    tree: GoalTree


# ---------------------------------------------------------------------------
# Decomposers (strategy-agnostic)
# ---------------------------------------------------------------------------
class GoalDecomposer(Protocol):
    """Turns a mission specification into a deterministic goal tree."""

    def decompose(
        self,
        mission_id: str,
        spec: Any,
        *,
        assumptions: Any = None,
        memory: Optional[WorkingMemory] = None,
        constraints: Any = None,
    ) -> MissionPlan:
        ...


class StaticDecomposer:
    """Builds a tree from an explicit list of :class:`Goal` declarations.

    Fully deterministic: the same goal list always yields the same tree.
    ``spec`` is the ``List[Goal]``.
    """

    def decompose(self, mission_id, spec, *, assumptions=None, memory=None, constraints=None) -> MissionPlan:
        tree = GoalTree()
        goals: List[Goal] = list(spec)
        # Insert parents before children (stable order) so add_goal never
        # references a missing parent.
        by_id = {g.goal_id: g for g in goals}

        def depth(g: Goal) -> int:
            d, cur = 0, g
            seen = set()
            while cur.parent is not None and cur.parent in by_id and cur.parent not in seen:
                seen.add(cur.parent)
                cur = by_id[cur.parent]
                d += 1
            return d

        for g in sorted(goals, key=lambda x: (depth(x), x.goal_id)):
            tree.add_goal(g)
        tree.validate_acyclic()
        return MissionPlan(mission_id=mission_id, tree=tree)


class RuleBasedDecomposer:
    """Deterministic rule-based decomposition.

    ``rules`` is a pure callable ``spec -> List[Goal]``; the same input must
    always return the same goals.  This is the seam for future symbolic or
    model-assisted decomposers — swap the callable, the runtime is unchanged.
    """

    def __init__(self, rules: Callable[[Any], List[Goal]]) -> None:
        self._rules = rules
        self._static = StaticDecomposer()

    def decompose(self, mission_id, spec, *, assumptions=None, memory=None, constraints=None) -> MissionPlan:
        goals = list(self._rules(spec))
        return self._static.decompose(mission_id, goals,
                                      assumptions=assumptions, memory=memory, constraints=constraints)


# ---------------------------------------------------------------------------
# Hierarchy trace
# ---------------------------------------------------------------------------
@dataclass
class WaveRecord:
    wave: int
    ready_goals: List[str]
    assignments: List[Dict[str, Any]]       # goal_id → agent/state from H16
    completed: List[str]
    failed: List[str]
    released: List[str]                      # goals that became READY afterward
    replanned: List[str] = field(default_factory=list)
    coordination_status: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wave": self.wave,
            "ready_goals": list(self.ready_goals),
            "assignments": list(self.assignments),
            "completed": list(self.completed),
            "failed": list(self.failed),
            "released": list(self.released),
            "replanned": list(self.replanned),
            "coordination_status": self.coordination_status,
        }


class HierarchyTrace:
    """Append-only record of every planning wave."""

    def __init__(self) -> None:
        self.waves: List[WaveRecord] = []

    def record(self, record: WaveRecord) -> None:
        self.waves.append(record)

    def to_list(self) -> List[Dict[str, Any]]:
        return [w.to_dict() for w in self.waves]


@dataclass
class HierarchyResult:
    mission_id: str
    status: str
    tree: GoalTree
    completed_goals: List[str] = field(default_factory=list)
    failed_goals: List[str] = field(default_factory=list)
    trace: Optional[HierarchyTrace] = None
    run_budget: Optional[Any] = None
    coordination_results: List[Any] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "status": self.status,
            "completed_goals": list(self.completed_goals),
            "failed_goals": list(self.failed_goals),
            "tree": self.tree.to_dict(),
            "trace": self.trace.to_list() if self.trace else [],
            "run_budget": self.run_budget.snapshot() if self.run_budget is not None else None,
        }


# ---------------------------------------------------------------------------
# Hierarchy executor — reuses the H16 coordinator unchanged
# ---------------------------------------------------------------------------
class HierarchyExecutor:
    """Executes a :class:`MissionPlan` by delegating READY leaf goals to H16.

    Wave loop: discover READY leaf goals → build an H16 ``Mission`` → run the
    unchanged :class:`Coordinator` → update goal statuses → release dependents
    → repeat.  All goals share one ``WorkingMemory`` and one ``RunBudget``.

    Args:
        registry: The H16 :class:`CapabilityRegistry` of workers.
        memory: The shared H14 ``WorkingMemory``.
        run_budget: The shared H11 ``RunBudget`` (never re-created).
        authority: H16 :class:`AuthorityModel`.
        assumption_context: Optional H13 ``AssumptionContext`` — a goal whose
            (inherited) assumptions are INVALID is blocked/escalated.
        subtree_replanner: Optional ``(tree, failed_goal_id) -> List[Goal]``
            that re-decomposes ONLY the failed leaf's subtree (localized H12
            replanning).  Returns replacement leaves, or empty for no replan.
        max_waves: Hard cap on planning waves (terminal).
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        memory: WorkingMemory,
        *,
        run_budget: Optional[Any] = None,
        authority: Optional[AuthorityModel] = None,
        assumption_context: Optional[Any] = None,
        subtree_replanner: Optional[Callable[[GoalTree, str], List[Goal]]] = None,
        max_waves: int = 64,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.run_budget = run_budget
        self.authority = authority or AuthorityModel()
        self.assumption_context = assumption_context
        self.subtree_replanner = subtree_replanner
        self.max_waves = max_waves

    # ----- assumption gating (H13, read-only) -----
    def _inherited_assumptions(self, tree: GoalTree, goal_id: str) -> List[str]:
        out: List[str] = []
        cur = tree.lookup(goal_id).goal
        seen = set()
        while cur is not None:
            out.extend(cur.assumptions)
            if cur.parent is None or cur.parent in seen or not tree.has(cur.parent):
                break
            seen.add(cur.parent)
            cur = tree.lookup(cur.parent).goal
        return out

    def _assumptions_ok(self, tree: GoalTree, goal_id: str) -> bool:
        if self.assumption_context is None:
            return True
        from agentic.agentic_framework.plan_validity import AssumptionState
        for aid in self._inherited_assumptions(tree, goal_id):
            a = self.assumption_context.registry.get(aid)
            if a is not None and a.state in (AssumptionState.INVALID, AssumptionState.EXPIRED):
                return False
        return True

    # ----- readiness -----
    def _ready_leaves(self, tree: GoalTree) -> List[GoalNode]:
        completed = {n.goal.goal_id for n in tree.nodes() if n.status == GoalStatus.COMPLETED}
        failed = {n.goal.goal_id for n in tree.nodes() if n.status in _FAILED}
        ready: List[GoalNode] = []
        for node in tree.leaves():
            if node.status in _TERMINAL or node.status == GoalStatus.EXECUTING:
                continue
            deps = node.goal.dependencies
            if any(d in failed for d in deps):
                node.transition(GoalStatus.BLOCKED, reason="dependency failed")
                continue
            if not all(d in completed for d in deps):
                if node.status != GoalStatus.BLOCKED:
                    node.transition(GoalStatus.BLOCKED, reason="waiting on dependencies")
                continue
            if not self._assumptions_ok(tree, node.goal.goal_id):
                node.transition(GoalStatus.BLOCKED, reason="assumption invalid")
                continue
            node.transition(GoalStatus.READY, reason="dependencies satisfied")
            ready.append(node)
        ready.sort(key=lambda n: (n.goal.priority, n.goal.goal_id))
        return ready

    # ----- roll-up of internal goals -----
    def _rollup(self, tree: GoalTree) -> None:
        # Deepest-first so parents see updated children.
        for node in sorted(tree.nodes(), key=lambda n: -len(tree.subtree(n.goal.goal_id))):
            g = node.goal
            if g.is_leaf or node.status in _TERMINAL:
                continue
            children = tree.children_of(g.goal_id)
            # ABORTED children were replaced by a localized replan — ignore them.
            mandatory = [c for c in children
                         if c.goal.mandatory and c.status != GoalStatus.ABORTED]
            if mandatory and all(c.status == GoalStatus.COMPLETED for c in mandatory):
                node.transition(GoalStatus.COMPLETED, reason="all children completed")
            elif any(c.status in _FAILED for c in mandatory):
                node.transition(GoalStatus.FAILED, reason="mandatory child failed")

    # ----- execution -----
    def run(self, plan: MissionPlan) -> HierarchyResult:
        tree = plan.tree
        tree.validate_acyclic()
        trace = HierarchyTrace()
        result = HierarchyResult(
            mission_id=plan.mission_id, status=HierarchyStatus.MISSION_COMPLETED,
            tree=tree, trace=trace, run_budget=self.run_budget,
        )
        coordinator = Coordinator(self.registry, self.memory, run_budget=self.run_budget,
                                  authority=self.authority)

        for wave in range(self.max_waves):
            ready = self._ready_leaves(tree)
            if not ready:
                break

            for node in ready:
                node.transition(GoalStatus.EXECUTING, reason="delegated", timestamp=float(wave))

            mission = Mission.of(
                f"{plan.mission_id}::wave{wave}",
                [self._to_coordination_goal(n.goal) for n in ready],
            )
            coordination = coordinator.run(mission)
            result.coordination_results.append(coordination)

            completed_ids: List[str] = list(coordination.completed_goals)
            failed_ids: List[str] = list(coordination.failed_goals)
            replanned: List[str] = []

            for gid in completed_ids:
                node = tree.lookup(gid)
                assignment = coordination.assignment_for(gid)
                node.assigned_agent = assignment.agent_id if assignment else None
                node.transition(GoalStatus.COMPLETED, reason="worker completed", timestamp=float(wave))
            for gid in failed_ids:
                node = tree.lookup(gid)
                node.transition(GoalStatus.FAILED, reason="worker failed", timestamp=float(wave))
                # Localized replanning: re-decompose ONLY this subtree.
                if self.subtree_replanner is not None:
                    new_goals = list(self.subtree_replanner(tree, gid))
                    if new_goals:
                        tree.replace_leaf(gid, new_goals)
                        replanned.append(gid)

            self._rollup(tree)

            # Which goals are newly READY for the next wave?
            released = [n.goal.goal_id for n in self._preview_ready(tree)]

            trace.record(WaveRecord(
                wave=wave,
                ready_goals=[n.goal.goal_id for n in ready],
                assignments=[{"goal_id": gid,
                              "agent": (coordination.assignment_for(gid).agent_id
                                        if coordination.assignment_for(gid) else None),
                              "state": tree.lookup(gid).status}
                             for gid in [n.goal.goal_id for n in ready]],
                completed=completed_ids,
                failed=failed_ids,
                released=released,
                replanned=replanned,
                coordination_status=coordination.status,
            ))

            if coordination.status == MissionStatus.BUDGET_EXHAUSTED:
                result.status = HierarchyStatus.BUDGET_EXHAUSTED
                break

        # Final roll-up + mission status from mandatory leaves.
        self._rollup(tree)
        result.completed_goals = [n.goal.goal_id for n in tree.nodes() if n.status == GoalStatus.COMPLETED]
        result.failed_goals = [n.goal.goal_id for n in tree.nodes() if n.status in _FAILED]

        if result.status != HierarchyStatus.BUDGET_EXHAUSTED:
            # ABORTED leaves were replaced by a localized replan — ignore them.
            mandatory_leaves = [n for n in tree.leaves()
                                if n.goal.mandatory and n.status != GoalStatus.ABORTED]
            if all(n.status == GoalStatus.COMPLETED for n in mandatory_leaves):
                result.status = HierarchyStatus.MISSION_COMPLETED
            else:
                result.status = HierarchyStatus.MISSION_FAILED
        return result

    def _preview_ready(self, tree: GoalTree) -> List[GoalNode]:
        """Non-mutating preview of goals that would be READY next."""
        completed = {n.goal.goal_id for n in tree.nodes() if n.status == GoalStatus.COMPLETED}
        failed = {n.goal.goal_id for n in tree.nodes() if n.status in _FAILED}
        out = []
        for node in tree.leaves():
            if node.status in _TERMINAL or node.status == GoalStatus.EXECUTING:
                continue
            deps = node.goal.dependencies
            if any(d in failed for d in deps):
                continue
            if all(d in completed for d in deps) and self._assumptions_ok(tree, node.goal.goal_id):
                out.append(node)
        return out

    @staticmethod
    def _to_coordination_goal(goal: Goal) -> CoordinationGoal:
        """Map a leaf :class:`Goal` to an H16 :class:`CoordinationGoal`.

        Within a wave all dependencies are already completed, so ``depends_on``
        is empty — the tree, not H16, sequences the hierarchy.
        """
        return CoordinationGoal(
            goal_id=goal.goal_id,
            description=goal.description,
            goal_type=goal.goal_type,
            required_capabilities=goal.required_capabilities,
            authority_scope=goal.authority_scope,
            required_memory=goal.required_memory,
            produces_memory=goal.produced_memory,
            expected_outputs=goal.expected_outputs or goal.produced_memory,
            completion_criteria=goal.completion_criteria,
            mandatory=goal.mandatory,
        )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_goal_tree(tree: GoalTree) -> str:
    lines = ["Goal tree", "-" * 52]

    def render(goal_id: str, indent: int) -> None:
        node = tree.lookup(goal_id)
        deps = f" deps={list(node.goal.dependencies)}" if node.goal.dependencies else ""
        agent = f" [{node.assigned_agent}]" if node.assigned_agent else ""
        lines.append("  " + "  " * indent + f"{goal_id}: {node.status}{deps}{agent}")
        for child in node.goal.children:
            if tree.has(child):
                render(child, indent + 1)

    for root in tree.root_ids:
        render(root, 0)
    return "\n".join(lines)


def format_hierarchy_trace(result: HierarchyResult) -> str:
    lines = [
        f"Hierarchy: {result.mission_id}",
        f"status={result.status}  completed={result.completed_goals}  failed={result.failed_goals}",
        "=" * 60,
    ]
    if result.trace is None:
        return "\n".join(lines)
    for w in result.trace.waves:
        lines.append(f"  wave {w.wave}: ready={w.ready_goals} → coordinator ({w.coordination_status})")
        for a in w.assignments:
            lines.append(f"      {a['goal_id']} → {a['agent']} [{a['state']}]")
        if w.completed:
            lines.append(f"      completed: {w.completed}")
        if w.failed:
            lines.append(f"      failed: {w.failed}" + (f"  replanned: {w.replanned}" if w.replanned else ""))
        if w.released:
            lines.append(f"      released → ready: {w.released}")
    return "\n".join(lines)
