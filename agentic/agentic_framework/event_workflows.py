"""
Event-Driven Execution & Long-Lived Workflows (H17)
===================================================

Turns the bounded, continuous execution engine (H10–H16) into a persistent
orchestration engine: a workflow can **suspend**, **wait for an external
event**, and **resume deterministically** — without losing state or violating
any governance guarantee from the earlier phases.

```
Mission → Execute → WAIT → External Event → Resume → Continue → Complete
```

Execution is no longer assumed to be continuous.  A ``WorkflowInstance``
drives an H15 goal tree through the **unchanged** H16 coordinator; when a
READY goal is gated by an unsatisfied :class:`WaitCondition`, the workflow
suspends.  When a matching :class:`WorkflowEvent` arrives, the
:class:`WorkflowEngine` validates it, applies its effects to the shared H14
``WorkingMemory`` and H13 assumptions (through their public APIs), and resumes
**only the affected subtree** on the same H11 ``RunBudget``.

This layer adds orchestration over time only.  It does not modify H10–H16,
RunBudget, WorkingMemory, hierarchical planning, coordination, replanning,
plan validity, governance, authorization, ActionGate, TAP, tool execution, or
LLM providers — it composes on their public APIs.  Everything is deterministic
and in-process.

Excluded by design: distributed queues, Kafka, webhooks, cloud schedulers,
async networking, cross-process retries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from agentic.agentic_framework.working_memory import WorkingMemory, MemoryWrite
from agentic.agentic_framework.hierarchical_planning import (
    Goal,
    GoalStatus,
    GoalTree,
    MissionPlan,
)
from agentic.agentic_framework.coordination import (
    CapabilityRegistry,
    CoordinationGoal,
    Mission,
    Coordinator,
    AuthorityModel,
    MissionStatus,
)

__all__ = [
    "WorkflowStatus",
    "WaitKind",
    "EventType",
    "WaitCondition",
    "WorkflowEvent",
    "WorkflowTransition",
    "WorkflowTraceEntry",
    "WorkflowTrace",
    "WorkflowInstance",
    "WorkflowEngine",
    "ResumeEngine",
    "format_workflow_trace",
]


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class WorkflowStatus:
    """Append-only lifecycle of a workflow instance."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING = "WAITING"
    RESUMED = "RESUMED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


_TERMINAL_WF = {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED, WorkflowStatus.EXPIRED}


class WaitKind:
    WAIT_FOR_APPROVAL = "WAIT_FOR_APPROVAL"
    WAIT_FOR_FILE = "WAIT_FOR_FILE"
    WAIT_FOR_TIMER = "WAIT_FOR_TIMER"
    WAIT_FOR_EVENT = "WAIT_FOR_EVENT"


class EventType:
    """Common event types (any string is accepted)."""

    FILE_UPLOADED = "file_uploaded"
    APPROVAL_RECEIVED = "approval_received"
    TOOL_COMPLETED = "tool_completed"
    TIMEOUT = "timeout"
    TIMER = "timer"
    EXTERNAL_RESPONSE = "external_response"


# ---------------------------------------------------------------------------
# Wait condition (first-class)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class WaitCondition:
    """A deterministic gate that suspends a goal until a matching event.

    ``match`` is a set of key/value pairs the event payload must contain
    (subset match).  ``on_timeout`` decides what a timeout does: ``satisfy``
    proceeds as if the event arrived; ``fail`` fails the gated goal.
    """

    condition_id: str
    goal_id: str
    kind: str = WaitKind.WAIT_FOR_EVENT
    event_type: str = ""
    match: Tuple[Tuple[str, Any], ...] = ()
    min_confidence: float = 0.0
    on_timeout: str = "satisfy"   # "satisfy" | "fail"
    description: str = ""

    def match_dict(self) -> Dict[str, Any]:
        return dict(self.match)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "condition_id": self.condition_id,
            "goal_id": self.goal_id,
            "kind": self.kind,
            "event_type": self.event_type,
            "match": dict(self.match),
            "min_confidence": self.min_confidence,
            "on_timeout": self.on_timeout,
            "description": self.description,
        }


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------
@dataclass
class WorkflowEvent:
    """An external event delivered to the engine.

    Beyond identity/payload, an event may carry deterministic effects applied
    to the shared state *before* execution resumes: ``memory_writes`` /
    ``memory_invalidations`` (H14) and ``assumption_signals`` / ``introduces``
    (H13).
    """

    event_id: str
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    source: str = ""
    confidence: float = 1.0
    # Deterministic effects on shared state.
    memory_writes: List[MemoryWrite] = field(default_factory=list)
    memory_invalidations: List[str] = field(default_factory=list)
    assumption_signals: Dict[str, str] = field(default_factory=dict)
    introduces: List[Any] = field(default_factory=list)  # List[PlanAssumption]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
            "source": self.source,
            "confidence": self.confidence,
            "memory_writes": [w.key for w in self.memory_writes],
            "memory_invalidations": list(self.memory_invalidations),
            "assumption_signals": dict(self.assumption_signals),
        }


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------
@dataclass
class WorkflowTransition:
    from_status: str
    to_status: str
    reason: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"from_status": self.from_status, "to_status": self.to_status,
                "reason": self.reason, "timestamp": self.timestamp}


