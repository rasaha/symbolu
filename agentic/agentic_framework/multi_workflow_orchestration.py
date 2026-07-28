"""
Multi-Workflow Orchestration (H22)
==================================

Deterministic, bounded orchestration of *multiple* concurrent workflows under
one portfolio.

```
Portfolio Scheduler
        ↓
┌──────────────────────────────┐
│ Workflow A  (H21 waves)      │
│ Workflow B  (H21 waves)      │
│ Workflow C  (H21 waves)      │
└──────────────────────────────┘
```

**H21 governs parallelism *within* a workflow. H22 governs scheduling,
dependencies, budgets, and resource contention *across* workflows.** H20
governed external actions remain deferred and are outside H22.

H22 decides which workflow may advance, how much portfolio budget it may
consume, whether inter-workflow dependencies permit progress, whether shared
logical resources are available, whether a higher-priority workflow should run
first, and whether cancellation / suspension should propagate. It never decides
goal-level execution details — those stay owned by H15–H21. It advances each
workflow one *quantum* (one committed H21 wave) at a time through the H21
public execution interface.

Architectural boundary: H22 composes only on the public APIs of H11 RunBudget,
H14 WorkingMemory, H15 planning, H16 authority/ownership, H17 workflows, H18
durability, H19 human governance, and H21 deterministic parallel execution. It
modifies none of them. It implements no H20 external actions, no distributed
queues, no cluster scheduling, no production database locking, no cross-machine
execution, and performs no repository-wide restructuring.

Determinism: given identical portfolio state, configuration, workflow results,
and human decisions, the same workflow-selection order and committed portfolio
history are produced — proven by the tests and by checkpoint replay.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Protocol, Set, Tuple

from agentic.agentic_framework.run_budget import RunBudget, RunBudgetLimits
from agentic.agentic_framework.working_memory import WorkingMemory
from agentic.agentic_framework.hierarchical_planning import (
    GoalStatus,
    GoalTree,
    MissionPlan,
)
from agentic.agentic_framework.coordination import CapabilityRegistry, AuthorityModel
from agentic.agentic_framework.workflow_durability import (
    canonical_json,
    digest_of,
    CheckpointConflict,
    RecoveryError,
)
from agentic.agentic_framework.parallel_execution import (
    ConcurrencyPolicy,
    BudgetEstimate,
    BudgetLedgerEntry,
    GoalExecutionFootprint,
    ParallelHierarchyExecutor,
    ParallelHierarchyStatus,
    WaveStatus,
    SynchronousBackend,
    ReviewGate,
)

__all__ = [
    # vocabulary
    "PortfolioStatus",
    "PortfolioWorkflowStatus",
    "WorkflowPriority",
    "priority_rank",
    "BudgetAllocationPolicy",
    "DependencyType",
    "DependencyFailurePolicy",
    "ResourceAccessMode",
    "DeadlockPolicy",
    "PortfolioFailurePolicy",
    "CancellationScope",
    "PauseState",
    "InFlightWorkflowStatus",
    "PortfolioEvent",
    # policies
    "PortfolioConcurrencyPolicy",
    "SchedulingPolicy",
    # dependency / resource / output models
    "WorkflowDependency",
    "DependencyGraph",
    "WorkflowResourceClaim",
    "ResourceLedger",
    "WorkflowOutputRef",
    # budget
    "PortfolioBudgetCoordinator",
    # workflow controller seam
    "QuantumResult",
    "WorkflowController",
    "H21WorkflowController",
    # registration + aggregate
    "PortfolioWorkflowEntry",
    "WorkflowPortfolio",
    # trace
    "PortfolioTraceEntry",
    "PortfolioTrace",
    # durability
    "PortfolioCheckpoint",
    "InMemoryPortfolioStore",
    # scheduler + result
    "PortfolioScheduler",
    "PortfolioResult",
    # rendering
    "format_portfolio",
    "format_portfolio_trace",
]


# ===========================================================================
# Vocabulary (string-constant namespaces — matches the H15/H16/H21 idiom)
# ===========================================================================
class PortfolioStatus:
    CREATED = "CREATED"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class PortfolioWorkflowStatus:
    """H22-owned orchestration status — a derived portfolio-level view.

    Does NOT replace an H17 ``WorkflowStatus``; the source workflow remains
    authoritative for its own internal lifecycle.
    """

    REGISTERED = "REGISTERED"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_FOR_DEPENDENCY = "WAITING_FOR_DEPENDENCY"
    WAITING_FOR_BUDGET = "WAITING_FOR_BUDGET"
    WAITING_FOR_RESOURCE = "WAITING_FOR_RESOURCE"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


_TERMINAL_WF = {
    PortfolioWorkflowStatus.COMPLETED,
    PortfolioWorkflowStatus.FAILED,
    PortfolioWorkflowStatus.CANCELLED,
}


class WorkflowPriority:
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    NORMAL = "NORMAL"
    LOW = "LOW"
    BACKGROUND = "BACKGROUND"


# Lower rank = more preferred.  Levels are spaced by 100 so bounded aging
# (capped well below 100) can never let a lower class overtake a higher one.
_PRIORITY_RANK = {
    WorkflowPriority.CRITICAL: 0,
    WorkflowPriority.HIGH: 100,
    WorkflowPriority.NORMAL: 200,
    WorkflowPriority.LOW: 300,
    WorkflowPriority.BACKGROUND: 400,
}


def priority_rank(priority: str) -> int:
    return _PRIORITY_RANK.get(priority, _PRIORITY_RANK[WorkflowPriority.NORMAL])


class BudgetAllocationPolicy:
    FIXED_ALLOCATION = "FIXED_ALLOCATION"
    WEIGHTED_SHARE = "WEIGHTED_SHARE"
    PRIORITY_WEIGHTED = "PRIORITY_WEIGHTED"
    ON_DEMAND_BOUNDED = "ON_DEMAND_BOUNDED"


class DependencyType:
    REQUIRES_COMPLETION = "REQUIRES_COMPLETION"
    REQUIRES_SUCCESS = "REQUIRES_SUCCESS"
    REQUIRES_MILESTONE = "REQUIRES_MILESTONE"
    REQUIRES_REVIEW_DECISION = "REQUIRES_REVIEW_DECISION"
    REQUIRES_OUTPUT = "REQUIRES_OUTPUT"


class DependencyFailurePolicy:
    BLOCK_DEPENDENT = "BLOCK_DEPENDENT"
    CANCEL_DEPENDENT = "CANCEL_DEPENDENT"
    ALLOW_DEGRADED = "ALLOW_DEGRADED"
    REQUIRE_HUMAN_DECISION = "REQUIRE_HUMAN_DECISION"


class ResourceAccessMode:
    READ = "READ"
    WRITE = "WRITE"
    EXCLUSIVE = "EXCLUSIVE"
    UNKNOWN = "UNKNOWN"


class DeadlockPolicy:
    CANCEL_LOWEST_PRIORITY = "CANCEL_LOWEST_PRIORITY"
    PAUSE_YOUNGEST = "PAUSE_YOUNGEST"
    REQUIRE_HUMAN_DECISION = "REQUIRE_HUMAN_DECISION"
    FAIL_PORTFOLIO = "FAIL_PORTFOLIO"


class PortfolioFailurePolicy:
    ISOLATE_WORKFLOW = "ISOLATE_WORKFLOW"
    FAIL_DEPENDENTS = "FAIL_DEPENDENTS"
    DEGRADED_CONTINUATION = "DEGRADED_CONTINUATION"
    FAIL_PORTFOLIO = "FAIL_PORTFOLIO"
    REQUIRE_HUMAN_REVIEW = "REQUIRE_HUMAN_REVIEW"


class CancellationScope:
    WORKFLOW_ONLY = "WORKFLOW_ONLY"
    DEPENDENT_SUBGRAPH = "DEPENDENT_SUBGRAPH"
    PORTFOLIO_ALL = "PORTFOLIO_ALL"


class PauseState:
    ACTIVE = "ACTIVE"
    PAUSE_REQUESTED = "PAUSE_REQUESTED"
    PAUSED = "PAUSED"
    RESUME_REQUESTED = "RESUME_REQUESTED"


class InFlightWorkflowStatus:
    NOT_GRANTED = "NOT_GRANTED"
    GRANTED_NOT_STARTED = "GRANTED_NOT_STARTED"
    RUNNING_NO_COMMIT = "RUNNING_NO_COMMIT"
    COMMITTED = "COMMITTED"
    WAITING = "WAITING"
    TERMINAL = "TERMINAL"


class PortfolioEvent:
    PORTFOLIO_CREATED = "PORTFOLIO_CREATED"
    WORKFLOW_REGISTERED = "WORKFLOW_REGISTERED"
    WORKFLOW_READY = "WORKFLOW_READY"
    WORKFLOW_SELECTED = "WORKFLOW_SELECTED"
    WORKFLOW_QUANTUM_GRANTED = "WORKFLOW_QUANTUM_GRANTED"
    WORKFLOW_QUANTUM_COMMITTED = "WORKFLOW_QUANTUM_COMMITTED"
    WORKFLOW_WAITING_FOR_DEPENDENCY = "WORKFLOW_WAITING_FOR_DEPENDENCY"
    WORKFLOW_WAITING_FOR_BUDGET = "WORKFLOW_WAITING_FOR_BUDGET"
    WORKFLOW_WAITING_FOR_RESOURCE = "WORKFLOW_WAITING_FOR_RESOURCE"
    WORKFLOW_WAITING_FOR_REVIEW = "WORKFLOW_WAITING_FOR_REVIEW"
    RESOURCE_CLAIM_ACQUIRED = "RESOURCE_CLAIM_ACQUIRED"
    RESOURCE_CLAIM_RELEASED = "RESOURCE_CLAIM_RELEASED"
    DEPENDENCY_SATISFIED = "DEPENDENCY_SATISFIED"
    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"
    PRIORITY_AGED = "PRIORITY_AGED"
    DEADLOCK_DETECTED = "DEADLOCK_DETECTED"
    WORKFLOW_PAUSED = "WORKFLOW_PAUSED"
    WORKFLOW_RESUMED = "WORKFLOW_RESUMED"
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    PORTFOLIO_CHECKPOINTED = "PORTFOLIO_CHECKPOINTED"
    PORTFOLIO_RESTORED = "PORTFOLIO_RESTORED"
    PORTFOLIO_COMPLETED = "PORTFOLIO_COMPLETED"
    PORTFOLIO_FAILED = "PORTFOLIO_FAILED"


# ===========================================================================
# Policies (immutable)
# ===========================================================================
@dataclass(frozen=True)
class PortfolioConcurrencyPolicy:
    """Bounded, conservative concurrency limits across workflows (§19)."""

    max_concurrent_workflows: int = 3
    max_active_waves: Optional[int] = None
    max_workflows_per_agent: Optional[int] = None
    max_workflows_per_authority_scope: Optional[int] = None
    max_workflows_per_resource_class: Optional[int] = None
    scheduling_quantum: str = "ONE_WAVE"
    preemption_policy: str = "SAFE_BOUNDARY"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_concurrent_workflows": self.max_concurrent_workflows,
            "max_active_waves": self.max_active_waves,
            "max_workflows_per_agent": self.max_workflows_per_agent,
            "max_workflows_per_authority_scope": self.max_workflows_per_authority_scope,
            "max_workflows_per_resource_class": self.max_workflows_per_resource_class,
            "scheduling_quantum": self.scheduling_quantum,
            "preemption_policy": self.preemption_policy,
        }


@dataclass(frozen=True)
class SchedulingPolicy:
    """Priority-aging + fairness configuration (§10, §21)."""

    aging_increment: int = 10
    aging_cap: int = 500           # non-critical ages toward (never reaching) rank 0
    fairness: str = "DEFICIT_ROUND_ROBIN"
    allocation_policy: str = BudgetAllocationPolicy.ON_DEMAND_BOUNDED
    dependency_failure_policy: str = DependencyFailurePolicy.BLOCK_DEPENDENT
    deadlock_policy: str = DeadlockPolicy.PAUSE_YOUNGEST
    portfolio_failure_policy: str = PortfolioFailurePolicy.ISOLATE_WORKFLOW
    max_rounds: int = 512

    def to_dict(self) -> Dict[str, Any]:
        return {
            "aging_increment": self.aging_increment,
            "aging_cap": self.aging_cap,
            "fairness": self.fairness,
            "allocation_policy": self.allocation_policy,
            "dependency_failure_policy": self.dependency_failure_policy,
            "deadlock_policy": self.deadlock_policy,
            "portfolio_failure_policy": self.portfolio_failure_policy,
            "max_rounds": self.max_rounds,
        }


# ===========================================================================
# Inter-workflow dependency model (§13, §14)
# ===========================================================================
@dataclass(frozen=True)
class WorkflowDependency:
    """A hard dependency of ``dependent`` on ``predecessor``."""

    dependent: str
    predecessor: str
    dep_type: str = DependencyType.REQUIRES_COMPLETION
    milestone: Optional[str] = None       # for REQUIRES_MILESTONE
    output_name: Optional[str] = None     # for REQUIRES_OUTPUT
    review_key: Optional[str] = None      # for REQUIRES_REVIEW_DECISION
    min_version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dependent": self.dependent,
            "predecessor": self.predecessor,
            "dep_type": self.dep_type,
            "milestone": self.milestone,
            "output_name": self.output_name,
            "review_key": self.review_key,
            "min_version": self.min_version,
        }


class DependencyGraph:
    """A validated directed dependency graph across workflows (cycles rejected)."""

    def __init__(self) -> None:
        self._deps: List[WorkflowDependency] = []
        self._by_dependent: Dict[str, List[WorkflowDependency]] = {}

    def add(self, dep: WorkflowDependency) -> None:
        self._deps.append(dep)
        self._by_dependent.setdefault(dep.dependent, []).append(dep)
        self.validate_acyclic()

    def dependencies_of(self, workflow_id: str) -> List[WorkflowDependency]:
        return list(self._by_dependent.get(workflow_id, []))

    def predecessors(self, workflow_id: str) -> Set[str]:
        return {d.predecessor for d in self._by_dependent.get(workflow_id, [])}

    def dependents_of(self, workflow_id: str) -> List[str]:
        return [d.dependent for d in self._deps if d.predecessor == workflow_id]

    def depth(self, workflow_id: str) -> int:
        """Longest predecessor chain length (deterministic; acyclic)."""
        seen: Dict[str, int] = {}

        def _d(wid: str, stack: FrozenSet[str]) -> int:
            if wid in seen:
                return seen[wid]
            preds = self.predecessors(wid)
            best = 0 if not preds else 1 + max(_d(p, stack | {wid}) for p in sorted(preds))
            seen[wid] = best
            return best

        return _d(workflow_id, frozenset())

    def validate_acyclic(self) -> None:
        WHITE, GREY, BLACK = 0, 1, 2
        nodes = {d.dependent for d in self._deps} | {d.predecessor for d in self._deps}
        color = {n: WHITE for n in nodes}

        def visit(n: str) -> None:
            color[n] = GREY
            for pred in sorted(self.predecessors(n)):
                if color.get(pred, WHITE) == GREY:
                    raise ValueError(f"workflow dependency cycle at '{n}' → '{pred}'")
                if color.get(pred, WHITE) == WHITE:
                    visit(pred)
            color[n] = BLACK

        for n in sorted(nodes):
            if color[n] == WHITE:
                visit(n)

    def to_list(self) -> List[Dict[str, Any]]:
        return [d.to_dict() for d in self._deps]


# ===========================================================================
# Cross-workflow output references (§24)
# ===========================================================================
@dataclass(frozen=True)
class WorkflowOutputRef:
    """A durable, immutable reference to an output a workflow committed."""

    producing_workflow: str
    output_name: str
    version: int
    digest: str
    type_id: str = ""
    available: bool = True
    milestone: Optional[str] = None
    provenance: str = ""

    @classmethod
    def of(cls, producing_workflow: str, output_name: str, value: Any, version: int,
           *, type_id: str = "", milestone: Optional[str] = None,
           provenance: str = "") -> "WorkflowOutputRef":
        digest = digest_of(canonical_json({"name": output_name, "version": version, "value": value}))
        return cls(producing_workflow, output_name, version, digest, type_id, True, milestone, provenance)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "producing_workflow": self.producing_workflow,
            "output_name": self.output_name,
            "version": self.version,
            "digest": self.digest,
            "type_id": self.type_id,
            "available": self.available,
            "milestone": self.milestone,
            "provenance": self.provenance,
        }


# ===========================================================================
# Shared logical resource claims + contention (§16, §17, §18)
# ===========================================================================
@dataclass(frozen=True)
class WorkflowResourceClaim:
    """A portfolio-level *logical* resource claim (not an H20 external mutation)."""

    resource_key: str
    workflow_id: str
    access_mode: str = ResourceAccessMode.UNKNOWN
    scope: str = "portfolio"
    exclusive: bool = False
    duration_class: str = "quantum"
    priority: int = 0
    preemption_policy: str = "NONE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_key": self.resource_key,
            "workflow_id": self.workflow_id,
            "access_mode": self.access_mode,
            "scope": self.scope,
            "exclusive": self.exclusive,
            "duration_class": self.duration_class,
            "priority": self.priority,
            "preemption_policy": self.preemption_policy,
        }


def _modes_conflict(a: str, b: str) -> bool:
    """Deterministic contention rules (§17).  UNKNOWN fails closed."""
    if ResourceAccessMode.UNKNOWN in (a, b):
        return True
    if ResourceAccessMode.EXCLUSIVE in (a, b):
        return True
    if a == ResourceAccessMode.READ and b == ResourceAccessMode.READ:
        return False
    # any WRITE vs READ/WRITE conflicts
    return True


class ResourceLedger:
    """Atomic, deterministic acquisition of logical resource claims.

    A workflow's claims are acquired all-or-none against a stable global
    resource ordering, so partial acquisition and last-arrival-wins never
    happen.  Holders and waiters feed a wait-for graph for deadlock detection.
    """

    def __init__(self) -> None:
        # resource_key -> {workflow_id: access_mode}
        self._held: Dict[str, Dict[str, str]] = {}
        self._lock = threading.Lock()

    def _claim_conflicts(self, claim: WorkflowResourceClaim) -> Set[str]:
        holders = self._held.get(claim.resource_key, {})
        blocking: Set[str] = set()
        for wid, mode in holders.items():
            if wid == claim.workflow_id:
                continue
            if _modes_conflict(claim.access_mode, mode):
                blocking.add(wid)
        return blocking

    def blockers_for(self, claims: List[WorkflowResourceClaim]) -> Set[str]:
        """Which *other* workflows currently block this claim set (read-only)."""
        with self._lock:
            out: Set[str] = set()
            for c in sorted(claims, key=lambda c: c.resource_key):
                out |= self._claim_conflicts(c)
            return out

    def try_acquire(self, workflow_id: str, claims: List[WorkflowResourceClaim]) -> bool:
        """Atomically acquire every claim, or none (deterministic order)."""
        with self._lock:
            ordered = sorted(claims, key=lambda c: c.resource_key)  # stable global order
            for c in ordered:
                if self._claim_conflicts(c):
                    return False
            for c in ordered:
                self._held.setdefault(c.resource_key, {})[workflow_id] = c.access_mode
            return True

    def release_all(self, workflow_id: str) -> List[str]:
        with self._lock:
            released: List[str] = []
            for key in sorted(self._held):
                if workflow_id in self._held[key]:
                    del self._held[key][workflow_id]
                    released.append(key)
            return released

    def holders(self, resource_key: str) -> Dict[str, str]:
        with self._lock:
            return dict(self._held.get(resource_key, {}))

    def snapshot(self) -> Dict[str, Dict[str, str]]:
        with self._lock:
            return {k: dict(v) for k, v in self._held.items() if v}


# ===========================================================================
# Shared portfolio budget (§11, §12)
# ===========================================================================
_EST_DIMS: Tuple[str, ...] = (
    "model_calls", "tool_calls", "iterations", "handoffs",
    "prompt_tokens", "completion_tokens", "cost",
)


class PortfolioBudgetCoordinator:
    """Lock-protected reservation over one shared portfolio :class:`RunBudget`.

    Sits above the per-workflow H11 budget and the H21 wave reservation:

        Portfolio budget → Workflow allocation → H21 wave reservation → goal.

    Mirrors the H21 ``SharedBudgetCoordinator`` design: an H22-owned reservation
    pool measured against live headroom (fully reversible), with H11's monotonic
    counters mutated only at reconcile with *actual* usage.  Also enforces a
    per-workflow maximum allocation and records allocation policy state.
    """

    def __init__(
        self,
        portfolio_budget: Optional[RunBudget],
        *,
        allocation_policy: str = BudgetAllocationPolicy.ON_DEMAND_BOUNDED,
        max_allocations: Optional[Dict[str, BudgetEstimate]] = None,
    ) -> None:
        self._budget = portfolio_budget
        self._lock = threading.Lock()
        self._reserved: Dict[str, float] = {d: 0.0 for d in _EST_DIMS}
        self.allocation_policy = allocation_policy
        self._max_alloc = max_allocations or {}
        self._allocated: Dict[str, Dict[str, float]] = {}

    @property
    def run_budget(self) -> Optional[RunBudget]:
        return self._budget

    def _headroom(self, dim: str) -> Optional[float]:
        if self._budget is None:
            return None
        return self._budget.remaining(dim)

    def _alloc(self, workflow_id: str) -> Dict[str, float]:
        return self._allocated.setdefault(workflow_id, {d: 0.0 for d in _EST_DIMS})

    def _within_max(self, workflow_id: str, est: BudgetEstimate) -> Tuple[bool, Optional[str]]:
        cap = self._max_alloc.get(workflow_id)
        if cap is None:
            return True, None
        alloc = self._alloc(workflow_id)
        for d in _EST_DIMS:
            limit = float(getattr(cap, d))
            if limit <= 0:
                continue
            if alloc[d] + float(getattr(est, d)) > limit:
                return False, d
        return True, None

    def reserve_quantum(self, workflow_id: str, est: BudgetEstimate) -> Tuple[bool, Optional[str], Optional[str]]:
        """Reserve one workflow quantum. Returns ``(ok, kind, dimension)`` where
        ``kind`` is ``None`` / ``"MAX_ALLOCATION"`` / ``"PORTFOLIO_BUDGET"``.
        Serialised so two workflows can never oversubscribe the portfolio."""
        with self._lock:
            within, dim = self._within_max(workflow_id, est)
            if not within:
                return False, "MAX_ALLOCATION", dim
            if self._budget is not None:
                if self._budget.is_exhausted():
                    return False, "PORTFOLIO_BUDGET", None
                for d in _EST_DIMS:
                    need = float(getattr(est, d))
                    if need <= 0:
                        continue
                    head = self._headroom(d)
                    if head is not None and need + self._reserved[d] > head:
                        return False, "PORTFOLIO_BUDGET", d
            for d in _EST_DIMS:
                self._reserved[d] += float(getattr(est, d))
            return True, None, None

    def reconcile(self, workflow_id: str, est: BudgetEstimate, actual: BudgetLedgerEntry) -> None:
        with self._lock:
            if self._budget is not None:
                self._budget.reserve(
                    model_calls=actual.model_calls,
                    iterations=actual.iterations,
                    handoffs=actual.handoffs,
                )
                self._budget.record_usage(
                    prompt_tokens=actual.prompt_tokens,
                    completion_tokens=actual.completion_tokens,
                    cost=actual.cost,
                    tool_calls=actual.tool_calls,
                )
            alloc = self._alloc(workflow_id)
            for d in _EST_DIMS:
                alloc[d] += float(getattr(actual, d))
                self._reserved[d] = max(0.0, self._reserved[d] - float(getattr(est, d)))

    def release(self, est: BudgetEstimate) -> None:
        with self._lock:
            for d in _EST_DIMS:
                self._reserved[d] = max(0.0, self._reserved[d] - float(getattr(est, d)))

    def allocated(self, workflow_id: str) -> Dict[str, float]:
        with self._lock:
            return dict(self._alloc(workflow_id))

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "allocation_policy": self.allocation_policy,
                "reserved": dict(self._reserved),
                "allocated": {w: dict(a) for w, a in self._allocated.items()},
                "budget": self._budget.snapshot() if self._budget is not None else None,
            }


# ===========================================================================
# Workflow controller seam (§7) — advances a workflow one quantum via H21
# ===========================================================================
@dataclass
class QuantumResult:
    """The outcome of advancing one workflow by a single quantum (H21 wave)."""

    workflow_id: str
    progressed: bool
    committed_goals: List[str]
    terminal: bool
    succeeded: bool
    waiting_review: bool
    budget_blocked: bool
    budget_delta: BudgetLedgerEntry
    committed_memory_keys: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "progressed": self.progressed,
            "committed_goals": list(self.committed_goals),
            "terminal": self.terminal,
            "succeeded": self.succeeded,
            "waiting_review": self.waiting_review,
            "budget_blocked": self.budget_blocked,
            "budget_delta": self.budget_delta.to_dict(),
            "committed_memory_keys": list(self.committed_memory_keys),
        }


class WorkflowController(Protocol):
    """Advances one workflow by a bounded quantum through its H21 interface."""

    workflow_id: str
    memory: WorkingMemory

    def advance_quantum(self) -> QuantumResult: ...
    def milestone_reached(self, memory_key: str) -> bool: ...
    def output_ref(self, memory_key: str, output_name: str) -> Optional[WorkflowOutputRef]: ...


class H21WorkflowController:
    """Reference controller wrapping an H21 :class:`ParallelHierarchyExecutor`.

    Each ``advance_quantum`` invokes the executor for exactly one committed H21
    wave (``max_waves=1``) and reports precise progress — never re-running
    committed work.  H21 remains authoritative for intra-workflow parallelism.
    """

    def __init__(
        self,
        workflow_id: str,
        plan: MissionPlan,
        memory: WorkingMemory,
        registry: CapabilityRegistry,
        *,
        run_budget: Optional[RunBudget] = None,
        authority: Optional[AuthorityModel] = None,
        assumption_context: Optional[Any] = None,
        footprints: Optional[Dict[str, GoalExecutionFootprint]] = None,
        estimates: Optional[Dict[str, BudgetEstimate]] = None,
        default_estimate: Optional[BudgetEstimate] = None,
        backend: Optional[Any] = None,
        review_gate: Optional[ReviewGate] = None,
        subtree_replanner: Optional[Callable[[GoalTree, str], List[Any]]] = None,
        concurrency_policy: Optional[ConcurrencyPolicy] = None,
        worker: Optional[Any] = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.plan = plan
        self.memory = memory
        self.run_budget = run_budget
        self.review_gate = review_gate
        self._executor = ParallelHierarchyExecutor(
            registry, memory, run_budget=run_budget, authority=authority,
            assumption_context=assumption_context, subtree_replanner=subtree_replanner,
            concurrency_policy=concurrency_policy or ConcurrencyPolicy(),
            footprints=footprints or {}, estimates=estimates or {},
            default_estimate=default_estimate, backend=backend or SynchronousBackend(),
            review_gate=review_gate, worker=worker, workflow_id=workflow_id, max_waves=1,
        )

    # ----- usage tracking for portfolio reconciliation -----
    def _usage(self) -> BudgetLedgerEntry:
        if self.run_budget is None:
            return BudgetLedgerEntry()
        return BudgetLedgerEntry.from_budget(self.run_budget)

    @staticmethod
    def _delta(before: BudgetLedgerEntry, after: BudgetLedgerEntry) -> BudgetLedgerEntry:
        return BudgetLedgerEntry(
            model_calls=after.model_calls - before.model_calls,
            tool_calls=after.tool_calls - before.tool_calls,
            iterations=after.iterations - before.iterations,
            handoffs=after.handoffs - before.handoffs,
            prompt_tokens=after.prompt_tokens - before.prompt_tokens,
            completion_tokens=after.completion_tokens - before.completion_tokens,
            cost=after.cost - before.cost,
        )

    def _probe(self) -> Tuple[bool, bool, bool]:
        """Return (terminal, succeeded, waiting_review) from tree readiness."""
        tree = self.plan.tree
        ready = self._executor.scheduler.ready_leaves(tree)
        runnable: List[Any] = []
        review_held = 0
        for node in ready:
            gid = node.goal.goal_id
            gate = self.review_gate
            if gate is not None and gate.requires_review(node.goal) \
                    and not gate.is_cleared(gid) and gate.rejection(gid) is None:
                review_held += 1
            else:
                runnable.append(node)
        if runnable:
            return False, False, False
        if review_held:
            return False, False, True
        mandatory_leaves = [n for n in tree.leaves()
                            if n.goal.mandatory and n.status != GoalStatus.ABORTED]
        succeeded = all(n.status == GoalStatus.COMPLETED for n in mandatory_leaves)
        return True, succeeded, False

    def advance_quantum(self) -> QuantumResult:
        before = self._usage()
        keys_before = set(self.memory.keys())
        result = self._executor.run(self.plan)
        delta = self._delta(before, self._usage())
        committed_keys = sorted(set(self.memory.keys()) - keys_before)

        if result.waves:
            wave = result.waves[-1]
            committed = list(wave.completed_goal_ids)
            budget_blocked = wave.status == WaveStatus.BLOCKED
            terminal, succeeded, waiting_review = self._probe()
            progressed = bool(committed)
            if budget_blocked:  # nothing dispatched this quantum
                terminal = False
        else:
            committed = []
            progressed = False
            budget_blocked = result.status == ParallelHierarchyStatus.BUDGET_EXHAUSTED
            if budget_blocked:
                terminal, succeeded, waiting_review = False, False, False
            else:
                terminal, succeeded, waiting_review = self._probe()
        return QuantumResult(
            workflow_id=self.workflow_id, progressed=progressed, committed_goals=committed,
            terminal=terminal, succeeded=succeeded, waiting_review=waiting_review,
            budget_blocked=budget_blocked, budget_delta=delta, committed_memory_keys=committed_keys,
        )

    def milestone_reached(self, memory_key: str) -> bool:
        return self.memory.peek(memory_key) is not None

    def output_ref(self, memory_key: str, output_name: str) -> Optional[WorkflowOutputRef]:
        rec = self.memory.peek(memory_key)
        if rec is None:
            return None
        return WorkflowOutputRef.of(
            self.workflow_id, output_name, rec.value, rec.version,
            provenance=f"{self.workflow_id}/{memory_key}",
        )


# ===========================================================================
# Workflow registration entry (§5) — append-only, mutable orchestration state
# ===========================================================================
@dataclass
class PortfolioWorkflowEntry:
    workflow_id: str
    controller: WorkflowController
    priority: str = WorkflowPriority.NORMAL
    weight: int = 1
    registration_sequence: int = 0
    status: str = PortfolioWorkflowStatus.REGISTERED
    budget_estimate: BudgetEstimate = field(default_factory=BudgetEstimate)
    max_allocation: Optional[BudgetEstimate] = None
    resource_claims: Tuple[WorkflowResourceClaim, ...] = ()
    authority_scope: FrozenSet[str] = frozenset()
    assigned_agent: Optional[str] = None
    resource_class: Optional[str] = None
    cancellation_policy: str = CancellationScope.WORKFLOW_ONLY
    #: memory_key -> output_name  (durable cross-workflow outputs)
    output_keys: Dict[str, str] = field(default_factory=dict)
    #: milestone_name -> memory_key
    milestone_keys: Dict[str, str] = field(default_factory=dict)
    #: review_key -> bool (durable human decisions this workflow records)
    review_decisions: Dict[str, bool] = field(default_factory=dict)
    degraded: bool = False
    # runtime orchestration bookkeeping
    age: int = 0
    deficit: float = 0.0
    pause_state: str = PauseState.ACTIVE
    cancel_reason: Optional[str] = None
    last_selected_round: int = -1
    succeeded: bool = False
    history: List[Tuple[str, str]] = field(default_factory=list)

    def set_status(self, new_status: str) -> None:
        if new_status != self.status:
            self.history.append((self.status, new_status))
            self.status = new_status

    def is_terminal(self) -> bool:
        return self.status in _TERMINAL_WF

    def effective_rank(self, aging_cap: int) -> int:
        """Lower = more preferred.  CRITICAL is absolute (never ages); every
        other class ages toward — but never reaching — rank 0, so a starving
        workflow can climb above its peers while CRITICAL stays distinguishable
        (§10)."""
        base = priority_rank(self.priority)
        if self.priority == WorkflowPriority.CRITICAL:
            return base
        return max(1, base - min(self.age, aging_cap))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "priority": self.priority,
            "weight": self.weight,
            "registration_sequence": self.registration_sequence,
            "status": self.status,
            "budget_estimate": self.budget_estimate.to_dict(),
            "max_allocation": self.max_allocation.to_dict() if self.max_allocation else None,
            "resource_claims": [c.to_dict() for c in self.resource_claims],
            "authority_scope": sorted(self.authority_scope),
            "assigned_agent": self.assigned_agent,
            "resource_class": self.resource_class,
            "cancellation_policy": self.cancellation_policy,
            "output_keys": dict(self.output_keys),
            "milestone_keys": dict(self.milestone_keys),
            "review_decisions": dict(self.review_decisions),
            "degraded": self.degraded,
            "age": self.age,
            "deficit": self.deficit,
            "pause_state": self.pause_state,
            "cancel_reason": self.cancel_reason,
            "last_selected_round": self.last_selected_round,
            "succeeded": self.succeeded,
        }


# ===========================================================================
# Portfolio trace (§31) — portfolio logical sequence numbers
# ===========================================================================
@dataclass
class PortfolioTraceEntry:
    seq: int
    event: str
    workflow_id: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"seq": self.seq, "event": self.event,
                "workflow_id": self.workflow_id, "detail": self.detail}


class PortfolioTrace:
    def __init__(self) -> None:
        self.entries: List[PortfolioTraceEntry] = []
        self._seq = 0

    def record(self, event: str, *, workflow_id: Optional[str] = None, **detail: Any) -> PortfolioTraceEntry:
        entry = PortfolioTraceEntry(seq=self._seq, event=event, workflow_id=workflow_id, detail=dict(detail))
        self.entries.append(entry)
        self._seq += 1
        return entry

    @property
    def next_seq(self) -> int:
        return self._seq

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]


# ===========================================================================
# Portfolio aggregate (§4)
# ===========================================================================
class WorkflowPortfolio:
    """The orchestration aggregate: registered workflows + shared state.

    A portfolio is complete only when every non-cancelled workflow reaches an
    allowed terminal state.
    """

    def __init__(
        self,
        portfolio_id: str,
        *,
        scope: str = "default",
        portfolio_budget: Optional[RunBudget] = None,
        concurrency_policy: Optional[PortfolioConcurrencyPolicy] = None,
        scheduling_policy: Optional[SchedulingPolicy] = None,
        allocation_policy: str = BudgetAllocationPolicy.ON_DEMAND_BOUNDED,
    ) -> None:
        self.portfolio_id = portfolio_id
        self.scope = scope
        self.status = PortfolioStatus.CREATED
        self.concurrency_policy = concurrency_policy or PortfolioConcurrencyPolicy()
        self.scheduling_policy = scheduling_policy or SchedulingPolicy()
        self.entries: Dict[str, PortfolioWorkflowEntry] = {}
        self._order: List[str] = []
        self.dependencies = DependencyGraph()
        self.resources = ResourceLedger()
        self.budget = PortfolioBudgetCoordinator(portfolio_budget, allocation_policy=allocation_policy)
        self.outputs: Dict[Tuple[str, str], WorkflowOutputRef] = {}  # (wf, output) -> ref
        self.trace = PortfolioTrace()
        self.round = 0
        self.cancellation_state: Dict[str, str] = {}
        self.history: List[Tuple[str, str]] = []
        self.trace.record(PortfolioEvent.PORTFOLIO_CREATED, portfolio_id=portfolio_id)

    def set_status(self, new_status: str) -> None:
        if new_status != self.status:
            self.history.append((self.status, new_status))
            self.status = new_status

    # ----- registration (§5): deterministic, append-only, idempotent -----
    def register(self, entry: PortfolioWorkflowEntry) -> PortfolioWorkflowEntry:
        existing = self.entries.get(entry.workflow_id)
        if existing is not None:
            return existing  # idempotent
        entry.registration_sequence = len(self._order)
        self.entries[entry.workflow_id] = entry
        self._order.append(entry.workflow_id)
        # Max-allocation cap flows into the shared budget coordinator.
        if entry.max_allocation is not None:
            self.budget._max_alloc[entry.workflow_id] = entry.max_allocation  # noqa: SLF001
        self.trace.record(PortfolioEvent.WORKFLOW_REGISTERED, workflow_id=entry.workflow_id,
                          priority=entry.priority, sequence=entry.registration_sequence)
        return entry

    def add_dependency(self, dep: WorkflowDependency) -> None:
        self.dependencies.add(dep)

    def ordered_entries(self) -> List[PortfolioWorkflowEntry]:
        return [self.entries[w] for w in self._order]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "scope": self.scope,
            "status": self.status,
            "round": self.round,
            "concurrency_policy": self.concurrency_policy.to_dict(),
            "scheduling_policy": self.scheduling_policy.to_dict(),
            "workflows": [self.entries[w].to_dict() for w in self._order],
            "dependencies": self.dependencies.to_list(),
            "resources": self.resources.snapshot(),
            "budget": self.budget.snapshot(),
            "outputs": {f"{w}:{o}": ref.to_dict() for (w, o), ref in self.outputs.items()},
            "cancellation_state": dict(self.cancellation_state),
        }


# ===========================================================================
# Portfolio durability (§28) — composes H18 public helpers, fail-closed
# ===========================================================================
@dataclass
class PortfolioCheckpoint:
    checkpoint_id: str
    portfolio_id: str
    logical_sequence: int
    body: Dict[str, Any]
    workflow_checkpoint_refs: Dict[str, str]
    integrity_digest: str = ""

    def payload(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "portfolio_id": self.portfolio_id,
            "logical_sequence": self.logical_sequence,
            "body": self.body,
            "workflow_checkpoint_refs": self.workflow_checkpoint_refs,
        }

    def compute_digest(self) -> str:
        return digest_of(canonical_json(self.payload()))

    def with_digest(self) -> "PortfolioCheckpoint":
        self.integrity_digest = self.compute_digest()
        return self

    def to_dict(self) -> Dict[str, Any]:
        d = self.payload()
        d["integrity_digest"] = self.integrity_digest
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioCheckpoint":
        return cls(
            checkpoint_id=d["checkpoint_id"], portfolio_id=d["portfolio_id"],
            logical_sequence=d["logical_sequence"], body=d["body"],
            workflow_checkpoint_refs=dict(d["workflow_checkpoint_refs"]),
            integrity_digest=d.get("integrity_digest", ""),
        )

    def validate(self, *, workflow_digests: Optional[Dict[str, str]] = None) -> None:
        """Fail-closed integrity check (mirrors H18).  If portfolio and workflow
        checkpoints disagree, raise rather than guess (§29)."""
        if not self.integrity_digest:
            raise RecoveryError(RecoveryError.CHECKPOINT_CORRUPT, "missing portfolio digest")
        if self.integrity_digest != self.compute_digest():
            raise RecoveryError(RecoveryError.CHECKPOINT_CORRUPT, "portfolio digest mismatch")
        if self.logical_sequence < 0:
            raise RecoveryError(RecoveryError.CHECKPOINT_INVARIANT_VIOLATION, "negative logical sequence")
        if workflow_digests is not None:
            for wid, ref in self.workflow_checkpoint_refs.items():
                got = workflow_digests.get(wid)
                if got is not None and got != ref:
                    raise RecoveryError(
                        RecoveryError.CHECKPOINT_INVARIANT_VIOLATION,
                        f"portfolio/workflow checkpoint disagreement for {wid}",
                    )


class InMemoryPortfolioStore:
    """Append-only, optimistic-concurrency store for portfolio checkpoints."""

    def __init__(self) -> None:
        self._by_id: Dict[str, PortfolioCheckpoint] = {}
        self._latest: Dict[str, str] = {}

    def save(self, cp: PortfolioCheckpoint) -> None:
        cp = cp if cp.integrity_digest else cp.with_digest()
        cp.validate()
        self._by_id[cp.checkpoint_id] = cp
        self._latest[cp.portfolio_id] = cp.checkpoint_id

    def compare_and_save(self, cp: PortfolioCheckpoint, *, expected_latest_id: Optional[str]) -> None:
        current = self._latest.get(cp.portfolio_id)
        if current != expected_latest_id:
            raise CheckpointConflict(f"expected latest {expected_latest_id!r}, found {current!r}")
        self.save(cp)

    def load(self, checkpoint_id: str) -> PortfolioCheckpoint:
        cp = self._by_id[checkpoint_id]
        cp.validate()
        return cp

    def load_latest(self, portfolio_id: str) -> Optional[PortfolioCheckpoint]:
        cid = self._latest.get(portfolio_id)
        return self.load(cid) if cid else None

    def latest_id(self, portfolio_id: str) -> Optional[str]:
        return self._latest.get(portfolio_id)


# ===========================================================================
# Portfolio scheduler (§7, §8) — the orchestrator
# ===========================================================================
@dataclass
class PortfolioResult:
    portfolio_id: str
    status: str
    workflow_status: Dict[str, str] = field(default_factory=dict)
    succeeded_workflows: List[str] = field(default_factory=list)
    failed_workflows: List[str] = field(default_factory=list)
    cancelled_workflows: List[str] = field(default_factory=list)
    rounds: int = 0
    trace: Optional[PortfolioTrace] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "status": self.status,
            "workflow_status": dict(self.workflow_status),
            "succeeded_workflows": list(self.succeeded_workflows),
            "failed_workflows": list(self.failed_workflows),
            "cancelled_workflows": list(self.cancelled_workflows),
            "rounds": self.rounds,
            "trace": self.trace.to_list() if self.trace else [],
        }


class PortfolioScheduler:
    """Deterministic, bounded multi-workflow scheduler.

    It advances workflows through their public H17/H21 execution interfaces; it
    never executes goals directly.  A scheduling round: evaluate dependencies →
    classify readiness → order by effective priority (with aging) + fairness →
    reserve portfolio budget → acquire resources atomically → grant a quantum →
    reconcile → checkpoint.
    """

    def __init__(self, portfolio: WorkflowPortfolio, *, store: Optional[InMemoryPortfolioStore] = None) -> None:
        self.portfolio = portfolio
        self.store = store
        self._last_ckpt_id: Optional[str] = None

    # ----- dependency evaluation (§14) -----
    def _dependency_state(self, entry: PortfolioWorkflowEntry) -> Tuple[str, Optional[WorkflowDependency]]:
        """Return ('SATISFIED'|'WAITING'|'FAILED', failing_dep)."""
        p = self.portfolio
        for dep in p.dependencies.dependencies_of(entry.workflow_id):
            pred = p.entries.get(dep.predecessor)
            if pred is None:
                return "WAITING", dep
            if dep.dep_type == DependencyType.REQUIRES_COMPLETION:
                if pred.status == PortfolioWorkflowStatus.COMPLETED:
                    continue
                if pred.status in (PortfolioWorkflowStatus.FAILED, PortfolioWorkflowStatus.CANCELLED):
                    return "FAILED", dep
                return "WAITING", dep
            if dep.dep_type == DependencyType.REQUIRES_SUCCESS:
                if pred.status == PortfolioWorkflowStatus.COMPLETED and pred.succeeded:
                    continue
                if pred.status in (PortfolioWorkflowStatus.FAILED, PortfolioWorkflowStatus.CANCELLED) \
                        or (pred.status == PortfolioWorkflowStatus.COMPLETED and not pred.succeeded):
                    return "FAILED", dep
                return "WAITING", dep
            if dep.dep_type == DependencyType.REQUIRES_MILESTONE:
                key = pred.milestone_keys.get(dep.milestone or "")
                if key and pred.controller.milestone_reached(key):
                    continue
                if pred.status in (PortfolioWorkflowStatus.FAILED, PortfolioWorkflowStatus.CANCELLED):
                    return "FAILED", dep
                return "WAITING", dep
            if dep.dep_type == DependencyType.REQUIRES_OUTPUT:
                ref = p.outputs.get((dep.predecessor, dep.output_name or ""))
                if ref is not None and ref.available and ref.version >= dep.min_version:
                    continue
                if pred.status in (PortfolioWorkflowStatus.FAILED, PortfolioWorkflowStatus.CANCELLED):
                    return "FAILED", dep
                return "WAITING", dep
            if dep.dep_type == DependencyType.REQUIRES_REVIEW_DECISION:
                decided = pred.review_decisions.get(dep.review_key or "")
                if decided is True:
                    continue
                if decided is False:
                    return "FAILED", dep
                return "WAITING", dep
        return "SATISFIED", None

    def _apply_dependency_failure(self, entry: PortfolioWorkflowEntry, dep: WorkflowDependency) -> None:
        policy = self.portfolio.scheduling_policy.dependency_failure_policy
        p = self.portfolio
        p.trace.record(PortfolioEvent.DEPENDENCY_FAILED, workflow_id=entry.workflow_id,
                       predecessor=dep.predecessor, dep_type=dep.dep_type, policy=policy)
        if policy == DependencyFailurePolicy.BLOCK_DEPENDENT:
            entry.set_status(PortfolioWorkflowStatus.BLOCKED)
        elif policy == DependencyFailurePolicy.CANCEL_DEPENDENT:
            self.cancel(entry.workflow_id, scope=CancellationScope.WORKFLOW_ONLY,
                        reason=f"dependency {dep.predecessor} failed")
        elif policy == DependencyFailurePolicy.ALLOW_DEGRADED:
            entry.degraded = True
            entry.set_status(PortfolioWorkflowStatus.READY)
        elif policy == DependencyFailurePolicy.REQUIRE_HUMAN_DECISION:
            entry.set_status(PortfolioWorkflowStatus.WAITING_FOR_REVIEW)

    # ----- readiness classification (§6) -----
    #: Sticky states are managed by explicit events, not by re-classification:
    #: portfolio-budget exhaustion never frees; review clears only via an
    #: external decision poke; paused resumes explicitly.
    _STICKY = frozenset({
        PortfolioWorkflowStatus.WAITING_FOR_BUDGET,
        PortfolioWorkflowStatus.WAITING_FOR_REVIEW,
    })

    def _classify(self, entry: PortfolioWorkflowEntry) -> None:
        """Update one workflow's orchestration status (never mutates H17)."""
        if entry.is_terminal():
            return
        if entry.pause_state == PauseState.PAUSED:
            entry.set_status(PortfolioWorkflowStatus.PAUSED)
            return
        if entry.status in self._STICKY:
            return
        state, dep = self._dependency_state(entry)
        if state == "FAILED":
            self._apply_dependency_failure(entry, dep)  # type: ignore[arg-type]
            return
        if state == "WAITING":
            entry.set_status(PortfolioWorkflowStatus.WAITING_FOR_DEPENDENCY)
            self.portfolio.trace.record(PortfolioEvent.WORKFLOW_WAITING_FOR_DEPENDENCY,
                                        workflow_id=entry.workflow_id, predecessor=dep.predecessor if dep else None)
            return
        # Dependencies satisfied → runnable (WAITING_FOR_RESOURCE retries here).
        entry.set_status(PortfolioWorkflowStatus.READY)

    def _is_eligible(self, entry: PortfolioWorkflowEntry) -> bool:
        return entry.status == PortfolioWorkflowStatus.READY

    def notify_review_ready(self, workflow_id: str) -> None:
        """External signal that a workflow's human review is resolved (§23).

        Clears the sticky WAITING_FOR_REVIEW so the workflow is reconsidered.
        The controller's own H19 review gate remains authoritative for what
        actually runs.
        """
        entry = self.portfolio.entries[workflow_id]
        if entry.status == PortfolioWorkflowStatus.WAITING_FOR_REVIEW:
            entry.set_status(PortfolioWorkflowStatus.READY)
            self.portfolio.trace.record(PortfolioEvent.WORKFLOW_RESUMED, workflow_id=workflow_id,
                                        reason="review resolved")

    # ----- deterministic ordering (§8, §9, §10, §21) -----
    def _order_eligible(self, eligible: List[PortfolioWorkflowEntry]) -> List[PortfolioWorkflowEntry]:
        cap = self.portfolio.scheduling_policy.aging_cap
        deps = self.portfolio.dependencies
        return sorted(
            eligible,
            key=lambda e: (
                e.effective_rank(cap),          # priority class (with bounded aging)
                deps.depth(e.workflow_id),      # dependency depth
                -e.deficit,                     # fairness within class (deficit RR)
                e.registration_sequence,        # stable registration order
                e.workflow_id,                  # final tie-break
            ),
        )

    def _concurrency_ok(self, entry: PortfolioWorkflowEntry, granted: List[PortfolioWorkflowEntry],
                        per_agent: Dict[str, int], per_scope: Dict[str, int], per_class: Dict[str, int]) -> bool:
        pol = self.portfolio.concurrency_policy
        if len(granted) >= pol.max_concurrent_workflows:
            return False
        if pol.max_workflows_per_agent is not None and entry.assigned_agent:
            if per_agent.get(entry.assigned_agent, 0) >= pol.max_workflows_per_agent:
                return False
        if pol.max_workflows_per_authority_scope is not None:
            for s in entry.authority_scope:
                if per_scope.get(s, 0) >= pol.max_workflows_per_authority_scope:
                    return False
        if pol.max_workflows_per_resource_class is not None and entry.resource_class:
            if per_class.get(entry.resource_class, 0) >= pol.max_workflows_per_resource_class:
                return False
        return True

    # ----- deadlock detection (§18) -----
    def _wait_for_graph(self, waiting: List[PortfolioWorkflowEntry]) -> Dict[str, Set[str]]:
        graph: Dict[str, Set[str]] = {}
        for e in waiting:
            graph[e.workflow_id] = self.portfolio.resources.blockers_for(list(e.resource_claims))
        return graph

    def _find_cycle(self, graph: Dict[str, Set[str]]) -> Optional[List[str]]:
        WHITE, GREY, BLACK = 0, 1, 2
        color = {n: WHITE for n in graph}
        stack: List[str] = []

        def visit(n: str) -> Optional[List[str]]:
            color[n] = GREY
            stack.append(n)
            for m in sorted(graph.get(n, set())):
                if m not in color:
                    continue
                if color[m] == GREY:
                    return stack[stack.index(m):] + [m]
                if color[m] == WHITE:
                    c = visit(m)
                    if c:
                        return c
            color[n] = BLACK
            stack.pop()
            return None

        for n in sorted(graph):
            if color[n] == WHITE:
                c = visit(n)
                if c:
                    return c
        return None

    def _resolve_deadlock(self, cycle: List[str]) -> None:
        policy = self.portfolio.scheduling_policy.deadlock_policy
        p = self.portfolio
        members = sorted(set(cycle))
        p.trace.record(PortfolioEvent.DEADLOCK_DETECTED, cycle=members, policy=policy)
        entries = [p.entries[w] for w in members]
        if policy == DeadlockPolicy.PAUSE_YOUNGEST:
            youngest = max(entries, key=lambda e: e.registration_sequence)
            self.pause(youngest.workflow_id)
        elif policy == DeadlockPolicy.CANCEL_LOWEST_PRIORITY:
            cap = p.scheduling_policy.aging_cap
            lowest = max(entries, key=lambda e: (e.effective_rank(cap), e.registration_sequence))
            self.cancel(lowest.workflow_id, scope=CancellationScope.WORKFLOW_ONLY, reason="deadlock")
        elif policy == DeadlockPolicy.REQUIRE_HUMAN_DECISION:
            for e in entries:
                e.set_status(PortfolioWorkflowStatus.WAITING_FOR_REVIEW)
        elif policy == DeadlockPolicy.FAIL_PORTFOLIO:
            p.set_status(PortfolioStatus.FAILED)

    # ----- pause / resume / cancel (§22, §26) -----
    def pause(self, workflow_id: str) -> None:
        entry = self.portfolio.entries[workflow_id]
        if entry.is_terminal():
            return
        entry.pause_state = PauseState.PAUSED
        entry.set_status(PortfolioWorkflowStatus.PAUSED)
        self.portfolio.resources.release_all(workflow_id)  # release at safe boundary
        self.portfolio.trace.record(PortfolioEvent.WORKFLOW_PAUSED, workflow_id=workflow_id)

    def resume(self, workflow_id: str) -> None:
        entry = self.portfolio.entries[workflow_id]
        if entry.pause_state == PauseState.PAUSED:
            entry.pause_state = PauseState.ACTIVE
            entry.set_status(PortfolioWorkflowStatus.REGISTERED)
            self.portfolio.trace.record(PortfolioEvent.WORKFLOW_RESUMED, workflow_id=workflow_id)

    def cancel(self, workflow_id: str, *, scope: str = CancellationScope.WORKFLOW_ONLY,
               reason: str = "cancelled") -> None:
        p = self.portfolio
        targets: List[str] = [workflow_id]
        if scope == CancellationScope.DEPENDENT_SUBGRAPH:
            targets = self._dependent_closure(workflow_id)
        elif scope == CancellationScope.PORTFOLIO_ALL:
            targets = list(p.entries.keys())
        for wid in targets:
            entry = p.entries[wid]
            if entry.is_terminal():
                continue  # idempotent
            entry.cancel_reason = reason
            entry.set_status(PortfolioWorkflowStatus.CANCELLED)
            entry.pause_state = PauseState.ACTIVE
            p.resources.release_all(wid)
            p.cancellation_state[wid] = reason
            p.trace.record(PortfolioEvent.WORKFLOW_CANCELLED, workflow_id=wid, scope=scope, reason=reason)

    def _dependent_closure(self, workflow_id: str) -> List[str]:
        out: Set[str] = set()
        stack = [workflow_id]
        while stack:
            cur = stack.pop()
            if cur in out:
                continue
            out.add(cur)
            stack.extend(self.portfolio.dependencies.dependents_of(cur))
        return sorted(out)

    # ----- output / milestone harvesting -----
    def _harvest_outputs(self, entry: PortfolioWorkflowEntry) -> None:
        p = self.portfolio
        for mem_key, out_name in sorted(entry.output_keys.items()):
            ref = entry.controller.output_ref(mem_key, out_name)
            if ref is not None:
                p.outputs[(entry.workflow_id, out_name)] = ref

    # ----- the scheduling round -----
    def _advance_workflow(self, entry: PortfolioWorkflowEntry) -> bool:
        """Grant one quantum to *entry*.  Returns True iff a quantum actually
        ran (real progress); budget/resource denials return False."""
        p = self.portfolio
        # 1. Reserve portfolio budget for this quantum.
        ok, kind, dim = p.budget.reserve_quantum(entry.workflow_id, entry.budget_estimate)
        if not ok:
            if kind == "MAX_ALLOCATION":
                # Hard per-workflow cap reached: succeeded workflows complete,
                # unfinished ones fail (they can never afford more).
                if entry.succeeded:
                    entry.set_status(PortfolioWorkflowStatus.COMPLETED)
                else:
                    entry.set_status(PortfolioWorkflowStatus.FAILED)
                    p.trace.record(PortfolioEvent.WORKFLOW_FAILED, workflow_id=entry.workflow_id,
                                   reason="max allocation exhausted")
                    self._apply_workflow_failure(entry)
            else:
                entry.set_status(PortfolioWorkflowStatus.WAITING_FOR_BUDGET)
                p.trace.record(PortfolioEvent.WORKFLOW_WAITING_FOR_BUDGET, workflow_id=entry.workflow_id,
                               kind=kind, dimension=dim)
            return False
        # 2. Acquire resource claims atomically (all-or-none).
        claims = list(entry.resource_claims)
        acquired = False
        if claims:
            acquired = p.resources.try_acquire(entry.workflow_id, claims)
            if not acquired:
                p.budget.release(entry.budget_estimate)
                entry.set_status(PortfolioWorkflowStatus.WAITING_FOR_RESOURCE)
                p.trace.record(PortfolioEvent.WORKFLOW_WAITING_FOR_RESOURCE, workflow_id=entry.workflow_id,
                               resources=[c.resource_key for c in claims])
                return False
            for c in claims:
                p.trace.record(PortfolioEvent.RESOURCE_CLAIM_ACQUIRED, workflow_id=entry.workflow_id,
                               resource=c.resource_key, mode=c.access_mode)
        # 3. Grant a quantum and advance through the H21 interface.
        entry.set_status(PortfolioWorkflowStatus.RUNNING)
        entry.last_selected_round = p.round
        p.trace.record(PortfolioEvent.WORKFLOW_QUANTUM_GRANTED, workflow_id=entry.workflow_id, round=p.round)
        qr = entry.controller.advance_quantum()
        # 4. Reconcile budget with actual usage.
        p.budget.reconcile(entry.workflow_id, entry.budget_estimate, qr.budget_delta)
        # 5. Release resources at the safe (post-quantum) boundary.
        if acquired:
            for key in p.resources.release_all(entry.workflow_id):
                p.trace.record(PortfolioEvent.RESOURCE_CLAIM_RELEASED, workflow_id=entry.workflow_id, resource=key)
        # 6. Harvest durable outputs/milestones.
        self._harvest_outputs(entry)
        if qr.committed_goals:
            p.trace.record(PortfolioEvent.WORKFLOW_QUANTUM_COMMITTED, workflow_id=entry.workflow_id,
                           committed=qr.committed_goals)
        # 7. Update orchestration status from the quantum outcome.
        if qr.budget_blocked:
            entry.set_status(PortfolioWorkflowStatus.WAITING_FOR_BUDGET)
        elif qr.terminal:
            entry.succeeded = qr.succeeded
            if qr.succeeded:
                entry.set_status(PortfolioWorkflowStatus.COMPLETED)
                p.trace.record(PortfolioEvent.WORKFLOW_COMPLETED, workflow_id=entry.workflow_id)
            else:
                entry.set_status(PortfolioWorkflowStatus.FAILED)
                p.trace.record(PortfolioEvent.WORKFLOW_FAILED, workflow_id=entry.workflow_id)
                self._apply_workflow_failure(entry)
        elif qr.waiting_review:
            entry.set_status(PortfolioWorkflowStatus.WAITING_FOR_REVIEW)
            p.trace.record(PortfolioEvent.WORKFLOW_WAITING_FOR_REVIEW, workflow_id=entry.workflow_id)
        else:
            entry.set_status(PortfolioWorkflowStatus.READY)
        return True

    def _apply_workflow_failure(self, entry: PortfolioWorkflowEntry) -> None:
        policy = self.portfolio.scheduling_policy.portfolio_failure_policy
        if policy == PortfolioFailurePolicy.FAIL_PORTFOLIO:
            self.portfolio.set_status(PortfolioStatus.FAILED)
        elif policy == PortfolioFailurePolicy.FAIL_DEPENDENTS:
            for wid in self.portfolio.dependencies.dependents_of(entry.workflow_id):
                self.cancel(wid, scope=CancellationScope.WORKFLOW_ONLY,
                            reason=f"predecessor {entry.workflow_id} failed")
        # ISOLATE_WORKFLOW (default): do nothing further — failure is contained.

    def run_round(self) -> bool:
        """Advance the portfolio by one scheduling round.  Returns True if any
        workflow made progress this round."""
        p = self.portfolio
        p.set_status(PortfolioStatus.ACTIVE)

        # Fairness credit: eligible workflows accrue their weight each round.
        for entry in p.ordered_entries():
            self._classify(entry)
        eligible = [e for e in p.ordered_entries() if self._is_eligible(e)]
        for e in eligible:
            e.deficit += e.weight

        ordered = self._order_eligible(eligible)

        granted: List[PortfolioWorkflowEntry] = []
        per_agent: Dict[str, int] = {}
        per_scope: Dict[str, int] = {}
        per_class: Dict[str, int] = {}
        for entry in ordered:
            if not self._concurrency_ok(entry, granted, per_agent, per_scope, per_class):
                continue
            granted.append(entry)
            entry.deficit -= 1.0  # deficit round-robin cost
            if entry.assigned_agent:
                per_agent[entry.assigned_agent] = per_agent.get(entry.assigned_agent, 0) + 1
            for s in entry.authority_scope:
                per_scope[s] = per_scope.get(s, 0) + 1
            if entry.resource_class:
                per_class[entry.resource_class] = per_class.get(entry.resource_class, 0) + 1
            p.trace.record(PortfolioEvent.WORKFLOW_SELECTED, workflow_id=entry.workflow_id, round=p.round)

        progressed = False
        for entry in granted:
            if self._advance_workflow(entry):
                progressed = True

        # Priority aging: eligible-but-not-selected runnable workflows age
        # (bounded); selected ones reset; waiting/blocked ones do not age.
        selected_ids = {e.workflow_id for e in granted}
        cap = p.scheduling_policy.aging_cap
        inc = p.scheduling_policy.aging_increment
        for entry in eligible:
            if entry.workflow_id in selected_ids:
                entry.age = 0
            elif entry.status == PortfolioWorkflowStatus.READY:  # still runnable, lost the slot
                new_age = min(entry.age + inc, cap)
                if new_age != entry.age:
                    entry.age = new_age
                    p.trace.record(PortfolioEvent.PRIORITY_AGED, workflow_id=entry.workflow_id, age=entry.age)

        # Deadlock detection across resource waiters (safety net — atomic
        # all-or-none acquisition already prevents hold-and-wait in the common
        # case).  Only engage when nothing progressed this round.
        waiting_res = [e for e in p.ordered_entries()
                       if e.status == PortfolioWorkflowStatus.WAITING_FOR_RESOURCE]
        if waiting_res and not progressed:
            cycle = self._find_cycle(self._wait_for_graph(waiting_res))
            if cycle:
                self._resolve_deadlock(cycle)
                progressed = True  # a policy action was taken

        p.round += 1

        if self.store is not None:
            self._checkpoint()
        return progressed

    def run(self) -> PortfolioResult:
        """Run scheduling rounds until the portfolio reaches a terminal or
        fully-blocked state."""
        p = self.portfolio
        max_rounds = p.scheduling_policy.max_rounds
        for _ in range(max_rounds):
            if p.status in (PortfolioStatus.FAILED, PortfolioStatus.CANCELLED):
                break
            non_terminal = [e for e in p.ordered_entries() if not e.is_terminal()]
            if not non_terminal:
                break
            progressed = self.run_round()
            # Re-classify to surface newly-terminal / waiting states.
            for entry in p.ordered_entries():
                self._classify(entry)
            still_active = [e for e in p.ordered_entries() if not e.is_terminal()]
            if not still_active:
                break
            if not progressed:
                # No workflow can advance (all waiting for external review /
                # unresolved) — stop rather than spin.
                break
        return self._finalize()

    def _finalize(self) -> PortfolioResult:
        p = self.portfolio
        succeeded = sorted(w for w, e in p.entries.items()
                           if e.status == PortfolioWorkflowStatus.COMPLETED and e.succeeded)
        failed = sorted(w for w, e in p.entries.items() if e.status == PortfolioWorkflowStatus.FAILED)
        cancelled = sorted(w for w, e in p.entries.items() if e.status == PortfolioWorkflowStatus.CANCELLED)
        all_terminal = all(e.is_terminal() for e in p.entries.values())
        if p.status not in (PortfolioStatus.FAILED, PortfolioStatus.CANCELLED):
            if all_terminal and not failed:
                p.set_status(PortfolioStatus.COMPLETED)
                p.trace.record(PortfolioEvent.PORTFOLIO_COMPLETED, portfolio_id=p.portfolio_id)
            elif all_terminal and failed:
                # Failures were isolated by policy; portfolio completes with
                # failed members unless the policy escalated to FAIL_PORTFOLIO.
                p.set_status(PortfolioStatus.COMPLETED)
                p.trace.record(PortfolioEvent.PORTFOLIO_COMPLETED, portfolio_id=p.portfolio_id,
                               failed=failed)
            else:
                p.set_status(PortfolioStatus.PAUSED)  # blocked on external input
        else:
            p.trace.record(PortfolioEvent.PORTFOLIO_FAILED, portfolio_id=p.portfolio_id)
        return PortfolioResult(
            portfolio_id=p.portfolio_id, status=p.status,
            workflow_status={w: e.status for w, e in p.entries.items()},
            succeeded_workflows=succeeded, failed_workflows=failed, cancelled_workflows=cancelled,
            rounds=p.round, trace=p.trace,
        )

    # ----- durability (§28, §29, §30) -----
    def _checkpoint(self) -> PortfolioCheckpoint:
        p = self.portfolio
        body = p.to_dict()
        refs = {w: digest_of(canonical_json(e.to_dict())) for w, e in p.entries.items()}
        cp = PortfolioCheckpoint(
            checkpoint_id=f"{p.portfolio_id}::round{p.round}",
            portfolio_id=p.portfolio_id, logical_sequence=p.trace.next_seq,
            body=body, workflow_checkpoint_refs=refs,
        ).with_digest()
        assert self.store is not None
        self.store.compare_and_save(cp, expected_latest_id=self._last_ckpt_id)
        self._last_ckpt_id = cp.checkpoint_id
        p.trace.record(PortfolioEvent.PORTFOLIO_CHECKPOINTED, checkpoint_id=cp.checkpoint_id)
        return cp

    def classify_in_flight(self) -> Dict[str, str]:
        """Classify each workflow for recovery (§30)."""
        out: Dict[str, str] = {}
        for wid, e in self.portfolio.entries.items():
            if e.is_terminal():
                out[wid] = InFlightWorkflowStatus.TERMINAL
            elif e.status in (PortfolioWorkflowStatus.WAITING_FOR_DEPENDENCY,
                              PortfolioWorkflowStatus.WAITING_FOR_BUDGET,
                              PortfolioWorkflowStatus.WAITING_FOR_RESOURCE,
                              PortfolioWorkflowStatus.WAITING_FOR_REVIEW,
                              PortfolioWorkflowStatus.PAUSED,
                              PortfolioWorkflowStatus.BLOCKED):
                out[wid] = InFlightWorkflowStatus.WAITING
            elif e.status == PortfolioWorkflowStatus.RUNNING:
                out[wid] = InFlightWorkflowStatus.RUNNING_NO_COMMIT
            else:
                out[wid] = InFlightWorkflowStatus.NOT_GRANTED
        return out


# ===========================================================================
# Rendering
# ===========================================================================
def format_portfolio(portfolio: WorkflowPortfolio) -> str:
    lines = [
        f"Portfolio {portfolio.portfolio_id}  [{portfolio.status}]  round={portfolio.round}",
        "-" * 60,
    ]
    for e in portfolio.ordered_entries():
        lines.append(f"  {e.workflow_id:<16} {e.priority:<10} {e.status:<24} "
                     f"age={e.age} deficit={e.deficit:.1f}")
    return "\n".join(lines)


def format_portfolio_trace(result: PortfolioResult) -> str:
    lines = [
        f"Portfolio: {result.portfolio_id}  status={result.status}  rounds={result.rounds}",
        f"succeeded={result.succeeded_workflows} failed={result.failed_workflows} "
        f"cancelled={result.cancelled_workflows}",
        "=" * 60,
    ]
    if result.trace is None:
        return "\n".join(lines)
    for e in result.trace.entries:
        wf = f" [{e.workflow_id}]" if e.workflow_id else ""
        lines.append(f"  {e.seq:>3} {e.event:<32}{wf}")
    return "\n".join(lines)
