"""
Authority-Aware Multi-Agent Coordination (H16)
==============================================

Governed multi-agent coordination: a deterministic **coordinator** assigns
mission goals to **worker** agents through explicit authority, capability,
and immutable delegation contracts, while every agent shares the same H14
``WorkingMemory`` and the same H11 ``RunBudget``.

```
Mission → Coordinator → Assign Goal → Worker Agent → Shared State
       → Coordinator → Next Assignment
```

Three concerns are kept distinct:

* **coordination** — the coordinator chooses who does what (never executes
  worker tasks itself);
* **execution** — worker agents run the delegated goal under the shared
  budget and shared memory;
* **authorization** — every assignment must pass capability, authority,
  budget, and goal-ownership checks before a worker runs.

This layer adds coordination only.  It does not modify RunBudget,
WorkingMemory, replanning, plan validity, governance, authorization,
ActionGate, TAP, routing, tool execution, or LLM providers — it composes on
their public APIs.  It is planning-strategy agnostic: the coordinator
advances a mission's goals and can sit above any (future) hierarchical
planner without change.

Excluded by design: autonomous organization creation, self-modifying agents,
voting, negotiation, reinforcement learning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Protocol, Tuple

from agentic.agentic_framework.run_budget import (
    RunBudget,
    BudgetExhausted,
    attach_run_budget,
)
from agentic.agentic_framework.working_memory import WorkingMemory

__all__ = [
    "CoordinationState",
    "RejectionReason",
    "MissionStatus",
    "AgentProfile",
    "CapabilityRegistry",
    "CoordinationGoal",
    "Mission",
    "DelegationContract",
    "AgentAssignment",
    "AssignmentTransition",
    "GoalOwnershipLedger",
    "AuthorityDecision",
    "AuthorityModel",
    "WorkerResult",
    "WorkerExecutor",
    "ScriptedWorker",
    "AgentWorker",
    "CoordinationTraceEntry",
    "CoordinationTrace",
    "CoordinationResult",
    "Coordinator",
    "format_coordination_trace",
]

COORDINATOR_ID = "coordinator"


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class CoordinationState:
    """Append-only lifecycle of an assignment."""

    CREATED = "CREATED"
    ASSIGNED = "ASSIGNED"
    ACCEPTED = "ACCEPTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RejectionReason:
    """Deterministic reasons an assignment is rejected or fails."""

    CAPABILITY_MISMATCH = "CAPABILITY_MISMATCH"
    AUTHORITY_DENIED = "AUTHORITY_DENIED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    OWNERSHIP_CONFLICT = "OWNERSHIP_CONFLICT"
    AGENT_UNAVAILABLE = "AGENT_UNAVAILABLE"
    GOAL_UNSUPPORTED = "GOAL_UNSUPPORTED"
    DELEGATION_TIMEOUT = "DELEGATION_TIMEOUT"
    WORKER_FAILURE = "WORKER_FAILURE"
    NO_QUALIFIED_AGENT = "NO_QUALIFIED_AGENT"


class MissionStatus:
    """Terminal status of a coordinated mission."""

    MISSION_COMPLETED = "MISSION_COMPLETED"
    MISSION_FAILED = "MISSION_FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"


# ---------------------------------------------------------------------------
# Agent model (immutable during execution)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AgentProfile:
    """An immutable description of a worker agent's authority envelope."""

    agent_id: str
    role: str = ""
    capabilities: FrozenSet[str] = frozenset()
    permissions: FrozenSet[str] = frozenset()
    owned_tools: FrozenSet[str] = frozenset()
    supported_goals: FrozenSet[str] = frozenset()   # goal types; empty = any
    execution_limits: Tuple[Tuple[str, Any], ...] = ()  # frozen key/value pairs
    trust_level: int = 0

    def limits(self) -> Dict[str, Any]:
        return dict(self.execution_limits)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role,
            "capabilities": sorted(self.capabilities),
            "permissions": sorted(self.permissions),
            "owned_tools": sorted(self.owned_tools),
            "supported_goals": sorted(self.supported_goals),
            "execution_limits": dict(self.execution_limits),
            "trust_level": self.trust_level,
        }