@dataclass
class WorkflowTraceEntry:
    seq: int
    kind: str            # STARTED | WAVE | SUSPENDED | EVENT | RESUMED | REPLANNED | COMPLETED | FAILED | TIMEOUT | WRONG_EVENT
    detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"seq": self.seq, "kind": self.kind, "detail": self.detail, "timestamp": self.timestamp}


class WorkflowTrace:
    """Append-only reconstruction of a workflow's lifecycle."""

    def __init__(self) -> None:
        self.entries: List[WorkflowTraceEntry] = []
        self._seq = 0

    def record(self, kind: str, detail: Dict[str, Any], timestamp: float = 0.0) -> None:
        self.entries.append(WorkflowTraceEntry(self._seq, kind, detail, timestamp))
        self._seq += 1

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]


# ---------------------------------------------------------------------------
# Workflow instance
# ---------------------------------------------------------------------------
class WorkflowInstance:
    """A long-lived, suspendable execution of one mission."""

    def __init__(
        self,
        workflow_id: str,
        plan: MissionPlan,
        memory: WorkingMemory,
        *,
        assumption_context: Optional[Any] = None,
        run_budget: Optional[Any] = None,
        wait_conditions: Optional[List[WaitCondition]] = None,
        created_at: float = 0.0,
    ) -> None:
        self.workflow_id = workflow_id
        self.plan = plan
        self.memory = memory
        self.assumption_context = assumption_context
        self.run_budget = run_budget
        self.wait_by_goal: Dict[str, WaitCondition] = {
            wc.goal_id: wc for wc in (wait_conditions or [])
        }
        self.satisfied: set = set()            # satisfied condition ids
        self.waiting_conditions: List[WaitCondition] = []
        self.current_goal: Optional[str] = None
        self.status = WorkflowStatus.CREATED
        self.history: List[WorkflowTransition] = []
        self.event_log: List[WorkflowEvent] = []
        self.coordination_results: List[Any] = []
        self.trace = WorkflowTrace()
        self.created_at = created_at
        self.resumed_at: Optional[float] = None
        self._wave = 0

    @property
    def tree(self) -> GoalTree:
        return self.plan.tree

    def transition(self, new_status: str, *, reason: str = "", timestamp: float = 0.0) -> None:
        if new_status == self.status:
            return
        self.history.append(WorkflowTransition(self.status, new_status, reason, timestamp))
        self.status = new_status

    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_WF

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "status": self.status,
            "current_goal": self.current_goal,
            "waiting_conditions": [wc.to_dict() for wc in self.waiting_conditions],
            "history": [t.to_dict() for t in self.history],
            "events": [e.to_dict() for e in self.event_log],
            "tree": self.tree.to_dict(),
            "trace": self.trace.to_list(),
            "run_budget": self.run_budget.snapshot() if self.run_budget is not None else None,
            "created_at": self.created_at,
            "resumed_at": self.resumed_at,
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
class WorkflowEngine:
    """Drives workflows: run until WAIT, then resume on matching events.

    Reuses the H16 :class:`Coordinator` unchanged for execution, the H15
    :class:`GoalTree` for structure, and H14/H13/H11 for state.  Adds only the
    time dimension: suspension on unsatisfied :class:`WaitCondition`s and
    deterministic resume.

    Args:
        registry: H16 :class:`CapabilityRegistry` of workers.
        authority: H16 :class:`AuthorityModel`.
        subtree_replanner: Optional H15 localized replanner
            ``(tree, failed_goal_id) -> List[Goal]``.
        max_waves: Hard cap on execution waves per advance (terminal).
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        authority: Optional[AuthorityModel] = None,
        subtree_replanner: Optional[Callable[[GoalTree, str], List[Goal]]] = None,
        max_waves: int = 64,
    ) -> None:
        self.registry = registry
        self.authority = authority or AuthorityModel()
        self.subtree_replanner = subtree_replanner
        self.max_waves = max_waves
        self.workflows: List[WorkflowInstance] = []

    # ----- creation -----
    def create_workflow(
        self,
        workflow_id: str,
        plan: MissionPlan,
        memory: WorkingMemory,
        *,
        assumption_context: Optional[Any] = None,
        run_budget: Optional[Any] = None,
        wait_conditions: Optional[List[WaitCondition]] = None,
        created_at: float = 0.0,
    ) -> WorkflowInstance:
        wf = WorkflowInstance(
            workflow_id, plan, memory, assumption_context=assumption_context,
            run_budget=run_budget, wait_conditions=wait_conditions, created_at=created_at,
        )
        self.workflows.append(wf)
        return wf

    # ----- assumption gating (H13, read-only) -----
    def _inherited_assumptions(self, tree: GoalTree, goal_id: str) -> List[str]:
        out: List[str] = []
        cur = tree.lookup(goal_id).goal
        seen: set = set()
        while cur is not None:
            out.extend(cur.assumptions)
            if cur.parent is None or cur.parent in seen or not tree.has(cur.parent):
                break
            seen.add(cur.parent)
            cur = tree.lookup(cur.parent).goal
        return out

    def _assumptions_ok(self, wf: WorkflowInstance, goal_id: str) -> bool:
        if wf.assumption_context is None:
            return True
        from agentic.agentic_framework.plan_validity import AssumptionState
        for aid in self._inherited_assumptions(wf.tree, goal_id):
            a = wf.assumption_context.registry.get(aid)
            if a is not None and a.state in (AssumptionState.INVALID, AssumptionState.EXPIRED):
                return False
        return True

    # ----- classification -----
    def _classify(self, wf: WorkflowInstance) -> Tuple[List[Any], List[Tuple[Any, WaitCondition]]]:
        tree = wf.tree
        completed = {n.goal.goal_id for n in tree.nodes() if n.status == GoalStatus.COMPLETED}
        failed = {n.goal.goal_id for n in tree.nodes() if n.status == GoalStatus.FAILED}
        ready: List[Any] = []
        waiting: List[Tuple[Any, WaitCondition]] = []
        for node in tree.leaves():
            if node.status in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.ABORTED, GoalStatus.EXECUTING):
                continue
            deps = node.goal.dependencies
            if any(d in failed for d in deps):
                node.transition(GoalStatus.BLOCKED, reason="dependency failed")
                continue
            if not all(d in completed for d in deps):
                node.transition(GoalStatus.BLOCKED, reason="waiting on dependencies")
                continue
            # A pending wait condition takes precedence over an (invalid)
            # assumption: the awaited event may itself satisfy the assumption,
            # so the goal WAITS rather than hard-failing.
            wc = wf.wait_by_goal.get(node.goal.goal_id)
            if wc is not None and wc.condition_id not in wf.satisfied:
                node.transition(GoalStatus.BLOCKED, reason=f"waiting for {wc.event_type or wc.kind}")
                waiting.append((node, wc))
                continue
            if not self._assumptions_ok(wf, node.goal.goal_id):
                node.transition(GoalStatus.BLOCKED, reason="assumption invalid")
                continue
            node.transition(GoalStatus.READY, reason="ready")
            ready.append(node)
        ready.sort(key=lambda n: (n.goal.priority, n.goal.goal_id))
        return ready, waiting

    # ----- roll-up (mirrors H15 semantics, on the shared tree) -----
    def _rollup(self, tree: GoalTree) -> None:
        for node in sorted(tree.nodes(), key=lambda n: -len(tree.subtree(n.goal.goal_id))):
            g = node.goal
            if g.is_leaf or node.status in (GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.ABORTED):
                continue
            children = tree.children_of(g.goal_id)
            mandatory = [c for c in children if c.goal.mandatory and c.status != GoalStatus.ABORTED]
            if mandatory and all(c.status == GoalStatus.COMPLETED for c in mandatory):
                node.transition(GoalStatus.COMPLETED, reason="all children completed")
            elif any(c.status == GoalStatus.FAILED for c in mandatory):
                node.transition(GoalStatus.FAILED, reason="mandatory child failed")

    @staticmethod
    def _cg(goal: Goal) -> CoordinationGoal:
        return CoordinationGoal(
            goal_id=goal.goal_id, description=goal.description, goal_type=goal.goal_type,
            required_capabilities=goal.required_capabilities, authority_scope=goal.authority_scope,
            required_memory=goal.required_memory, produces_memory=goal.produced_memory,
            expected_outputs=goal.expected_outputs or goal.produced_memory,
            completion_criteria=goal.completion_criteria, mandatory=goal.mandatory,
        )

    def _mandatory_done(self, tree: GoalTree) -> bool:
        leaves = [n for n in tree.leaves() if n.goal.mandatory and n.status != GoalStatus.ABORTED]
        return all(n.status == GoalStatus.COMPLETED for n in leaves)

    def _mandatory_failed(self, tree: GoalTree) -> bool:
        leaves = [n for n in tree.leaves() if n.goal.mandatory and n.status != GoalStatus.ABORTED]
        return any(n.status in (GoalStatus.FAILED, GoalStatus.BLOCKED) for n in leaves)

    # ----- execution -----
    def start(self, wf: WorkflowInstance) -> WorkflowInstance:
        """Run the workflow until it suspends (WAIT) or terminates."""
        wf.plan.tree.validate_acyclic()
        wf.trace.record("STARTED", {"mission": wf.plan.mission_id}, wf.created_at)
        return self._advance(wf, timestamp=wf.created_at)

    def _advance(self, wf: WorkflowInstance, *, timestamp: float = 0.0) -> WorkflowInstance:
        if wf.is_terminal():
            return wf
        wf.transition(WorkflowStatus.RUNNING, reason="advance", timestamp=timestamp)
        coordinator = Coordinator(self.registry, wf.memory, run_budget=wf.run_budget, authority=self.authority)

        for _ in range(self.max_waves):
            ready, _waiting = self._classify(wf)
            if not ready:
                break
            for node in ready:
                node.transition(GoalStatus.EXECUTING, reason="delegated", timestamp=timestamp)
            mission = Mission.of(f"{wf.workflow_id}::w{wf._wave}", [self._cg(n.goal) for n in ready])
            coordination = coordinator.run(mission)
            wf.coordination_results.append(coordination)

            replanned: List[str] = []
            for gid in coordination.completed_goals:
                node = wf.tree.lookup(gid)
                a = coordination.assignment_for(gid)
                node.assigned_agent = a.agent_id if a else None
                node.transition(GoalStatus.COMPLETED, reason="worker completed", timestamp=timestamp)
            for gid in coordination.failed_goals:
                wf.tree.lookup(gid).transition(GoalStatus.FAILED, reason="worker failed", timestamp=timestamp)
                if self.subtree_replanner is not None:
                    new_goals = list(self.subtree_replanner(wf.tree, gid))
                    if new_goals:
                        wf.tree.replace_leaf(gid, new_goals)
                        replanned.append(gid)
            self._rollup(wf.tree)
            wf.trace.record("WAVE", {
                "wave": wf._wave,
                "ready": [n.goal.goal_id for n in ready],
                "completed": list(coordination.completed_goals),
                "failed": list(coordination.failed_goals),
                "replanned": replanned,
                "coordination_status": coordination.status,
            }, timestamp)
            wf._wave += 1
            if coordination.status == MissionStatus.BUDGET_EXHAUSTED:
                wf.transition(WorkflowStatus.FAILED, reason="budget exhausted", timestamp=timestamp)
                wf.trace.record("FAILED", {"reason": "budget exhausted"}, timestamp)
                return wf

        # Decide: suspend on waits, else terminal.
        _ready, waiting = self._classify(wf)
        if waiting:
            wf.waiting_conditions = [wc for (_n, wc) in waiting]
            wf.current_goal = waiting[0][0].goal.goal_id
            wf.transition(WorkflowStatus.WAITING, reason="awaiting external events", timestamp=timestamp)
            wf.trace.record("SUSPENDED", {
                "waiting_on": [wc.condition_id for wc in wf.waiting_conditions],
                "goals": [wc.goal_id for wc in wf.waiting_conditions],
            }, timestamp)
        elif self._mandatory_done(wf.tree):
            wf.transition(WorkflowStatus.COMPLETED, reason="all required goals completed", timestamp=timestamp)
            wf.trace.record("COMPLETED", {"completed": [n.goal.goal_id for n in wf.tree.nodes()
                                                        if n.status == GoalStatus.COMPLETED]}, timestamp)
        else:
            wf.transition(WorkflowStatus.FAILED, reason="mandatory goal unreachable", timestamp=timestamp)
            wf.trace.record("FAILED", {"failed": [n.goal.goal_id for n in wf.tree.nodes()
                                                  if n.status == GoalStatus.FAILED]}, timestamp)
        return wf

    # ----- event delivery / resume -----
    def _matches(self, wc: WaitCondition, event: WorkflowEvent) -> bool:
        if wc.event_type and event.type != wc.event_type:
            return False
        if event.confidence < wc.min_confidence:
            return False
        for k, v in wc.match_dict().items():
            if event.payload.get(k) != v:
                return False
        return True

    def _apply_event(self, wf: WorkflowInstance, event: WorkflowEvent) -> None:
        """Apply the event's deterministic effects to shared state (H14/H13)."""
        for w in event.memory_writes:
            wf.memory.write(w.key, w.value, category=w.category, confidence=w.confidence,
                            provenance=f"event:{event.event_id}", producing_step=f"event:{event.event_id}",
                            timestamp=event.timestamp)
        for key in event.memory_invalidations:
            wf.memory.invalidate(key, reason=f"event:{event.type}", timestamp=event.timestamp)
        if wf.assumption_context is not None:
            for intro in event.introduces:
                if not wf.assumption_context.registry.has(intro.assumption_id):
                    wf.assumption_context.registry.add(intro)
            for aid, state in event.assumption_signals.items():
                a = wf.assumption_context.registry.get(aid)
                if a is not None and a.state != state:
                    a.transition(state, reason=f"event:{event.type}", timestamp=event.timestamp)

    def deliver(
        self, event: WorkflowEvent, *, to: Optional[WorkflowInstance] = None
    ) -> List[WorkflowInstance]:
        """Route *event* to matching WAITING workflows and resume them.

        Deterministic routing: workflows are considered in creation order; a
        workflow matches only if it is WAITING and holds a waiting condition
        the event satisfies.  A non-matching event leaves the workflow WAITING.
        Returns the workflows that resumed.
        """
        targets = [to] if to is not None else list(self.workflows)
        affected: List[WorkflowInstance] = []
        for wf in targets:
            if wf.status != WorkflowStatus.WAITING:
                continue
            matched = next((wc for wc in wf.waiting_conditions if self._matches(wc, event)), None)
            if matched is None:
                wf.trace.record("WRONG_EVENT", {"event_id": event.event_id, "type": event.type}, event.timestamp)
                continue  # stays WAITING

            # Timeout handling (deterministic).
            if event.type == EventType.TIMEOUT and matched.on_timeout == "fail":
                wf.tree.lookup(matched.goal_id).transition(GoalStatus.FAILED, reason="timeout", timestamp=event.timestamp)
                if self.subtree_replanner is not None:
                    new_goals = list(self.subtree_replanner(wf.tree, matched.goal_id))
                    if new_goals:
                        wf.tree.replace_leaf(matched.goal_id, new_goals)
                wf.trace.record("TIMEOUT", {"condition_id": matched.condition_id, "goal_id": matched.goal_id,
                                            "action": "fail"}, event.timestamp)
            else:
                # Satisfy the wait (also the WAIT_FOR_TIMER 'satisfy' path).
                self._apply_event(wf, event)
                wf.trace.record("EVENT", {"event_id": event.event_id, "type": event.type,
                                          "condition_id": matched.condition_id,
                                          "memory_writes": [w.key for w in event.memory_writes],
                                          "assumption_signals": dict(event.assumption_signals)}, event.timestamp)

            wf.satisfied.add(matched.condition_id)
            wf.event_log.append(event)
            wf.resumed_at = event.timestamp
            wf.waiting_conditions = [wc for wc in wf.waiting_conditions if wc.condition_id != matched.condition_id]
            wf.transition(WorkflowStatus.RESUMED, reason=f"event:{event.type}", timestamp=event.timestamp)
            wf.trace.record("RESUMED", {"event_id": event.event_id}, event.timestamp)
            self._advance(wf, timestamp=event.timestamp)
            affected.append(wf)
        return affected

    def fire_timeout(self, wf: WorkflowInstance, condition_id: str, *, timestamp: float = 0.0) -> WorkflowInstance:
        """Deterministically fire a timeout for one waiting condition."""
        event = WorkflowEvent(event_id=f"timeout:{condition_id}", type=EventType.TIMEOUT,
                              payload={"condition_id": condition_id}, timestamp=timestamp)
        # Match by condition_id directly (bypass payload matching for timeouts).
        wc = next((c for c in wf.waiting_conditions if c.condition_id == condition_id), None)
        if wc is None or wf.status != WorkflowStatus.WAITING:
            return wf
        if wc.on_timeout == "fail":
            wf.tree.lookup(wc.goal_id).transition(GoalStatus.FAILED, reason="timeout", timestamp=timestamp)
            if self.subtree_replanner is not None:
                new_goals = list(self.subtree_replanner(wf.tree, wc.goal_id))
                if new_goals:
                    wf.tree.replace_leaf(wc.goal_id, new_goals)
            wf.trace.record("TIMEOUT", {"condition_id": condition_id, "goal_id": wc.goal_id, "action": "fail"}, timestamp)
        else:
            wf.trace.record("TIMEOUT", {"condition_id": condition_id, "goal_id": wc.goal_id, "action": "satisfy"}, timestamp)
        wf.satisfied.add(condition_id)
        wf.event_log.append(event)
        wf.resumed_at = timestamp
        wf.waiting_conditions = [c for c in wf.waiting_conditions if c.condition_id != condition_id]
        wf.transition(WorkflowStatus.RESUMED, reason="timeout", timestamp=timestamp)
        self._advance(wf, timestamp=timestamp)
        return wf

    def cancel(self, wf: WorkflowInstance, *, reason: str = "cancelled", timestamp: float = 0.0) -> None:
        if not wf.is_terminal():
            wf.transition(WorkflowStatus.CANCELLED, reason=reason, timestamp=timestamp)
            wf.trace.record("FAILED", {"reason": reason, "cancelled": True}, timestamp)