class CapabilityRegistry:
    """Explicit registry mapping agents to their profiles + executors.

    Availability is tracked here (not on the immutable profile) so an agent
    can be marked unavailable during a mission without mutating its identity.
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, AgentProfile] = {}
        self._executors: Dict[str, "WorkerExecutor"] = {}
        self._unavailable: set = set()

    def register(self, profile: AgentProfile, executor: "WorkerExecutor") -> "CapabilityRegistry":
        if profile.agent_id in self._profiles:
            raise ValueError(f"agent '{profile.agent_id}' already registered")
        self._profiles[profile.agent_id] = profile
        self._executors[profile.agent_id] = executor
        return self

    def profile(self, agent_id: str) -> AgentProfile:
        return self._profiles[agent_id]

    def executor(self, agent_id: str) -> "WorkerExecutor":
        return self._executors[agent_id]

    def agent_ids(self) -> List[str]:
        return list(self._profiles)

    def is_available(self, agent_id: str) -> bool:
        return agent_id in self._profiles and agent_id not in self._unavailable

    def mark_unavailable(self, agent_id: str) -> None:
        self._unavailable.add(agent_id)

    def mark_available(self, agent_id: str) -> None:
        self._unavailable.discard(agent_id)

    def candidates_for(self, goal: "CoordinationGoal") -> List[AgentProfile]:
        """Deterministically ordered agents that *could* take *goal*.

        Filters by goal support + required capabilities + availability, then
        orders by (-trust_level, agent_id) so selection is reproducible.
        """
        out = []
        for aid, profile in self._profiles.items():
            if not self.is_available(aid):
                continue
            if goal.goal_type and profile.supported_goals and goal.goal_type not in profile.supported_goals:
                continue
            if not goal.required_capabilities.issubset(profile.capabilities):
                continue
            out.append(profile)
        out.sort(key=lambda p: (-p.trust_level, p.agent_id))
        return out


# ---------------------------------------------------------------------------
# Mission / goal
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class CoordinationGoal:
    """One goal in a mission, with its authority requirements."""

    goal_id: str
    description: str
    goal_type: str = ""
    required_capabilities: FrozenSet[str] = frozenset()
    authority_scope: FrozenSet[str] = frozenset()
    required_memory: Tuple[str, ...] = ()
    produces_memory: Tuple[str, ...] = ()
    expected_outputs: Tuple[str, ...] = ()
    timeout: Optional[float] = None
    completion_criteria: str = ""
    depends_on: Tuple[str, ...] = ()
    mandatory: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "description": self.description,
            "goal_type": self.goal_type,
            "required_capabilities": sorted(self.required_capabilities),
            "authority_scope": sorted(self.authority_scope),
            "required_memory": list(self.required_memory),
            "produces_memory": list(self.produces_memory),
            "expected_outputs": list(self.expected_outputs),
            "timeout": self.timeout,
            "completion_criteria": self.completion_criteria,
            "depends_on": list(self.depends_on),
            "mandatory": self.mandatory,
        }


@dataclass(frozen=True)
class Mission:
    """An ordered set of coordination goals."""

    mission_id: str
    goals: Tuple[CoordinationGoal, ...]

    @classmethod
    def of(cls, mission_id: str, goals: List[CoordinationGoal]) -> "Mission":
        return cls(mission_id=mission_id, goals=tuple(goals))


# ---------------------------------------------------------------------------
# Delegation contract (immutable)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class DelegationContract:
    """An immutable contract governing one delegation."""

    contract_id: str
    goal_id: str
    goal_description: str
    assigned_agent: str
    required_inputs: Tuple[str, ...] = ()
    expected_outputs: Tuple[str, ...] = ()
    required_memory: Tuple[str, ...] = ()
    assumptions: Tuple[str, ...] = ()
    authority_scope: FrozenSet[str] = frozenset()
    timeout: Optional[float] = None
    completion_criteria: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "goal_id": self.goal_id,
            "goal_description": self.goal_description,
            "assigned_agent": self.assigned_agent,
            "required_inputs": list(self.required_inputs),
            "expected_outputs": list(self.expected_outputs),
            "required_memory": list(self.required_memory),
            "assumptions": list(self.assumptions),
            "authority_scope": sorted(self.authority_scope),
            "timeout": self.timeout,
            "completion_criteria": self.completion_criteria,
        }


# ---------------------------------------------------------------------------
# Assignment (append-only lifecycle)
# ---------------------------------------------------------------------------
@dataclass
class AssignmentTransition:
    from_state: str
    to_state: str
    reason: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"from_state": self.from_state, "to_state": self.to_state,
                "reason": self.reason, "timestamp": self.timestamp}


@dataclass
class AgentAssignment:
    """A worker's assignment for one contract, with append-only history."""

    assignment_id: str
    contract: DelegationContract
    agent_id: str
    state: str = CoordinationState.CREATED
    history: List[AssignmentTransition] = field(default_factory=list)
    result: Optional["WorkerResult"] = None
    created_at: float = 0.0

    def transition(self, new_state: str, *, reason: str = "", timestamp: float = 0.0) -> None:
        self.history.append(AssignmentTransition(self.state, new_state, reason, timestamp))
        self.state = new_state

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "agent_id": self.agent_id,
            "state": self.state,
            "contract": self.contract.to_dict(),
            "history": [t.to_dict() for t in self.history],
            "result": self.result.to_dict() if self.result else None,
        }