#: The resume behaviour is part of the engine; alias for callers that think of
#: it as a distinct component (per the H17 API list).
ResumeEngine = WorkflowEngine


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_workflow_trace(wf: WorkflowInstance) -> str:
    lines = [
        f"Workflow: {wf.workflow_id}  ({wf.plan.mission_id})",
        f"status={wf.status}  current_goal={wf.current_goal}",
        "=" * 60,
    ]
    for e in wf.trace.entries:
        if e.kind == "WAVE":
            lines.append(f"  {e.seq}: WAVE {e.detail['wave']} ready={e.detail['ready']} "
                         f"completed={e.detail['completed']}"
                         + (f" failed={e.detail['failed']}" if e.detail['failed'] else ""))
        elif e.kind == "SUSPENDED":
            lines.append(f"  {e.seq}: WAIT on {e.detail['waiting_on']} (goals {e.detail['goals']})")
        elif e.kind == "EVENT":
            lines.append(f"  {e.seq}: EVENT {e.detail['type']} → condition {e.detail['condition_id']}")
        elif e.kind == "WRONG_EVENT":
            lines.append(f"  {e.seq}: (ignored non-matching event {e.detail['type']})")
        else:
            lines.append(f"  {e.seq}: {e.kind} {e.detail}")
    return "\n".join(lines)