# ---------------------------------------------------------------------------
# Goal ownership (exactly one owner, explicit transfers)
# ---------------------------------------------------------------------------
@dataclass
class OwnershipTransfer:
    goal_id: str
    from_owner: str
    to_owner: str
    reason: str = ""
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {"goal_id": self.goal_id, "from_owner": self.from_owner,
                "to_owner": self.to_owner, "reason": self.reason, "timestamp": self.timestamp}


class GoalOwnershipLedger:
    """Tracks the single owner of each goal via append-only transfers."""

    def __init__(self, default_owner: str = COORDINATOR_ID) -> None:
        self._default = default_owner
        self._owner: Dict[str, str] = {}
        self.transfers: List[OwnershipTransfer] = []

    def owner_of(self, goal_id: str) -> str:
        return self._owner.get(goal_id, self._default)

    def transfer(self, goal_id: str, to_owner: str, *, reason: str = "", timestamp: float = 0.0) -> OwnershipTransfer:
        frm = self.owner_of(goal_id)
        t = OwnershipTransfer(goal_id, frm, to_owner, reason, timestamp)
        self.transfers.append(t)
        self._owner[goal_id] = to_owner
        return t

    def is_owned_by_worker(self, goal_id: str) -> bool:
        owner = self.owner_of(goal_id)
        return owner != self._default

    def to_list(self) -> List[Dict[str, Any]]:
        return [t.to_dict() for t in self.transfers]


# ---------------------------------------------------------------------------
# Authority model (deterministic checks)
# ---------------------------------------------------------------------------
@dataclass
class AuthorityDecision:
    ok: bool
    reason: Optional[str] = None
    detail: str = ""


class AuthorityModel:
    """Deterministic capability / authority / budget / ownership checks.

    A delegation is authorized only if every check passes, evaluated in a
    fixed order so rejections are deterministic.
    """

    def check_goal_support(self, profile: AgentProfile, goal: CoordinationGoal) -> AuthorityDecision:
        if goal.goal_type and profile.supported_goals and goal.goal_type not in profile.supported_goals:
            return AuthorityDecision(False, RejectionReason.GOAL_UNSUPPORTED,
                                     f"{profile.agent_id} does not support goal type '{goal.goal_type}'")
        return AuthorityDecision(True)

    def check_capability(self, profile: AgentProfile, goal: CoordinationGoal) -> AuthorityDecision:
        missing = goal.required_capabilities - profile.capabilities
        if missing:
            return AuthorityDecision(False, RejectionReason.CAPABILITY_MISMATCH,
                                     f"missing capabilities: {sorted(missing)}")
        return AuthorityDecision(True)

    def check_authority(self, profile: AgentProfile, goal: CoordinationGoal) -> AuthorityDecision:
        missing = goal.authority_scope - profile.permissions
        if missing:
            return AuthorityDecision(False, RejectionReason.AUTHORITY_DENIED,
                                     f"missing permissions: {sorted(missing)}")
        return AuthorityDecision(True)

    def check_budget(self, budget: Optional[RunBudget]) -> AuthorityDecision:
        if budget is None:
            return AuthorityDecision(True)
        if budget.is_exhausted() or not budget.can_afford(handoffs=1).ok:
            return AuthorityDecision(False, RejectionReason.BUDGET_EXHAUSTED, "run budget exhausted")
        return AuthorityDecision(True)

    def check_ownership(self, ledger: GoalOwnershipLedger, goal: CoordinationGoal) -> AuthorityDecision:
        if ledger.is_owned_by_worker(goal.goal_id):
            return AuthorityDecision(False, RejectionReason.OWNERSHIP_CONFLICT,
                                     f"goal '{goal.goal_id}' already owned by {ledger.owner_of(goal.goal_id)}")
        return AuthorityDecision(True)

    def authorize(
        self,
        profile: AgentProfile,
        goal: CoordinationGoal,
        budget: Optional[RunBudget],
        ledger: GoalOwnershipLedger,
    ) -> AuthorityDecision:
        for check in (
            self.check_goal_support(profile, goal),
            self.check_capability(profile, goal),
            self.check_authority(profile, goal),
            self.check_ownership(ledger, goal),
            self.check_budget(budget),
        ):
            if not check.ok:
                return check
        return AuthorityDecision(True)


# ---------------------------------------------------------------------------
# Worker execution
# ---------------------------------------------------------------------------
@dataclass
class WorkerResult:
    """The outcome a worker returns to the coordinator."""

    success: bool
    outputs: Dict[str, Any] = field(default_factory=dict)
    detail: str = ""
    timed_out: bool = False
    duration: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "outputs": dict(self.outputs),
            "detail": self.detail,
            "timed_out": self.timed_out,
            "duration": self.duration,
        }


class WorkerUnavailable(Exception):
    """Raised by an executor when the agent cannot take the work."""


class WorkerExecutor(Protocol):
    """Executes a delegated contract under the shared memory + budget."""

    def execute(
        self,
        contract: DelegationContract,
        memory: WorkingMemory,
        budget: Optional[RunBudget],
    ) -> WorkerResult:
        ...


class ScriptedWorker:
    """A deterministic worker driven by a fixed result (for tests/demos).

    ``results`` may be a single :class:`WorkerResult`, a list consumed in
    order, or a callable ``(contract, memory) -> WorkerResult``.
    """

    def __init__(self, results: Any) -> None:
        self._results = results
        self._i = 0

    def execute(self, contract, memory, budget) -> WorkerResult:
        if callable(self._results):
            return self._results(contract, memory)
        if isinstance(self._results, list):
            r = self._results[min(self._i, len(self._results) - 1)]
            self._i += 1
            return r
        return self._results


class AgentWorker:
    """Wraps a governed agent so it can execute a delegated contract.

    Runs the contract's goal through ``agent.run_with_trace`` (under the
    shared budget, attached by the coordinator) and reports success from the
    trace.  Declared ``expected_outputs`` are filled from the response so the
    coordinator can commit them to shared memory.
    """

    def __init__(self, agent: Any) -> None:
        self.agent = agent

    def execute(self, contract, memory, budget) -> WorkerResult:
        from agentic.agentic_framework.streaming_events import RUN_COMPLETED
        try:
            trace = self.agent.run_with_trace(contract.goal_description)
        except BudgetExhausted:
            raise
        response = ""
        for evt in trace.get_events(RUN_COMPLETED):
            if isinstance(evt.payload, dict) and isinstance(evt.payload.get("result"), dict):
                response = evt.payload["result"].get("response", "")
        success = not trace.error_occurred and not trace.safety_blocked
        outputs = {key: response for key in contract.expected_outputs}
        return WorkerResult(success=success, outputs=outputs,
                            detail="ok" if success else "agent run failed")


# ---------------------------------------------------------------------------
# Coordination trace
# ---------------------------------------------------------------------------
@dataclass
class CoordinationTraceEntry:
    seq: int
    goal_id: str
    decision: str            # SELECTED | REJECTED | COMPLETED | FAILED | RECOVERED
    agent_id: Optional[str]
    reason: str
    contract: Optional[Dict[str, Any]] = None
    worker_result: Optional[Dict[str, Any]] = None
    memory_writes: List[str] = field(default_factory=list)
    ownership_from: Optional[str] = None
    ownership_to: Optional[str] = None
    state: Optional[str] = None
    rejections: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "seq": self.seq,
            "goal_id": self.goal_id,
            "decision": self.decision,
            "agent_id": self.agent_id,
            "reason": self.reason,
            "contract": self.contract,
            "worker_result": self.worker_result,
            "memory_writes": list(self.memory_writes),
            "ownership_from": self.ownership_from,
            "ownership_to": self.ownership_to,
            "state": self.state,
            "rejections": list(self.rejections),
        }


class CoordinationTrace:
    """Append-only log of every coordination decision."""

    def __init__(self) -> None:
        self.entries: List[CoordinationTraceEntry] = []
        self._seq = 0

    def record(self, **kw: Any) -> CoordinationTraceEntry:
        entry = CoordinationTraceEntry(seq=self._seq, **kw)
        self.entries.append(entry)
        self._seq += 1
        return entry

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
@dataclass
class CoordinationResult:
    mission_id: str
    status: str
    assignments: List[AgentAssignment] = field(default_factory=list)
    completed_goals: List[str] = field(default_factory=list)
    failed_goals: List[str] = field(default_factory=list)
    ownership: Optional[GoalOwnershipLedger] = None
    trace: Optional[CoordinationTrace] = None
    run_budget: Optional[RunBudget] = None

    def assignment_for(self, goal_id: str) -> Optional[AgentAssignment]:
        for a in self.assignments:
            if a.contract.goal_id == goal_id:
                return a
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "status": self.status,
            "completed_goals": list(self.completed_goals),
            "failed_goals": list(self.failed_goals),
            "assignments": [a.to_dict() for a in self.assignments],
            "ownership": self.ownership.to_list() if self.ownership else [],
            "trace": self.trace.to_list() if self.trace else [],
            "run_budget": self.run_budget.snapshot() if self.run_budget else None,
        }


# ---------------------------------------------------------------------------
# Coordinator (deterministic; never executes worker tasks directly)
# ---------------------------------------------------------------------------
class Coordinator:
    """Assigns mission goals to worker agents under explicit governance.

    The coordinator NEVER executes a worker task itself — it selects an agent
    (capability + authority + budget + ownership), issues an immutable
    :class:`DelegationContract`, invokes the worker's executor, collects the
    result, commits declared outputs to the shared :class:`WorkingMemory`,
    advances goal ownership, and moves to the next goal.  All agents share one
    :class:`RunBudget`; delegation never creates a new budget.

    Args:
        registry: The :class:`CapabilityRegistry` of workers.
        memory: The shared H14 ``WorkingMemory`` (one instance, no copies).
        run_budget: The shared H11 ``RunBudget`` (attached to every worker).
        authority: The :class:`AuthorityModel` (deterministic checks).
        max_delegations: Hard cap on total delegations (terminal).
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        memory: WorkingMemory,
        *,
        run_budget: Optional[RunBudget] = None,
        authority: Optional[AuthorityModel] = None,
        max_delegations: int = 64,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.run_budget = run_budget
        self.authority = authority or AuthorityModel()
        self.max_delegations = max_delegations

    def run(self, mission: Mission) -> CoordinationResult:
        ownership = GoalOwnershipLedger(COORDINATOR_ID)
        trace = CoordinationTrace()
        result = CoordinationResult(
            mission_id=mission.mission_id, status=MissionStatus.MISSION_COMPLETED,
            ownership=ownership, trace=trace, run_budget=self.run_budget,
        )

        if self.run_budget is not None:
            for aid in self.registry.agent_ids():
                ex = self.registry.executor(aid)
                if isinstance(ex, AgentWorker):
                    attach_run_budget(ex.agent, self.run_budget)
            self.run_budget.start()

        completed: set = set()
        seq = 0
        delegations = 0

        for goal in mission.goals:
            # Dependency gate: unmet dependency → mission fails deterministically.
            if any(dep not in completed for dep in goal.depends_on):
                trace.record(goal_id=goal.goal_id, decision="FAILED", agent_id=None,
                             reason="unmet dependency", state=CoordinationState.FAILED)
                result.failed_goals.append(goal.goal_id)
                if goal.mandatory:
                    result.status = MissionStatus.MISSION_FAILED
                    break
                continue

            if delegations >= self.max_delegations:
                result.status = MissionStatus.MISSION_FAILED
                break

            # Budget gate before any work.
            if self.run_budget is not None and self.run_budget.is_exhausted():
                result.status = MissionStatus.BUDGET_EXHAUSTED
                break

            outcome = self._coordinate_goal(goal, ownership, trace, seq)
            seq = outcome["seq"]
            delegations += outcome["delegations"]
            if outcome["assignment"] is not None:
                result.assignments.append(outcome["assignment"])

            if outcome["status"] == "completed":
                completed.add(goal.goal_id)
                result.completed_goals.append(goal.goal_id)
            elif outcome["status"] == "budget_exhausted":
                result.status = MissionStatus.BUDGET_EXHAUSTED
                break
            else:  # failed
                result.failed_goals.append(goal.goal_id)
                if goal.mandatory:
                    result.status = MissionStatus.MISSION_FAILED
                    break

        if self.run_budget is not None and not self.run_budget.is_exhausted():
            self.run_budget.complete()
        return result

    # ----- per-goal coordination -----
    def _coordinate_goal(self, goal, ownership, trace, seq) -> Dict[str, Any]:
        """Select a qualified agent and delegate; recover across candidates."""
        candidates = self.registry.candidates_for(goal)
        rejections: List[Dict[str, str]] = []
        delegations = 0
        last_assignment: Optional[AgentAssignment] = None

        if not candidates:
            trace.record(goal_id=goal.goal_id, decision="REJECTED", agent_id=None,
                         reason=RejectionReason.NO_QUALIFIED_AGENT, state=CoordinationState.FAILED,
                         rejections=rejections)
            return {"status": "failed", "seq": seq + 1, "delegations": 0, "assignment": None}

        for profile in candidates:
            decision = self.authority.authorize(profile, goal, self.run_budget, ownership)
            if not decision.ok:
                rejections.append({"agent_id": profile.agent_id, "reason": decision.reason,
                                   "detail": decision.detail})
                if decision.reason == RejectionReason.BUDGET_EXHAUSTED:
                    trace.record(goal_id=goal.goal_id, decision="REJECTED", agent_id=profile.agent_id,
                                 reason=RejectionReason.BUDGET_EXHAUSTED, state=CoordinationState.FAILED,
                                 rejections=rejections)
                    return {"status": "budget_exhausted", "seq": seq + 1, "delegations": delegations,
                            "assignment": None}
                continue

            # Reserve the delegation from the shared budget (handoff dimension).
            if self.run_budget is not None:
                res = self.run_budget.reserve(handoffs=1)
                if not res.ok:
                    trace.record(goal_id=goal.goal_id, decision="REJECTED", agent_id=profile.agent_id,
                                 reason=RejectionReason.BUDGET_EXHAUSTED, state=CoordinationState.FAILED,
                                 rejections=rejections)
                    return {"status": "budget_exhausted", "seq": seq + 1, "delegations": delegations,
                            "assignment": None}

            contract = DelegationContract(
                contract_id=f"{goal.goal_id}->{profile.agent_id}",
                goal_id=goal.goal_id,
                goal_description=goal.description,
                assigned_agent=profile.agent_id,
                required_inputs=tuple(goal.required_memory),
                expected_outputs=tuple(goal.expected_outputs) or tuple(goal.produces_memory),
                required_memory=tuple(goal.required_memory),
                assumptions=(),
                authority_scope=goal.authority_scope,
                timeout=goal.timeout,
                completion_criteria=goal.completion_criteria,
            )
            assignment = AgentAssignment(
                assignment_id=f"a{seq}", contract=contract, agent_id=profile.agent_id,
                created_at=float(seq),
            )
            last_assignment = assignment
            assignment.transition(CoordinationState.ASSIGNED, reason="delegated", timestamp=float(seq))
            ownership.transfer(goal.goal_id, profile.agent_id, reason="delegation", timestamp=float(seq))
            assignment.transition(CoordinationState.ACCEPTED, timestamp=float(seq))
            assignment.transition(CoordinationState.EXECUTING, timestamp=float(seq))
            delegations += 1

            executor = self.registry.executor(profile.agent_id)
            try:
                worker_result = executor.execute(contract, self.memory, self.run_budget)
            except BudgetExhausted:
                assignment.transition(CoordinationState.FAILED, reason=RejectionReason.BUDGET_EXHAUSTED,
                                      timestamp=float(seq))
                # Ownership returns to the coordinator; memory untouched.
                ownership.transfer(goal.goal_id, COORDINATOR_ID, reason="budget exhausted", timestamp=float(seq))
                assignment.result = WorkerResult(success=False, detail="budget exhausted")
                trace.record(goal_id=goal.goal_id, decision="FAILED", agent_id=profile.agent_id,
                             reason=RejectionReason.BUDGET_EXHAUSTED, contract=contract.to_dict(),
                             worker_result=assignment.result.to_dict(), ownership_from=profile.agent_id,
                             ownership_to=COORDINATOR_ID, state=CoordinationState.FAILED, rejections=rejections)
                return {"status": "budget_exhausted", "seq": seq + 1, "delegations": delegations,
                        "assignment": assignment}
            except WorkerUnavailable as exc:
                self.registry.mark_unavailable(profile.agent_id)
                assignment.transition(CoordinationState.FAILED, reason=RejectionReason.AGENT_UNAVAILABLE,
                                      timestamp=float(seq))
                ownership.transfer(goal.goal_id, COORDINATOR_ID, reason="agent unavailable", timestamp=float(seq))
                rejections.append({"agent_id": profile.agent_id, "reason": RejectionReason.AGENT_UNAVAILABLE,
                                   "detail": str(exc)})
                trace.record(goal_id=goal.goal_id, decision="RECOVERED", agent_id=profile.agent_id,
                             reason=RejectionReason.AGENT_UNAVAILABLE, state=CoordinationState.FAILED,
                             rejections=rejections)
                continue  # recover: try next qualified agent

            assignment.result = worker_result

            # Timeout (deterministic) — worker signalled or exceeded contract timeout.
            timed_out = worker_result.timed_out or (
                contract.timeout is not None and worker_result.duration is not None
                and worker_result.duration > contract.timeout
            )
            if timed_out:
                assignment.transition(CoordinationState.FAILED, reason=RejectionReason.DELEGATION_TIMEOUT,
                                      timestamp=float(seq))
                ownership.transfer(goal.goal_id, COORDINATOR_ID, reason="timeout", timestamp=float(seq))
                rejections.append({"agent_id": profile.agent_id, "reason": RejectionReason.DELEGATION_TIMEOUT,
                                   "detail": worker_result.detail})
                trace.record(goal_id=goal.goal_id, decision="RECOVERED", agent_id=profile.agent_id,
                             reason=RejectionReason.DELEGATION_TIMEOUT, contract=contract.to_dict(),
                             worker_result=worker_result.to_dict(), ownership_from=profile.agent_id,
                             ownership_to=COORDINATOR_ID, state=CoordinationState.FAILED, rejections=rejections)
                continue  # recover: try next qualified agent

            if not worker_result.success:
                assignment.transition(CoordinationState.FAILED, reason=RejectionReason.WORKER_FAILURE,
                                      timestamp=float(seq))
                # Failure returns ownership; shared memory is NOT written.
                ownership.transfer(goal.goal_id, COORDINATOR_ID, reason="worker failure", timestamp=float(seq))
                rejections.append({"agent_id": profile.agent_id, "reason": RejectionReason.WORKER_FAILURE,
                                   "detail": worker_result.detail})
                trace.record(goal_id=goal.goal_id, decision="RECOVERED", agent_id=profile.agent_id,
                             reason=RejectionReason.WORKER_FAILURE, contract=contract.to_dict(),
                             worker_result=worker_result.to_dict(), ownership_from=profile.agent_id,
                             ownership_to=COORDINATOR_ID, state=CoordinationState.FAILED, rejections=rejections)
                continue  # recover: try next qualified agent

            # Success: commit declared outputs to shared memory (coordinator writes).
            writes: List[str] = []
            for key in (contract.expected_outputs or ()):
                if key in worker_result.outputs:
                    self.memory.write(key, worker_result.outputs[key], category="delegation",
                                      provenance=profile.agent_id, producing_step=profile.agent_id,
                                      timestamp=float(seq))
                    writes.append(key)
            assignment.transition(CoordinationState.COMPLETED, reason="success", timestamp=float(seq))
            ownership.transfer(goal.goal_id, COORDINATOR_ID, reason="completed", timestamp=float(seq))
            trace.record(goal_id=goal.goal_id, decision="COMPLETED", agent_id=profile.agent_id,
                         reason="success", contract=contract.to_dict(),
                         worker_result=worker_result.to_dict(), memory_writes=writes,
                         ownership_from=profile.agent_id, ownership_to=COORDINATOR_ID,
                         state=CoordinationState.COMPLETED, rejections=rejections)
            return {"status": "completed", "seq": seq + 1, "delegations": delegations,
                    "assignment": assignment}

        # No candidate succeeded.
        trace.record(goal_id=goal.goal_id, decision="FAILED", agent_id=None,
                     reason=RejectionReason.NO_QUALIFIED_AGENT, state=CoordinationState.FAILED,
                     rejections=rejections)
        return {"status": "failed", "seq": seq + 1, "delegations": delegations, "assignment": last_assignment}


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_coordination_trace(result: CoordinationResult) -> str:
    lines = [
        f"Coordination: {result.mission_id}",
        f"status={result.status}  completed={result.completed_goals}  failed={result.failed_goals}",
        "=" * 60,
    ]
    if result.trace is None:
        return "\n".join(lines)
    for e in result.trace.entries:
        lines.append(f"  {e.seq}: goal={e.goal_id} decision={e.decision} agent={e.agent_id} ({e.reason})")
        if e.rejections:
            for rej in e.rejections:
                lines.append(f"       rejected {rej['agent_id']}: {rej['reason']}")
        if e.memory_writes:
            lines.append(f"       memory ← {e.memory_writes}")
        if e.ownership_from or e.ownership_to:
            lines.append(f"       ownership {e.ownership_from} → {e.ownership_to}")
    return "\n".join(lines)
