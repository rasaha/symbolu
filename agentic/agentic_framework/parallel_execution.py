"""
Deterministic Parallel Goal Execution (H21)
===========================================

Bounded, deterministic, **in-process** parallel execution of independent
governed goals inside one workflow.

```
          ┌─ Goal A ─┐
READY ────┤          ├── Deterministic Join ── Commit
          └─ Goal B ─┘
```

Where H15 (:mod:`hierarchical_planning`) executes one wave of READY goals by
handing the whole wave to the **unchanged** H16 :class:`Coordinator`
(sequentially), H21 lets *proven-independent* goals in a wave execute
concurrently — while preserving every governance guarantee H10–H19 already
provide:

* deterministic scheduling (stable wave membership + goal order);
* dependency correctness (a dependent goal is released only after every
  predecessor result is *durably joined*, never on worker completion alone);
* one shared H11 :class:`RunBudget`, reserved under a lock so concurrent
  workers can never oversubscribe it;
* H16 authority: every worker is independently authorized before dispatch;
* H14 WorkingMemory integrity: workers read immutable snapshots and return
  *proposed* writes; the joiner commits them in a deterministic order with
  version-conflict detection (never last-writer-wins);
* H18 durability: wave state is checkpointed with a fail-closed digest so an
  interrupted wave recovers without duplicating already-joined work;
* H19 human review: a review-gated goal is held without blocking unrelated
  parallel-safe goals;
* trace reconstructability: every lifecycle action is logged with a *logical*
  sequence number, never wall-clock completion order;
* safe cooperative cancellation and recovery.

Design boundary (do not cross): this module composes **only** on the public
interfaces of H10–H19 in this package.  It does not modify any of them, and it
does not touch alternate control-plane / ActionGate / TAP implementations,
message buses, distributed schedulers, cloud orchestration, or databases.

Explicitly out of scope (see the module tests and docs): distributed or
multi-process execution, Kubernetes scheduling, queue-based workers,
cross-machine locking, speculative / race-based winner selection, unrestricted
threads, arbitrary async side effects, and H20 external-action execution.
Concurrency here is bounded and cooperative; determinism is proven by
:class:`SynchronousBackend` == :class:`ThreadPoolBackend` on the same inputs.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, replace as dc_replace
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    List,
    Optional,
    Protocol,
    Tuple,
)

from agentic.agentic_framework.cancellation import CancellationToken
from agentic.agentic_framework.run_budget import (
    RunBudget,
    RunBudgetLimits,
    BudgetExhausted,
    Reservation,
)
from agentic.agentic_framework.working_memory import WorkingMemory
from agentic.agentic_framework.hierarchical_planning import (
    Goal,
    GoalStatus,
    GoalNode,
    GoalTree,
    MissionPlan,
)
from agentic.agentic_framework.coordination import (
    AgentProfile,  # noqa: F401  (re-exported convenience)
    CapabilityRegistry,
    CoordinationGoal,
    DelegationContract,
    GoalOwnershipLedger,
    AuthorityModel,
    WorkerResult,
    WorkerUnavailable,
    COORDINATOR_ID,
)
from agentic.agentic_framework.workflow_durability import (
    canonical_json,
    digest_of,
    CheckpointConflict,
    RecoveryError,
)

__all__ = [
    # vocabulary
    "WaveStatus",
    "GoalConcurrency",
    "GoalOutcome",
    "FailurePolicy",
    "CancellationSource",
    "SideEffectClass",
    "MemoryConflictPolicy",
    "InFlightStatus",
    "ParallelEvent",
    # policy / footprint
    "ConcurrencyPolicy",
    "GoalExecutionFootprint",
    "footprint_from_goal",
    "FootprintConflictDetector",
    # budget
    "BudgetEstimate",
    "BudgetLedgerEntry",
    "BudgetReservation",
    "SharedBudgetCoordinator",
    # wave
    "WaveTransition",
    "ExecutionWave",
    # execution units
    "MemoryView",
    "AssumptionView",
    "ParallelGoalContext",
    "ProposedMemoryWrite",
    "ProposedAssumptionTransition",
    "GoalExecutionResult",
    "ParallelWorker",
    "CoordinatedParallelWorker",
    "DispatchUnit",
    # scheduling / review
    "ReviewGate",
    "StaticReviewGate",
    "ParallelGoalScheduler",
    # join
    "JoinReport",
    "DeterministicJoiner",
    # backends
    "ParallelExecutionBackend",
    "SynchronousBackend",
    "ThreadPoolBackend",
    # trace
    "ParallelTraceEntry",
    "ParallelExecutionTrace",
    # durability / recovery
    "WaveCheckpoint",
    "InMemoryWaveStore",
    "WaveRecoveryPlanner",
    # top-level executor
    "ParallelHierarchyStatus",
    "ParallelHierarchyResult",
    "ParallelHierarchyExecutor",
    "derive_execution_state",
    # rendering
    "format_execution_wave",
    "format_parallel_trace",
]


# ===========================================================================
# Vocabulary (string-constant namespaces — matches the H15/H16 idiom)
# ===========================================================================
class WaveStatus:
    """Append-only lifecycle of an :class:`ExecutionWave`."""

    CREATED = "CREATED"
    RESERVED = "RESERVED"
    RUNNING = "RUNNING"
    JOINING = "JOINING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    BLOCKED = "BLOCKED"


class GoalConcurrency:
    """How a goal may be co-scheduled.  ``UNKNOWN`` defaults to serial."""

    PARALLEL_SAFE = "PARALLEL_SAFE"
    SERIAL_ONLY = "SERIAL_ONLY"
    EXCLUSIVE_GROUP = "EXCLUSIVE_GROUP"
    UNKNOWN = "UNKNOWN"


class GoalOutcome:
    """Outcome a worker reports for one goal."""

    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    WAITING = "WAITING"
    CANCELLED = "CANCELLED"
    REQUIRES_REPLAN = "REQUIRES_REPLAN"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class FailurePolicy:
    """What a wave does when a goal fails."""

    FAIL_FAST = "FAIL_FAST"
    COMPLETE_IN_FLIGHT = "COMPLETE_IN_FLIGHT"
    ISOLATE_FAILURE = "ISOLATE_FAILURE"
    REPLAN_AFFECTED = "REPLAN_AFFECTED"


class CancellationSource:
    """Where a cancellation originated (for the trace)."""

    MISSION = "MISSION"
    WORKFLOW = "WORKFLOW"
    WAVE_FAILURE_POLICY = "WAVE_FAILURE_POLICY"
    HUMAN = "HUMAN"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    ASSUMPTION_INVALIDATED = "ASSUMPTION_INVALIDATED"
    DEPENDENCY_FAILED = "DEPENDENCY_FAILED"


class SideEffectClass:
    """Replay-safety classification for in-flight recovery."""

    PURE = "PURE"                    # no side effects; replay always safe
    DETERMINISTIC = "DETERMINISTIC"  # reproducible; replay safe under policy
    EXTERNAL = "EXTERNAL"            # may have external effects; never replayed


class MemoryConflictPolicy:
    """How the joiner resolves a versioned-memory write conflict.

    ``REJECT`` is the fail-closed default.  Last-writer-wins is never a
    silent default (§16).
    """

    REJECT = "REJECT"
    SERIALIZE_RETRY = "SERIALIZE_RETRY"
    LOCALIZED_REPLAN = "LOCALIZED_REPLAN"
    MERGE = "MERGE"


class InFlightStatus:
    """Recovery classification of a dispatched goal after process loss."""

    NOT_STARTED = "NOT_STARTED"
    STARTED_NO_RESULT = "STARTED_NO_RESULT"
    RESULT_AVAILABLE_NOT_JOINED = "RESULT_AVAILABLE_NOT_JOINED"
    JOINED = "JOINED"


class ParallelEvent:
    """Trace event kinds (logical, not wall-clock)."""

    WAVE_CREATED = "WAVE_CREATED"
    GOAL_SELECTED_FOR_WAVE = "GOAL_SELECTED_FOR_WAVE"
    GOAL_HELD_FOR_REVIEW = "GOAL_HELD_FOR_REVIEW"
    GOAL_SERIALIZED = "GOAL_SERIALIZED"
    BUDGET_RESERVED = "BUDGET_RESERVED"
    BUDGET_DENIED = "BUDGET_DENIED"
    GOAL_DISPATCHED = "GOAL_DISPATCHED"
    GOAL_STARTED = "GOAL_STARTED"
    GOAL_RESULT_PRODUCED = "GOAL_RESULT_PRODUCED"
    GOAL_CANCEL_REQUESTED = "GOAL_CANCEL_REQUESTED"
    GOAL_RESULT_JOINED = "GOAL_RESULT_JOINED"
    MEMORY_CONFLICT_DETECTED = "MEMORY_CONFLICT_DETECTED"
    ASSUMPTION_CONFLICT_DETECTED = "ASSUMPTION_CONFLICT_DETECTED"
    DEPENDENCY_BARRIER_RELEASED = "DEPENDENCY_BARRIER_RELEASED"
    BUDGET_RECONCILED = "BUDGET_RECONCILED"
    WAVE_COMPLETED = "WAVE_COMPLETED"
    WAVE_FAILED = "WAVE_FAILED"
    WAVE_RECOVERED = "WAVE_RECOVERED"


# Goal statuses that are terminal in the H15 tree (never re-executed).
_TERMINAL = {GoalStatus.COMPLETED, GoalStatus.FAILED, GoalStatus.ABORTED}
_FAILED = {GoalStatus.FAILED}
# H21-owned "held for human review" reason marker recorded on a BLOCKED node.
_REVIEW_REASON = "held for human review"


# ===========================================================================
# Concurrency policy (immutable)
# ===========================================================================
@dataclass(frozen=True)
class ConcurrencyPolicy:
    """Immutable bounds on how many goals may co-execute.

    Defaults are deliberately conservative (§8): a small global cap and no
    implicit per-agent / per-scope fan-out.
    """

    max_concurrent_goals: int = 4
    max_concurrent_per_agent: Optional[int] = None
    max_concurrent_per_authority_scope: Optional[int] = None
    max_wave_size: Optional[int] = None
    failure_policy: str = FailurePolicy.ISOLATE_FAILURE
    cancellation_policy: str = "COOPERATIVE"
    memory_conflict_policy: str = MemoryConflictPolicy.REJECT
    #: Authority scopes that may never run two goals concurrently.
    exclusive_authority_scopes: FrozenSet[str] = frozenset()
    #: If True, STARTED_NO_RESULT goals whose side-effect class is PURE or
    #: DETERMINISTIC may be re-dispatched on recovery.  Default fail-closed.
    allow_deterministic_replay: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_concurrent_goals": self.max_concurrent_goals,
            "max_concurrent_per_agent": self.max_concurrent_per_agent,
            "max_concurrent_per_authority_scope": self.max_concurrent_per_authority_scope,
            "max_wave_size": self.max_wave_size,
            "failure_policy": self.failure_policy,
            "cancellation_policy": self.cancellation_policy,
            "memory_conflict_policy": self.memory_conflict_policy,
            "exclusive_authority_scopes": sorted(self.exclusive_authority_scopes),
            "allow_deterministic_replay": self.allow_deterministic_replay,
        }


# ===========================================================================
# Goal execution footprint + conflict detection (§9, §10)
# ===========================================================================
@dataclass(frozen=True)
class GoalExecutionFootprint:
    """What a goal reads / writes / owns — the basis for co-scheduling safety.

    A goal defaults to ``UNKNOWN`` concurrency (serial) unless it explicitly
    declares ``PARALLEL_SAFE``.  Absence of a dependency edge is never
    sufficient to infer parallel safety (§10).
    """

    goal_id: str
    read_memory_keys: FrozenSet[str] = frozenset()
    write_memory_keys: FrozenSet[str] = frozenset()
    assumption_reads: FrozenSet[str] = frozenset()
    assumption_writes: FrozenSet[str] = frozenset()
    owned_resources: FrozenSet[str] = frozenset()
    authority_scope: FrozenSet[str] = frozenset()
    assigned_agent: Optional[str] = None
    exclusive_groups: FrozenSet[str] = frozenset()
    side_effect_class: str = SideEffectClass.DETERMINISTIC
    concurrency: str = GoalConcurrency.UNKNOWN

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "read_memory_keys": sorted(self.read_memory_keys),
            "write_memory_keys": sorted(self.write_memory_keys),
            "assumption_reads": sorted(self.assumption_reads),
            "assumption_writes": sorted(self.assumption_writes),
            "owned_resources": sorted(self.owned_resources),
            "authority_scope": sorted(self.authority_scope),
            "assigned_agent": self.assigned_agent,
            "exclusive_groups": sorted(self.exclusive_groups),
            "side_effect_class": self.side_effect_class,
            "concurrency": self.concurrency,
        }


def footprint_from_goal(
    goal: Goal,
    *,
    concurrency: str = GoalConcurrency.UNKNOWN,
    side_effect_class: str = SideEffectClass.DETERMINISTIC,
    exclusive_groups: FrozenSet[str] = frozenset(),
    owned_resources: Optional[FrozenSet[str]] = None,
) -> GoalExecutionFootprint:
    """Derive a footprint from a declarative :class:`Goal`.

    Read/write keys come from the goal's ``required_memory`` / ``produced_memory``;
    ``concurrency`` must be supplied explicitly (defaults to the safe
    ``UNKNOWN`` → serial) — it is never inferred from the goal itself.
    """
    return GoalExecutionFootprint(
        goal_id=goal.goal_id,
        read_memory_keys=frozenset(goal.required_memory),
        write_memory_keys=frozenset(goal.produced_memory),
        assumption_reads=frozenset(goal.assumptions),
        assumption_writes=frozenset(),
        owned_resources=owned_resources if owned_resources is not None else frozenset({goal.goal_id}),
        authority_scope=frozenset(goal.authority_scope),
        assigned_agent=None,
        exclusive_groups=exclusive_groups,
        side_effect_class=side_effect_class,
        concurrency=concurrency,
    )


class FootprintConflictDetector:
    """Deterministic pairwise co-scheduling safety (§9).

    Two goals may run concurrently only if their footprints are compatible.
    Conservative serialization is always preferred over unsafe parallelism.
    """

    def __init__(self, policy: Optional[ConcurrencyPolicy] = None) -> None:
        self.policy = policy or ConcurrencyPolicy()

    def is_parallelizable(self, fp: GoalExecutionFootprint) -> bool:
        """Whether *fp* may ever share a wave with another goal."""
        return fp.concurrency in (GoalConcurrency.PARALLEL_SAFE, GoalConcurrency.EXCLUSIVE_GROUP)

    def compatible(
        self, a: GoalExecutionFootprint, b: GoalExecutionFootprint
    ) -> Tuple[bool, str]:
        """Return ``(ok, reason)`` for co-scheduling *a* and *b*."""
        # SERIAL_ONLY / UNKNOWN can never be paired.
        for fp in (a, b):
            if fp.concurrency == GoalConcurrency.SERIAL_ONLY:
                return False, f"{fp.goal_id} is SERIAL_ONLY"
            if fp.concurrency == GoalConcurrency.UNKNOWN:
                return False, f"{fp.goal_id} concurrency UNKNOWN (defaults serial)"
        # Same exclusive execution group → mutually exclusive.
        shared_groups = a.exclusive_groups & b.exclusive_groups
        if shared_groups:
            return False, f"shared exclusive group {sorted(shared_groups)}"
        # Both write the same memory key.
        ww = a.write_memory_keys & b.write_memory_keys
        if ww:
            return False, f"write/write conflict on {sorted(ww)}"
        # One writes what the other reads/writes (read-after-write hazard).
        wr = a.write_memory_keys & b.read_memory_keys
        rw = b.write_memory_keys & a.read_memory_keys
        if wr or rw:
            return False, f"read/write hazard on {sorted(wr | rw)}"
        # Assumption hazards: one writes an assumption the other reads/writes.
        aw = a.assumption_writes & (b.assumption_reads | b.assumption_writes)
        bw = b.assumption_writes & (a.assumption_reads | a.assumption_writes)
        if aw or bw:
            return False, f"assumption hazard on {sorted(aw | bw)}"
        # Same owned resource / exclusive goal ownership.
        res = a.owned_resources & b.owned_resources
        if res:
            return False, f"owned-resource conflict on {sorted(res)}"
        # Authority policy prohibits concurrent operation in a scope.
        excl = self.policy.exclusive_authority_scopes
        shared_excl = (a.authority_scope & b.authority_scope) & excl
        if shared_excl:
            return False, f"exclusive authority scope {sorted(shared_excl)}"
        return True, "compatible"


# ===========================================================================
# Shared-budget coordination under concurrency (§11)
# ===========================================================================
@dataclass(frozen=True)
class BudgetEstimate:
    """A conservative pre-execution estimate of a goal's resource use.

    The estimate is a *ceiling*: workers execute against an isolated per-goal
    budget sized to it, so actual usage can never exceed the reservation.
    """

    model_calls: int = 1
    tool_calls: int = 0
    iterations: int = 1
    handoffs: int = 1
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0

    def to_limits(self) -> RunBudgetLimits:
        """The isolated per-goal :class:`RunBudgetLimits` for this estimate."""
        return RunBudgetLimits(
            max_model_calls=self.model_calls,
            max_tool_calls=self.tool_calls if self.tool_calls else None,
            max_prompt_tokens=self.prompt_tokens if self.prompt_tokens else None,
            max_completion_tokens=self.completion_tokens if self.completion_tokens else None,
            max_total_tokens=(self.prompt_tokens + self.completion_tokens) or None,
            max_cost=self.cost if self.cost else None,
            max_iterations=self.iterations,
            max_handoffs=self.handoffs,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "iterations": self.iterations,
            "handoffs": self.handoffs,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost": self.cost,
        }


@dataclass
class BudgetLedgerEntry:
    """Actual resource usage a worker consumed, for reconciliation."""

    model_calls: int = 0
    tool_calls: int = 0
    iterations: int = 0
    handoffs: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0

    @classmethod
    def from_budget(cls, budget: RunBudget) -> "BudgetLedgerEntry":
        u = budget.usage
        return cls(
            model_calls=u.model_calls,
            tool_calls=u.tool_calls,
            iterations=u.iterations,
            handoffs=u.handoffs,
            prompt_tokens=u.prompt_tokens,
            completion_tokens=u.completion_tokens,
            cost=u.cost,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "iterations": self.iterations,
            "handoffs": self.handoffs,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "cost": self.cost,
        }


@dataclass
class BudgetReservation:
    """The outcome of a per-goal reservation from the shared budget."""

    goal_id: str
    ok: bool
    estimate: BudgetEstimate
    reason: Optional[str] = None
    dimension: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal_id,
            "ok": self.ok,
            "estimate": self.estimate.to_dict(),
            "reason": self.reason,
            "dimension": self.dimension,
        }


# Fixed order → deterministic "which dimension was insufficient".
_EST_DIMS: Tuple[str, ...] = (
    "model_calls",
    "tool_calls",
    "iterations",
    "handoffs",
    "prompt_tokens",
    "completion_tokens",
    "cost",
)
_EST_TO_REMAINING = {
    "model_calls": "model_calls",
    "tool_calls": "tool_calls",
    "iterations": "iterations",
    "handoffs": "handoffs",
    "prompt_tokens": "prompt_tokens",
    "completion_tokens": "completion_tokens",
    "cost": "cost",
}


class SharedBudgetCoordinator:
    """Lock-protected reservation on top of one shared H11 :class:`RunBudget`.

    Implements the §11 protocol without changing H11 semantics:

        Estimate → Reserve (before dispatch) → Execute (isolated) →
        Reconcile actual usage → Release unused reservation.

    Reservations are tracked in an H21-owned pool measured against the shared
    budget's live headroom, so they are fully reversible (RunBudget counters
    are monotonic and are only mutated at reconcile with *actual* usage).  A
    single lock serialises reserve + reconcile, so two workers can never
    observe the same remaining budget and overspend it.
    """

    def __init__(self, run_budget: Optional[RunBudget]) -> None:
        self._budget = run_budget
        self._lock = threading.Lock()
        self._reserved: Dict[str, float] = {d: 0.0 for d in _EST_DIMS}

    @property
    def run_budget(self) -> Optional[RunBudget]:
        return self._budget

    # ----- internal (must hold the lock) -----
    def _remaining(self, est_dim: str) -> Optional[float]:
        if self._budget is None:
            return None
        rem = self._budget.remaining(_EST_TO_REMAINING[est_dim])
        return rem  # None = unconstrained

    def _fits(self, est: BudgetEstimate) -> Tuple[bool, Optional[str]]:
        for d in _EST_DIMS:
            need = float(getattr(est, d))
            if need <= 0:
                continue
            rem = self._remaining(d)
            if rem is None:
                continue
            if need + self._reserved[d] > rem:
                return False, d
        return True, None

    # ----- public API -----
    def reserve_wave(self, estimates: Dict[str, BudgetEstimate]) -> Tuple[bool, List[BudgetReservation]]:
        """Atomically reserve for every goal in a wave, or none of them.

        Prevents unsafe partial dispatch (§7/§11): if the aggregate does not
        fit the remaining budget, nothing is reserved and the wave is not
        dispatched.
        """
        with self._lock:
            if self._budget is None:
                return True, [BudgetReservation(gid, True, est) for gid, est in estimates.items()]
            if self._budget.is_exhausted():
                return False, [BudgetReservation(gid, False, est, reason="BUDGET_EXHAUSTED", dimension=None)
                               for gid, est in estimates.items()]
            reservations: List[BudgetReservation] = []
            taken: List[Tuple[str, BudgetEstimate]] = []
            ok_all = True
            for gid in sorted(estimates):  # deterministic aggregate order
                est = estimates[gid]
                fits, dim = self._fits(est)
                if not fits:
                    ok_all = False
                    reservations.append(BudgetReservation(gid, False, est, reason="INSUFFICIENT_BUDGET", dimension=dim))
                    continue
                for d in _EST_DIMS:
                    self._reserved[d] += float(getattr(est, d))
                taken.append((gid, est))
                reservations.append(BudgetReservation(gid, True, est))
            if not ok_all:
                # Roll back tentative reservations — all-or-nothing.
                for gid, est in taken:
                    for d in _EST_DIMS:
                        self._reserved[d] -= float(getattr(est, d))
                return False, reservations
            return True, reservations

    def isolated_budget(self, est: BudgetEstimate, *, clock: Optional[Callable[[], float]] = None) -> RunBudget:
        """A fresh per-goal :class:`RunBudget` capped at the reservation.

        A worker physically cannot spend more than its reservation, so actual
        usage is always ``<=`` the estimate — the invariant that keeps the
        shared budget safe from over-subscription.
        """
        if clock is not None:
            return RunBudget(est.to_limits(), clock=clock).start()
        return RunBudget(est.to_limits()).start()

    def reconcile(self, reservation: BudgetReservation, actual: BudgetLedgerEntry) -> None:
        """Commit actual usage to the shared budget and release the estimate."""
        with self._lock:
            est = reservation.estimate
            if reservation.ok and self._budget is not None:
                # Firm-consume the discrete actuals (monotonic reserve()).
                self._budget.reserve(
                    model_calls=actual.model_calls,
                    iterations=actual.iterations,
                    handoffs=actual.handoffs,
                )
                # Record post-hoc token/cost/tool usage.
                self._budget.record_usage(
                    prompt_tokens=actual.prompt_tokens,
                    completion_tokens=actual.completion_tokens,
                    cost=actual.cost,
                    tool_calls=actual.tool_calls,
                )
            # Release the (possibly unused) reservation.
            if reservation.ok:
                for d in _EST_DIMS:
                    self._reserved[d] = max(0.0, self._reserved[d] - float(getattr(est, d)))

    def release(self, reservation: BudgetReservation) -> None:
        """Release a reservation whose goal never executed (e.g. cancelled)."""
        with self._lock:
            if not reservation.ok:
                return
            est = reservation.estimate
            for d in _EST_DIMS:
                self._reserved[d] = max(0.0, self._reserved[d] - float(getattr(est, d)))

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "reserved": dict(self._reserved),
                "budget": self._budget.snapshot() if self._budget is not None else None,
            }


# ===========================================================================
# Execution wave (§5)
# ===========================================================================
@dataclass
class WaveTransition:
    from_status: str
    to_status: str
    reason: str = ""
    logical_seq: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {"from_status": self.from_status, "to_status": self.to_status,
                "reason": self.reason, "logical_seq": self.logical_seq}


@dataclass
class ExecutionWave:
    """One deterministic scheduling boundary's worth of goals.

    Contains only goals that are READY at the same boundary.  Membership and
    order are fixed at creation; the status transitions append-only through
    CREATED → RESERVED → RUNNING → JOINING → COMPLETED | FAILED | CANCELLED |
    BLOCKED.
    """

    wave_id: str
    workflow_id: str
    ordered_goal_ids: Tuple[str, ...]
    concurrency_limit: int
    created_logical_sequence: int
    failure_policy: str = FailurePolicy.ISOLATE_FAILURE
    status: str = WaveStatus.CREATED
    started_goal_ids: List[str] = field(default_factory=list)
    completed_goal_ids: List[str] = field(default_factory=list)
    failed_goal_ids: List[str] = field(default_factory=list)
    cancelled_goal_ids: List[str] = field(default_factory=list)
    blocked_goal_ids: List[str] = field(default_factory=list)
    review_goal_ids: List[str] = field(default_factory=list)
    result_order: List[str] = field(default_factory=list)
    history: List[WaveTransition] = field(default_factory=list)

    def transition(self, new_status: str, *, reason: str = "", logical_seq: int = 0) -> None:
        if new_status == self.status:
            return
        self.history.append(WaveTransition(self.status, new_status, reason, logical_seq))
        self.status = new_status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wave_id": self.wave_id,
            "workflow_id": self.workflow_id,
            "ordered_goal_ids": list(self.ordered_goal_ids),
            "concurrency_limit": self.concurrency_limit,
            "created_logical_sequence": self.created_logical_sequence,
            "failure_policy": self.failure_policy,
            "status": self.status,
            "started_goal_ids": list(self.started_goal_ids),
            "completed_goal_ids": list(self.completed_goal_ids),
            "failed_goal_ids": list(self.failed_goal_ids),
            "cancelled_goal_ids": list(self.cancelled_goal_ids),
            "blocked_goal_ids": list(self.blocked_goal_ids),
            "review_goal_ids": list(self.review_goal_ids),
            "result_order": list(self.result_order),
            "history": [t.to_dict() for t in self.history],
        }


# ===========================================================================
# Per-goal isolation: views, context, structured result (§13, §14, §16)
# ===========================================================================
class MemoryView:
    """An immutable read snapshot of working memory for one goal.

    Captures the ACTIVE value + version of the goal's declared read keys at
    dispatch time.  Workers read through this view (never the shared store);
    the recorded versions are the ``expected_version`` used by the joiner to
    detect concurrent-write conflicts (§16).
    """

    __slots__ = ("_values", "_versions")

    def __init__(self, values: Dict[str, Any], versions: Dict[str, int]) -> None:
        self._values = dict(values)
        self._versions = dict(versions)

    @classmethod
    def snapshot(cls, memory: WorkingMemory, keys: FrozenSet[str]) -> "MemoryView":
        values: Dict[str, Any] = {}
        versions: Dict[str, int] = {}
        for key in sorted(keys):
            rec = memory.peek(key)
            versions[key] = rec.version if rec is not None else 0
            if rec is not None:
                values[key] = rec.value
        return cls(values, versions)

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def version_of(self, key: str) -> int:
        return self._versions.get(key, 0)

    def to_working_memory(self) -> WorkingMemory:
        """A throwaway :class:`WorkingMemory` seeded with the snapshot values.

        Handed to legacy H16 :class:`WorkerExecutor` s so their reads resolve;
        any writes they make land here and are discarded (isolation).
        """
        wm = WorkingMemory()
        for key in sorted(self._values):
            wm.create(key, self._values[key], provenance="h21-snapshot")
        return wm

    def to_dict(self) -> Dict[str, Any]:
        return {"values": dict(self._values), "versions": dict(self._versions)}


class AssumptionView:
    """An immutable read snapshot of assumption states for one goal."""

    __slots__ = ("_states",)

    def __init__(self, states: Dict[str, str]) -> None:
        self._states = dict(states)

    @classmethod
    def snapshot(cls, assumption_context: Optional[Any], keys: FrozenSet[str]) -> "AssumptionView":
        states: Dict[str, str] = {}
        if assumption_context is not None:
            for aid in sorted(keys):
                a = assumption_context.registry.get(aid)
                if a is not None:
                    states[aid] = a.state
        return cls(states)

    def state_of(self, assumption_id: str) -> Optional[str]:
        return self._states.get(assumption_id)

    def to_dict(self) -> Dict[str, Any]:
        return {"states": dict(self._states)}


@dataclass(frozen=True)
class ParallelGoalContext:
    """The stable execution context a worker receives (§13).

    Immutable: workers never mutate shared joined state while executing — they
    return a structured :class:`GoalExecutionResult` instead.
    """

    goal: Goal
    workflow_id: str
    wave_id: str
    agent_id: Optional[str]
    reservation: BudgetReservation
    isolated_budget: Optional[RunBudget]
    memory_view: MemoryView
    assumption_view: AssumptionView
    cancellation_token: CancellationToken
    logical_seq: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_id": self.goal.goal_id,
            "workflow_id": self.workflow_id,
            "wave_id": self.wave_id,
            "agent_id": self.agent_id,
            "reservation": self.reservation.to_dict(),
            "memory_view": self.memory_view.to_dict(),
            "assumption_view": self.assumption_view.to_dict(),
            "cancelled": self.cancellation_token.is_cancelled,
            "logical_seq": self.logical_seq,
        }


@dataclass
class ProposedMemoryWrite:
    """A memory write a worker proposes; committed only by the joiner."""

    key: str
    value: Any
    category: str = "delegation"
    confidence: float = 1.0
    provenance: str = ""
    expected_version: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "confidence": self.confidence,
            "provenance": self.provenance,
            "expected_version": self.expected_version,
        }


@dataclass
class ProposedAssumptionTransition:
    """An assumption transition a worker proposes; verified by the joiner."""

    assumption_id: str
    to_state: str
    expected_prior_state: Optional[str] = None
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assumption_id": self.assumption_id,
            "to_state": self.to_state,
            "expected_prior_state": self.expected_prior_state,
            "reason": self.reason,
        }


@dataclass
class GoalExecutionResult:
    """Structured outcome a worker returns (§14).

    Never committed in thread-completion order — the joiner applies results in
    the wave's original stable goal order.
    """

    goal_id: str
    wave_id: str
    agent_id: Optional[str]
    outcome: str
    observations: Dict[str, Any] = field(default_factory=dict)
    proposed_memory_writes: List[ProposedMemoryWrite] = field(default_factory=list)
    proposed_assumption_transitions: List[ProposedAssumptionTransition] = field(default_factory=list)
    budget_usage: BudgetLedgerEntry = field(default_factory=BudgetLedgerEntry)
    produced_evidence: List[str] = field(default_factory=list)
    error: str = ""
    retry_recommendation: bool = False
    replan_recommendation: bool = False
    trace_events: List[Dict[str, Any]] = field(default_factory=list)
    result_digest: str = ""

    def payload(self) -> Dict[str, Any]:
        """Canonical, digest-covered content (excludes the digest)."""
        return {
            "goal_id": self.goal_id,
            "wave_id": self.wave_id,
            "agent_id": self.agent_id,
            "outcome": self.outcome,
            "observations": self.observations,
            "proposed_memory_writes": [w.to_dict() for w in self.proposed_memory_writes],
            "proposed_assumption_transitions": [t.to_dict() for t in self.proposed_assumption_transitions],
            "budget_usage": self.budget_usage.to_dict(),
            "produced_evidence": list(self.produced_evidence),
            "error": self.error,
            "retry_recommendation": self.retry_recommendation,
            "replan_recommendation": self.replan_recommendation,
        }

    def compute_digest(self) -> str:
        return digest_of(canonical_json(self.payload()))

    def with_digest(self) -> "GoalExecutionResult":
        self.result_digest = self.compute_digest()
        return self

    def to_dict(self) -> Dict[str, Any]:
        d = self.payload()
        d["result_digest"] = self.result_digest
        d["trace_events"] = list(self.trace_events)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GoalExecutionResult":
        r = cls(
            goal_id=d["goal_id"],
            wave_id=d["wave_id"],
            agent_id=d.get("agent_id"),
            outcome=d["outcome"],
            observations=dict(d.get("observations", {})),
            proposed_memory_writes=[
                ProposedMemoryWrite(**w) for w in d.get("proposed_memory_writes", [])
            ],
            proposed_assumption_transitions=[
                ProposedAssumptionTransition(**t) for t in d.get("proposed_assumption_transitions", [])
            ],
            budget_usage=BudgetLedgerEntry(**d.get("budget_usage", {})),
            produced_evidence=list(d.get("produced_evidence", [])),
            error=d.get("error", ""),
            retry_recommendation=d.get("retry_recommendation", False),
            replan_recommendation=d.get("replan_recommendation", False),
            trace_events=list(d.get("trace_events", [])),
            result_digest=d.get("result_digest", ""),
        )
        return r


# ===========================================================================
# Worker seam (§12) — reuses H16 authority + delegation contracts
# ===========================================================================
class ParallelWorker(Protocol):
    """Executes one goal into an isolated context and returns a result."""

    def run(self, context: ParallelGoalContext) -> GoalExecutionResult:
        ...


@dataclass
class DispatchUnit:
    """A context + the worker that will run it, ready for a backend."""

    goal_id: str
    context: ParallelGoalContext
    worker: ParallelWorker


class CoordinatedParallelWorker:
    """Reference :class:`ParallelWorker` that reuses the **unchanged** H16
    stack: capability registry, authority validation, and delegation
    contracts.

    It authorizes the assignment independently (so parallel execution never
    bypasses H16), then runs the selected agent's H16
    :class:`WorkerExecutor` against the goal's *isolated* memory snapshot and
    per-goal budget.  The executor's declared outputs become **proposed**
    memory writes — nothing is committed to shared state here.
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        authority: Optional[AuthorityModel] = None,
        ownership: Optional[GoalOwnershipLedger] = None,
    ) -> None:
        self.registry = registry
        self.authority = authority or AuthorityModel()
        # A dedicated ledger so ownership checks are meaningful under
        # concurrency without touching any H16 mission ledger.
        self.ownership = ownership or GoalOwnershipLedger(COORDINATOR_ID)
        self._lock = threading.Lock()

    def _coordination_goal(self, goal: Goal) -> CoordinationGoal:
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

    def run(self, context: ParallelGoalContext) -> GoalExecutionResult:
        goal = context.goal
        cg = self._coordination_goal(goal)
        result = GoalExecutionResult(
            goal_id=goal.goal_id, wave_id=context.wave_id, agent_id=None,
            outcome=GoalOutcome.FAILED,
        )

        # Observe cancellation at a safe point *before* doing any work.
        if context.cancellation_token.is_cancelled:
            result.outcome = GoalOutcome.CANCELLED
            result.error = context.cancellation_token.reason or "cancelled"
            return result.with_digest()

        # Independent H16 authorization across deterministically-ordered
        # candidates (mirrors the coordinator's per-goal recovery).
        candidates = self.registry.candidates_for(cg)
        if not candidates:
            result.error = "NO_QUALIFIED_AGENT"
            return result.with_digest()

        for profile in candidates:
            with self._lock:
                decision = self.authority.authorize(profile, cg, context.isolated_budget, self.ownership)
            if not decision.ok:
                result.error = decision.reason or "AUTHORITY_DENIED"
                continue

            contract = DelegationContract(
                contract_id=f"{goal.goal_id}->{profile.agent_id}",
                goal_id=goal.goal_id,
                goal_description=goal.description,
                assigned_agent=profile.agent_id,
                required_inputs=tuple(goal.required_memory),
                expected_outputs=tuple(cg.expected_outputs),
                required_memory=tuple(goal.required_memory),
                assumptions=tuple(goal.assumptions),
                authority_scope=goal.authority_scope,
                timeout=None,
                completion_criteria=goal.completion_criteria,
            )
            result.agent_id = profile.agent_id

            # Execute against the ISOLATED snapshot + per-goal budget.
            iso_memory = context.memory_view.to_working_memory()
            executor = self.registry.executor(profile.agent_id)
            try:
                worker_result: WorkerResult = executor.execute(
                    contract, iso_memory, context.isolated_budget
                )
            except BudgetExhausted as exc:
                result.outcome = GoalOutcome.BLOCKED
                result.error = f"BUDGET_EXHAUSTED:{exc.dimension}"
                result.retry_recommendation = True
                if context.isolated_budget is not None:
                    result.budget_usage = BudgetLedgerEntry.from_budget(context.isolated_budget)
                return result.with_digest()
            except WorkerUnavailable as exc:
                result.error = f"AGENT_UNAVAILABLE:{exc}"
                continue  # try the next qualified agent

            if context.isolated_budget is not None:
                result.budget_usage = BudgetLedgerEntry.from_budget(context.isolated_budget)

            if worker_result.timed_out:
                result.outcome = GoalOutcome.FAILED
                result.error = "DELEGATION_TIMEOUT"
                continue
            if not worker_result.success:
                result.outcome = GoalOutcome.FAILED
                result.error = worker_result.detail or "WORKER_FAILURE"
                continue

            # Success → declared outputs become PROPOSED writes (not committed).
            for key in contract.expected_outputs:
                if key in worker_result.outputs:
                    result.proposed_memory_writes.append(ProposedMemoryWrite(
                        key=key,
                        value=worker_result.outputs[key],
                        category="delegation",
                        provenance=profile.agent_id,
                        expected_version=context.memory_view.version_of(key),
                    ))
            result.observations = dict(worker_result.outputs)
            result.outcome = GoalOutcome.SUCCEEDED
            return result.with_digest()

        # No candidate succeeded.
        if result.outcome == GoalOutcome.FAILED and not result.error:
            result.error = "NO_QUALIFIED_AGENT"
        return result.with_digest()


class _FailurePolicyGuard:
    """Wraps a :class:`ParallelWorker` to enforce a wave failure policy (§19).

    ``FAIL_FAST`` cancels the shared token on the first failure, so not-yet-
    started goals observe cancellation at their safe point (and running goals
    are cooperatively signalled).  ``COMPLETE_IN_FLIGHT`` lets already-started
    goals finish but starts no new ones after a failure.  ``ISOLATE_FAILURE``
    / ``REPLAN_AFFECTED`` do not cancel siblings — the guard is a pass-through.
    """

    def __init__(self, inner: ParallelWorker, policy: str) -> None:
        self.inner = inner
        self.policy = policy
        self._failed = threading.Event()

    def run(self, context: ParallelGoalContext) -> GoalExecutionResult:
        token = context.cancellation_token
        stop_new = token.is_cancelled or (
            self.policy == FailurePolicy.COMPLETE_IN_FLIGHT and self._failed.is_set()
        )
        if self.policy in (FailurePolicy.FAIL_FAST, FailurePolicy.COMPLETE_IN_FLIGHT) and stop_new:
            res = GoalExecutionResult(
                goal_id=context.goal.goal_id, wave_id=context.wave_id, agent_id=None,
                outcome=GoalOutcome.CANCELLED, error="cancelled by wave failure policy",
            )
            return res.with_digest()
        res = self.inner.run(context)
        if res.outcome in (GoalOutcome.FAILED, GoalOutcome.BLOCKED):
            self._failed.set()
            if self.policy == FailurePolicy.FAIL_FAST:
                token.cancel(reason="FAIL_FAST wave failure policy")
        return res


# ===========================================================================
# Execution backends (§26)
# ===========================================================================
class ParallelExecutionBackend(Protocol):
    """Runs dispatch units, returning results keyed by goal id.

    The synchronous and concurrent backends MUST honour the same scheduling,
    result, and join contracts so the two are directly comparable (§27).
    """

    def execute(
        self,
        units: List[DispatchUnit],
        *,
        concurrency_limit: int,
        cancellation_token: CancellationToken,
    ) -> Dict[str, GoalExecutionResult]:
        ...


class SynchronousBackend:
    """Deterministic baseline: runs units one at a time in stable order."""

    def execute(self, units, *, concurrency_limit, cancellation_token) -> Dict[str, GoalExecutionResult]:
        results: Dict[str, GoalExecutionResult] = {}
        for unit in units:
            results[unit.goal_id] = unit.worker.run(unit.context)
        return results


class ThreadPoolBackend:
    """Bounded thread-pool backend.

    Runs at most ``concurrency_limit`` workers concurrently.  Completion order
    is nondeterministic, but results are keyed by goal id and the joiner
    applies them in the wave's stable order, so the committed state is
    identical to :class:`SynchronousBackend` for deterministic workers.
    """

    def execute(self, units, *, concurrency_limit, cancellation_token) -> Dict[str, GoalExecutionResult]:
        results: Dict[str, GoalExecutionResult] = {}
        if not units:
            return results
        workers = max(1, min(concurrency_limit, len(units)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(u.worker.run, u.context): u.goal_id for u in units}
            for fut, gid in futures.items():
                results[gid] = fut.result()
        return results


# ===========================================================================
# Trace (§25) — logical sequence numbers, never wall-clock
# ===========================================================================
@dataclass
class ParallelTraceEntry:
    seq: int
    event: str
    wave_id: str = ""
    goal_id: Optional[str] = None
    detail: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"seq": self.seq, "event": self.event, "wave_id": self.wave_id,
                "goal_id": self.goal_id, "detail": self.detail}


class ParallelExecutionTrace:
    """Append-only, logically-ordered trace of every parallel lifecycle action."""

    def __init__(self) -> None:
        self.entries: List[ParallelTraceEntry] = []
        self._seq = 0

    def record(self, event: str, *, wave_id: str = "", goal_id: Optional[str] = None,
               **detail: Any) -> ParallelTraceEntry:
        entry = ParallelTraceEntry(seq=self._seq, event=event, wave_id=wave_id,
                                   goal_id=goal_id, detail=dict(detail))
        self.entries.append(entry)
        self._seq += 1
        return entry

    @property
    def next_seq(self) -> int:
        return self._seq

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]


# ===========================================================================
# Deterministic ordering helpers
# ===========================================================================
def _goal_depth(tree: GoalTree, goal_id: str) -> int:
    d = 0
    cur = tree.lookup(goal_id).goal
    seen = set()
    while cur.parent is not None and tree.has(cur.parent) and cur.parent not in seen:
        seen.add(cur.parent)
        cur = tree.lookup(cur.parent).goal
        d += 1
    return d


def _order_key(tree: GoalTree, node: GoalNode) -> Tuple[int, int, str, str]:
    """Stable ordering: priority → depth → parent id → goal id (§7)."""
    g = node.goal
    return (g.priority, _goal_depth(tree, g.goal_id), g.parent or "", g.goal_id)


def _mem_version(memory: WorkingMemory, key: str) -> int:
    rec = memory.peek(key)
    return rec.version if rec is not None else 0


# ===========================================================================
# Review gate (§21) — H21-owned, wireable to H19
# ===========================================================================
class ReviewGate(Protocol):
    """Decides whether a goal must be held for human review and whether a
    held goal has since been cleared or rejected.

    A reference in-memory implementation is provided; production callers can
    back this onto H19's ``HumanPolicyEngine`` / ``ApprovalStore``.
    """

    def requires_review(self, goal: Goal) -> bool: ...
    def is_cleared(self, goal_id: str) -> bool: ...
    def rejection(self, goal_id: str) -> Optional[str]: ...


class StaticReviewGate:
    """Deterministic review gate driven by explicit sets (default: no review).

    ``review_required`` marks goals needing approval; ``cleared`` marks
    approved goals; ``rejected`` maps goal id → rejection reason.  Callers
    mutate the sets to model an operator approving/rejecting between waves.
    """

    def __init__(
        self,
        review_required: Optional[FrozenSet[str]] = None,
        cleared: Optional[set] = None,
        rejected: Optional[Dict[str, str]] = None,
    ) -> None:
        self.review_required = set(review_required or ())
        self.cleared = set(cleared or ())
        self.rejected = dict(rejected or {})

    def requires_review(self, goal: Goal) -> bool:
        return goal.goal_id in self.review_required

    def is_cleared(self, goal_id: str) -> bool:
        return goal_id in self.cleared

    def rejection(self, goal_id: str) -> Optional[str]:
        return self.rejected.get(goal_id)

    # convenience for callers/tests
    def approve(self, goal_id: str) -> None:
        self.cleared.add(goal_id)

    def reject(self, goal_id: str, reason: str = "rejected") -> None:
        self.rejected[goal_id] = reason


# ===========================================================================
# Parallel goal scheduler (§6, §7, §8)
# ===========================================================================
class ParallelGoalScheduler:
    """Builds a deterministic :class:`ExecutionWave` from the H15 goal tree.

    The scheduler inspects (never mutates policy owned by) H13/H15/H16/H19:
    it identifies READY leaves, excludes anything blocked / waiting /
    terminal / unauthorized / under-review, verifies pairwise footprint
    independence, applies deterministic ordering + concurrency limits, and
    emits an immutable wave.
    """

    def __init__(
        self,
        policy: ConcurrencyPolicy,
        footprints: Dict[str, GoalExecutionFootprint],
        *,
        assumption_context: Optional[Any] = None,
        review_gate: Optional[ReviewGate] = None,
        detector: Optional[FootprintConflictDetector] = None,
    ) -> None:
        self.policy = policy
        self.footprints = footprints
        self.assumption_context = assumption_context
        self.review_gate = review_gate
        self.detector = detector or FootprintConflictDetector(policy)

    def footprint_for(self, goal: Goal) -> GoalExecutionFootprint:
        return self.footprints.get(goal.goal_id) or footprint_from_goal(goal)

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

    def ready_leaves(self, tree: GoalTree) -> List[GoalNode]:
        """Deterministically ordered READY leaf goals (mirrors H15 semantics)."""
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
            ready.append(node)
        ready.sort(key=lambda n: _order_key(tree, n))
        return ready

    def build_wave(
        self,
        tree: GoalTree,
        *,
        workflow_id: str,
        wave_index: int,
        trace: ParallelExecutionTrace,
    ) -> Optional[ExecutionWave]:
        """Construct the next wave, or ``None`` when no runnable work remains.

        Review-gated goals are held (not selected) without blocking unrelated
        parallel-safe goals; their dependents remain blocked by the barrier.
        """
        ready = self.ready_leaves(tree)

        # Hold review-gated, uncleared goals; surface rejections as failures.
        selectable: List[GoalNode] = []
        held_for_review: List[str] = []
        rejected: List[Tuple[str, str]] = []
        if self.review_gate is not None:
            for node in ready:
                gid = node.goal.goal_id
                rej = self.review_gate.rejection(gid)
                if rej is not None:
                    rejected.append((gid, rej))
                    continue
                if self.review_gate.requires_review(node.goal) and not self.review_gate.is_cleared(gid):
                    held_for_review.append(gid)
                    continue
                selectable.append(node)
        else:
            selectable = ready

        if rejected:
            # A rejected review fails that goal (its subtree only, via barrier).
            for gid, reason in rejected:
                tree.lookup(gid).transition(GoalStatus.FAILED, reason=f"review rejected: {reason}")
            # Recompute readiness now that some goals failed.
            return self.build_wave(tree, workflow_id=workflow_id, wave_index=wave_index, trace=trace)

        # Mark held goals BLOCKED (a non-terminal hold), so they are surfaced
        # as review-held and re-evaluated once an operator clears them.
        for gid in held_for_review:
            node = tree.lookup(gid)
            if not (node.history and node.history[-1].reason == _REVIEW_REASON):
                node.transition(GoalStatus.BLOCKED, reason=_REVIEW_REASON)
            trace.record(ParallelEvent.GOAL_HELD_FOR_REVIEW, goal_id=gid)

        if not selectable:
            return None

        # Greedy deterministic selection under all caps + pairwise compatibility.
        # A wave may hold more goals than the concurrency limit; the backend
        # bounds how many run *simultaneously* to ``max_concurrent_goals``.
        limit = self.policy.max_concurrent_goals
        wave_cap = self.policy.max_wave_size
        selected: List[GoalNode] = []
        selected_fps: List[GoalExecutionFootprint] = []
        per_agent: Dict[str, int] = {}
        per_scope: Dict[str, int] = {}

        for node in selectable:
            if wave_cap is not None and len(selected) >= wave_cap:
                break
            fp = self.footprint_for(node.goal)

            # First pick may be anything; if it is not parallelizable it runs alone.
            if not selected:
                selected.append(node)
                selected_fps.append(fp)
                self._bump(per_agent, fp.assigned_agent)
                for s in fp.authority_scope:
                    self._bump(per_scope, s)
                if not self.detector.is_parallelizable(fp):
                    trace.record(ParallelEvent.GOAL_SERIALIZED, goal_id=node.goal.goal_id,
                                 reason=fp.concurrency)
                    break  # SERIAL_ONLY / UNKNOWN → wave of exactly one
                continue

            # Subsequent picks must be parallelizable and pairwise-compatible.
            if not self.detector.is_parallelizable(fp):
                continue
            if not self._caps_ok(fp, per_agent, per_scope):
                continue
            ok = True
            for other in selected_fps:
                compat, _reason = self.detector.compatible(fp, other)
                if not compat:
                    ok = False
                    break
            if not ok:
                continue
            selected.append(node)
            selected_fps.append(fp)
            self._bump(per_agent, fp.assigned_agent)
            for s in fp.authority_scope:
                self._bump(per_scope, s)

        ordered = tuple(n.goal.goal_id for n in selected)
        wave = ExecutionWave(
            wave_id=f"{workflow_id}::wave{wave_index}",
            workflow_id=workflow_id,
            ordered_goal_ids=ordered,
            concurrency_limit=limit,
            created_logical_sequence=trace.next_seq,
            failure_policy=self.policy.failure_policy,
        )
        wave.review_goal_ids = list(held_for_review)
        trace.record(ParallelEvent.WAVE_CREATED, wave_id=wave.wave_id,
                     goals=list(ordered), concurrency_limit=limit,
                     failure_policy=self.policy.failure_policy)
        for gid in ordered:
            trace.record(ParallelEvent.GOAL_SELECTED_FOR_WAVE, wave_id=wave.wave_id, goal_id=gid)
        return wave

    @staticmethod
    def _bump(counter: Dict[str, int], key: Optional[str]) -> None:
        if key:
            counter[key] = counter.get(key, 0) + 1

    def _caps_ok(self, fp: GoalExecutionFootprint, per_agent: Dict[str, int], per_scope: Dict[str, int]) -> bool:
        if self.policy.max_concurrent_per_agent is not None and fp.assigned_agent:
            if per_agent.get(fp.assigned_agent, 0) >= self.policy.max_concurrent_per_agent:
                return False
        if self.policy.max_concurrent_per_authority_scope is not None:
            for s in fp.authority_scope:
                if per_scope.get(s, 0) >= self.policy.max_concurrent_per_authority_scope:
                    return False
        return True


# ===========================================================================
# Deterministic join (§15, §16, §17, §18)
# ===========================================================================
@dataclass
class JoinReport:
    """Outcome of joining one wave's results."""

    wave_id: str
    committed: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)
    memory_conflicts: List[str] = field(default_factory=list)
    assumption_conflicts: List[str] = field(default_factory=list)
    replanned: List[str] = field(default_factory=list)
    review_held: List[str] = field(default_factory=list)
    cancelled: List[str] = field(default_factory=list)
    released: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "wave_id": self.wave_id,
            "committed": list(self.committed),
            "failed": list(self.failed),
            "memory_conflicts": list(self.memory_conflicts),
            "assumption_conflicts": list(self.assumption_conflicts),
            "replanned": list(self.replanned),
            "review_held": list(self.review_held),
            "cancelled": list(self.cancelled),
            "released": list(self.released),
        }


class DeterministicJoiner:
    """Applies wave results in the wave's original stable order, independent
    of worker-completion timing (§15).

    Guarantees: version-checked memory commits (no last-writer-wins),
    contradiction-checked assumption transitions (no timing winner),
    fail-closed conflict handling, budget reconciliation, and dependency
    barriers released only after a durable join.
    """

    def __init__(
        self,
        memory: WorkingMemory,
        *,
        assumption_context: Optional[Any] = None,
        budget_coordinator: Optional[SharedBudgetCoordinator] = None,
        conflict_policy: str = MemoryConflictPolicy.REJECT,
        subtree_replanner: Optional[Callable[[GoalTree, str], List[Goal]]] = None,
    ) -> None:
        self.memory = memory
        self.assumption_context = assumption_context
        self.budget_coordinator = budget_coordinator
        self.conflict_policy = conflict_policy
        self.subtree_replanner = subtree_replanner

    def join(
        self,
        wave: ExecutionWave,
        results: Dict[str, GoalExecutionResult],
        reservations: Dict[str, BudgetReservation],
        tree: GoalTree,
        *,
        trace: ParallelExecutionTrace,
        timestamp: float = 0.0,
    ) -> JoinReport:
        wave.transition(WaveStatus.JOINING, reason="join", logical_seq=trace.next_seq)
        report = JoinReport(wave_id=wave.wave_id)

        # ----- barrier: detect contradictory assumption transitions up front -----
        assumption_targets: Dict[str, set] = {}
        for gid in wave.ordered_goal_ids:
            res = results.get(gid)
            if res is None or res.outcome != GoalOutcome.SUCCEEDED:
                continue
            for tr in res.proposed_assumption_transitions:
                assumption_targets.setdefault(tr.assumption_id, set()).add(tr.to_state)
        contradictory = {aid for aid, states in assumption_targets.items() if len(states) > 1}
        for aid in sorted(contradictory):
            trace.record(ParallelEvent.ASSUMPTION_CONFLICT_DETECTED, wave_id=wave.wave_id,
                         assumption_id=aid, states=sorted(assumption_targets[aid]))
            report.assumption_conflicts.append(aid)

        # ----- apply results in the wave's stable order -----
        for gid in wave.ordered_goal_ids:
            res = results.get(gid)
            node = tree.lookup(gid)
            reservation = reservations.get(gid)

            # Reconcile budget for every dispatched goal (even failures spent).
            if self.budget_coordinator is not None and reservation is not None:
                self.budget_coordinator.reconcile(reservation, res.budget_usage if res else BudgetLedgerEntry())
                trace.record(ParallelEvent.BUDGET_RECONCILED, wave_id=wave.wave_id, goal_id=gid,
                             usage=(res.budget_usage.to_dict() if res else {}))

            if res is None:  # never produced a result (cancelled before start)
                node.transition(GoalStatus.BLOCKED, reason="no result (cancelled)", timestamp=timestamp)
                wave.cancelled_goal_ids.append(gid)
                report.cancelled.append(gid)
                continue

            # Integrity: the result must be self-consistent (fail-closed).
            if res.result_digest and res.result_digest != res.compute_digest():
                node.transition(GoalStatus.FAILED, reason="result digest mismatch", timestamp=timestamp)
                wave.failed_goal_ids.append(gid)
                report.failed.append(gid)
                continue

            if res.outcome == GoalOutcome.CANCELLED:
                node.transition(GoalStatus.BLOCKED, reason="cancelled", timestamp=timestamp)
                wave.cancelled_goal_ids.append(gid)
                report.cancelled.append(gid)
                trace.record(ParallelEvent.GOAL_CANCEL_REQUESTED, wave_id=wave.wave_id, goal_id=gid,
                             reason=res.error or "cancelled")
                continue

            if res.outcome == GoalOutcome.REQUIRES_REVIEW:
                node.transition(GoalStatus.BLOCKED, reason=_REVIEW_REASON, timestamp=timestamp)
                wave.review_goal_ids.append(gid)
                report.review_held.append(gid)
                continue

            if res.outcome in (GoalOutcome.FAILED, GoalOutcome.BLOCKED, GoalOutcome.WAITING):
                node.transition(GoalStatus.FAILED, reason=res.error or res.outcome, timestamp=timestamp)
                wave.failed_goal_ids.append(gid)
                report.failed.append(gid)
                self._maybe_replan(tree, gid, report)
                continue

            # ---- SUCCEEDED (or REQUIRES_REPLAN) ----
            if res.outcome == GoalOutcome.REQUIRES_REPLAN:
                node.transition(GoalStatus.FAILED, reason="requires replan", timestamp=timestamp)
                wave.failed_goal_ids.append(gid)
                report.failed.append(gid)
                self._maybe_replan(tree, gid, report)
                continue

            # If this goal touches an assumption under contradiction, do not
            # commit — block the smallest affected subtree and (optionally) replan.
            touches_conflict = any(
                tr.assumption_id in contradictory for tr in res.proposed_assumption_transitions
            )
            if touches_conflict:
                node.transition(GoalStatus.FAILED, reason="assumption transition conflict", timestamp=timestamp)
                wave.failed_goal_ids.append(gid)
                report.failed.append(gid)
                self._maybe_replan(tree, gid, report)
                continue

            # ---- versioned memory commit (no last-writer-wins) ----
            conflict_key = self._memory_conflict(res)
            if conflict_key is not None:
                trace.record(ParallelEvent.MEMORY_CONFLICT_DETECTED, wave_id=wave.wave_id,
                             goal_id=gid, key=conflict_key, policy=self.conflict_policy)
                report.memory_conflicts.append(gid)
                if self.conflict_policy in (MemoryConflictPolicy.REJECT, MemoryConflictPolicy.SERIALIZE_RETRY):
                    node.transition(GoalStatus.FAILED, reason=f"memory conflict on {conflict_key}",
                                    timestamp=timestamp)
                    wave.failed_goal_ids.append(gid)
                    report.failed.append(gid)
                    continue
                if self.conflict_policy == MemoryConflictPolicy.LOCALIZED_REPLAN:
                    node.transition(GoalStatus.FAILED, reason=f"memory conflict on {conflict_key}",
                                    timestamp=timestamp)
                    wave.failed_goal_ids.append(gid)
                    report.failed.append(gid)
                    self._maybe_replan(tree, gid, report)
                    continue
                # MERGE falls through to commit (explicit, configured strategy).

            # Commit memory writes deterministically.
            for w in res.proposed_memory_writes:
                self.memory.write(
                    w.key, w.value, category=w.category, confidence=w.confidence,
                    provenance=w.provenance or (res.agent_id or ""),
                    producing_step=res.agent_id, timestamp=timestamp,
                )
            # Apply assumption transitions (H13 public API), verifying prior state.
            self._apply_assumptions(res, timestamp)

            node.assigned_agent = res.agent_id
            node.transition(GoalStatus.COMPLETED, reason="worker completed", timestamp=timestamp)
            wave.completed_goal_ids.append(gid)
            wave.result_order.append(gid)
            report.committed.append(gid)
            trace.record(ParallelEvent.GOAL_RESULT_JOINED, wave_id=wave.wave_id, goal_id=gid,
                         memory_writes=[w.key for w in res.proposed_memory_writes])

        # ----- roll up parents; release dependents (barrier) -----
        _rollup(tree)
        report.released = self._released(tree)
        for gid in report.released:
            trace.record(ParallelEvent.DEPENDENCY_BARRIER_RELEASED, wave_id=wave.wave_id, goal_id=gid)

        if report.failed and not report.committed:
            wave.transition(WaveStatus.FAILED, reason="all goals failed", logical_seq=trace.next_seq)
            trace.record(ParallelEvent.WAVE_FAILED, wave_id=wave.wave_id)
        else:
            wave.transition(WaveStatus.COMPLETED, reason="joined", logical_seq=trace.next_seq)
            trace.record(ParallelEvent.WAVE_COMPLETED, wave_id=wave.wave_id,
                         committed=list(report.committed), failed=list(report.failed))
        return report

    # ----- helpers -----
    def _memory_conflict(self, res: GoalExecutionResult) -> Optional[str]:
        for w in res.proposed_memory_writes:
            if _mem_version(self.memory, w.key) != w.expected_version:
                return w.key
        return None

    def _apply_assumptions(self, res: GoalExecutionResult, timestamp: float) -> None:
        if self.assumption_context is None:
            return
        for tr in res.proposed_assumption_transitions:
            a = self.assumption_context.registry.get(tr.assumption_id)
            if a is None:
                continue
            if tr.expected_prior_state is not None and a.state != tr.expected_prior_state:
                continue  # prior-state mismatch → skip (fail-closed, no silent overwrite)
            a.transition(tr.to_state, reason=tr.reason or "h21 join", timestamp=timestamp)

    def _maybe_replan(self, tree: GoalTree, goal_id: str, report: JoinReport) -> None:
        if self.subtree_replanner is None:
            return
        new_goals = list(self.subtree_replanner(tree, goal_id))
        if new_goals:
            tree.replace_leaf(goal_id, new_goals)
            report.replanned.append(goal_id)

    @staticmethod
    def _released(tree: GoalTree) -> List[str]:
        completed = {n.goal.goal_id for n in tree.nodes() if n.status == GoalStatus.COMPLETED}
        failed = {n.goal.goal_id for n in tree.nodes() if n.status in _FAILED}
        out: List[str] = []
        for node in tree.leaves():
            if node.status in _TERMINAL or node.status == GoalStatus.EXECUTING:
                continue
            deps = node.goal.dependencies
            if any(d in failed for d in deps):
                continue
            if all(d in completed for d in deps):
                out.append(node.goal.goal_id)
        return out


def _rollup(tree: GoalTree) -> None:
    """Roll internal-goal status up from children (mirrors H15 roll-up)."""
    for node in sorted(tree.nodes(), key=lambda n: -len(tree.subtree(n.goal.goal_id))):
        g = node.goal
        if g.is_leaf or node.status in _TERMINAL:
            continue
        children = tree.children_of(g.goal_id)
        mandatory = [c for c in children if c.goal.mandatory and c.status != GoalStatus.ABORTED]
        if mandatory and all(c.status == GoalStatus.COMPLETED for c in mandatory):
            node.transition(GoalStatus.COMPLETED, reason="all children completed")
        elif any(c.status in _FAILED for c in mandatory):
            node.transition(GoalStatus.FAILED, reason="mandatory child failed")


# ===========================================================================
# Durability & recovery (§23, §24) — composes H18 public helpers
# ===========================================================================
@dataclass
class WaveCheckpoint:
    """A durable snapshot of in-flight parallel state (§23).

    Serialised with H18's public ``canonical_json`` / ``digest_of`` and stored
    with a fail-closed integrity digest, so recovery never trusts a corrupt or
    tampered snapshot and never re-executes already-joined work.
    """

    checkpoint_id: str
    workflow_id: str
    logical_sequence: int
    wave: Dict[str, Any]
    concurrency_policy: Dict[str, Any]
    reservations: Dict[str, Any]
    dispatched_goal_ids: List[str]
    results_not_joined: Dict[str, Any]
    joined_goal_ids: List[str]
    memory_versions: Dict[str, int]
    assumption_versions: Dict[str, str]
    cancellation: Dict[str, Any]
    trace: List[Dict[str, Any]]
    integrity_digest: str = ""

    def payload(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_id": self.workflow_id,
            "logical_sequence": self.logical_sequence,
            "wave": self.wave,
            "concurrency_policy": self.concurrency_policy,
            "reservations": self.reservations,
            "dispatched_goal_ids": list(self.dispatched_goal_ids),
            "results_not_joined": self.results_not_joined,
            "joined_goal_ids": list(self.joined_goal_ids),
            "memory_versions": self.memory_versions,
            "assumption_versions": self.assumption_versions,
            "cancellation": self.cancellation,
            "trace": self.trace,
        }

    def compute_digest(self) -> str:
        return digest_of(canonical_json(self.payload()))

    def with_digest(self) -> "WaveCheckpoint":
        self.integrity_digest = self.compute_digest()
        return self

    def to_dict(self) -> Dict[str, Any]:
        d = self.payload()
        d["integrity_digest"] = self.integrity_digest
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WaveCheckpoint":
        return cls(
            checkpoint_id=d["checkpoint_id"],
            workflow_id=d["workflow_id"],
            logical_sequence=d["logical_sequence"],
            wave=d["wave"],
            concurrency_policy=d["concurrency_policy"],
            reservations=d["reservations"],
            dispatched_goal_ids=list(d["dispatched_goal_ids"]),
            results_not_joined=d["results_not_joined"],
            joined_goal_ids=list(d["joined_goal_ids"]),
            memory_versions=d["memory_versions"],
            assumption_versions=d["assumption_versions"],
            cancellation=d["cancellation"],
            trace=d["trace"],
            integrity_digest=d.get("integrity_digest", ""),
        )

    def validate(self) -> None:
        """Fail-closed integrity check (mirrors H18's posture)."""
        if not self.integrity_digest:
            raise RecoveryError(RecoveryError.CHECKPOINT_CORRUPT, "missing integrity digest")
        if self.integrity_digest != self.compute_digest():
            raise RecoveryError(RecoveryError.CHECKPOINT_CORRUPT, "integrity digest mismatch")
        if self.logical_sequence < 0:
            raise RecoveryError(RecoveryError.CHECKPOINT_INVARIANT_VIOLATION, "negative logical sequence")


class InMemoryWaveStore:
    """Append-only, optimistic-concurrency store for :class:`WaveCheckpoint` s.

    Mirrors H18's fail-closed store contract: ``compare_and_save`` raises
    :class:`CheckpointConflict` on a stale write, making duplicate recovery
    attempts idempotent (§24 test 21).
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, WaveCheckpoint] = {}
        self._latest: Dict[str, str] = {}

    def save(self, checkpoint: WaveCheckpoint) -> None:
        cp = checkpoint if checkpoint.integrity_digest else checkpoint.with_digest()
        cp.validate()
        self._by_id[cp.checkpoint_id] = cp
        self._latest[cp.workflow_id] = cp.checkpoint_id

    def compare_and_save(self, checkpoint: WaveCheckpoint, *, expected_latest_id: Optional[str]) -> None:
        current = self._latest.get(checkpoint.workflow_id)
        if current != expected_latest_id:
            raise CheckpointConflict(
                f"expected latest {expected_latest_id!r}, found {current!r}"
            )
        self.save(checkpoint)

    def load(self, checkpoint_id: str) -> WaveCheckpoint:
        cp = self._by_id[checkpoint_id]
        cp.validate()
        return cp

    def load_latest(self, workflow_id: str) -> Optional[WaveCheckpoint]:
        cid = self._latest.get(workflow_id)
        return self.load(cid) if cid else None

    def latest_id(self, workflow_id: str) -> Optional[str]:
        return self._latest.get(workflow_id)


class WaveRecoveryPlanner:
    """Classifies dispatched goals after process loss and plans recovery (§24).

    Fail-closed: ``STARTED_NO_RESULT`` goals are never auto-replayed unless the
    policy allows deterministic replay AND the goal is PURE/DETERMINISTIC.
    ``RESULT_AVAILABLE_NOT_JOINED`` results are joined without re-execution;
    ``JOINED`` goals are never re-executed.
    """

    def __init__(self, policy: ConcurrencyPolicy, footprints: Dict[str, GoalExecutionFootprint]) -> None:
        self.policy = policy
        self.footprints = footprints

    def classify(self, checkpoint: WaveCheckpoint) -> Dict[str, str]:
        checkpoint.validate()
        joined = set(checkpoint.joined_goal_ids)
        have_result = set(checkpoint.results_not_joined)
        dispatched = list(checkpoint.dispatched_goal_ids)
        ordered = list(checkpoint.wave.get("ordered_goal_ids", []))
        out: Dict[str, str] = {}
        for gid in ordered:
            if gid in joined:
                out[gid] = InFlightStatus.JOINED
            elif gid in have_result:
                out[gid] = InFlightStatus.RESULT_AVAILABLE_NOT_JOINED
            elif gid in dispatched:
                out[gid] = InFlightStatus.STARTED_NO_RESULT
            else:
                out[gid] = InFlightStatus.NOT_STARTED
        return out

    def may_replay(self, goal_id: str) -> bool:
        if not self.policy.allow_deterministic_replay:
            return False
        fp = self.footprints.get(goal_id)
        if fp is None:
            return False
        return fp.side_effect_class in (SideEffectClass.PURE, SideEffectClass.DETERMINISTIC)


# ===========================================================================
# Top-level parallel executor (§22, §27)
# ===========================================================================
class ParallelHierarchyStatus:
    MISSION_COMPLETED = "MISSION_COMPLETED"
    MISSION_FAILED = "MISSION_FAILED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    WAITING_FOR_REVIEW = "WAITING_FOR_REVIEW"


@dataclass
class ParallelHierarchyResult:
    workflow_id: str
    mission_id: str
    status: str
    tree: GoalTree
    waves: List[ExecutionWave] = field(default_factory=list)
    join_reports: List[JoinReport] = field(default_factory=list)
    completed_goals: List[str] = field(default_factory=list)
    failed_goals: List[str] = field(default_factory=list)
    review_goals: List[str] = field(default_factory=list)
    trace: Optional[ParallelExecutionTrace] = None
    run_budget: Optional[RunBudget] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "mission_id": self.mission_id,
            "status": self.status,
            "completed_goals": list(self.completed_goals),
            "failed_goals": list(self.failed_goals),
            "review_goals": list(self.review_goals),
            "tree": self.tree.to_dict(),
            "waves": [w.to_dict() for w in self.waves],
            "join_reports": [r.to_dict() for r in self.join_reports],
            "trace": self.trace.to_list() if self.trace else [],
            "run_budget": self.run_budget.snapshot() if self.run_budget is not None else None,
        }


def derive_execution_state(
    tree: GoalTree,
    *,
    review_held: Optional[FrozenSet[str]] = None,
) -> Dict[str, List[str]]:
    """H21-owned derived execution-state view over a goal tree (§22).

    Reports goals by branch state without mutating any H17 ``WorkflowInstance``
    — so a workflow with one branch waiting for review and another still
    executable is represented directly, instead of being forced globally into
    WAITING.
    """
    review_held = review_held or frozenset()
    view: Dict[str, List[str]] = {
        "running": [], "ready": [], "blocked": [], "waiting_review": [],
        "completed": [], "failed": [],
    }
    for node in tree.nodes():
        gid = node.goal.goal_id
        if gid in review_held:
            view["waiting_review"].append(gid)
        elif node.status == GoalStatus.EXECUTING:
            view["running"].append(gid)
        elif node.status == GoalStatus.READY:
            view["ready"].append(gid)
        elif node.status == GoalStatus.BLOCKED:
            view["blocked"].append(gid)
        elif node.status == GoalStatus.COMPLETED:
            view["completed"].append(gid)
        elif node.status in _FAILED:
            view["failed"].append(gid)
    for key in view:
        view[key].sort()
    return view


class ParallelHierarchyExecutor:
    """Executes a :class:`MissionPlan` with bounded deterministic parallelism.

    The parallel analogue of H15's ``HierarchyExecutor``: it schedules waves of
    proven-independent READY goals, reserves the shared budget, dispatches
    governed workers through a pluggable :class:`ParallelExecutionBackend`, and
    commits results through the :class:`DeterministicJoiner`.  Swapping the
    backend between :class:`SynchronousBackend` and :class:`ThreadPoolBackend`
    yields identical committed state for deterministic workers (§27).
    """

    def __init__(
        self,
        registry: CapabilityRegistry,
        memory: WorkingMemory,
        *,
        run_budget: Optional[RunBudget] = None,
        authority: Optional[AuthorityModel] = None,
        assumption_context: Optional[Any] = None,
        subtree_replanner: Optional[Callable[[GoalTree, str], List[Goal]]] = None,
        concurrency_policy: Optional[ConcurrencyPolicy] = None,
        footprints: Optional[Dict[str, GoalExecutionFootprint]] = None,
        estimates: Optional[Dict[str, BudgetEstimate]] = None,
        default_estimate: Optional[BudgetEstimate] = None,
        backend: Optional[ParallelExecutionBackend] = None,
        review_gate: Optional[ReviewGate] = None,
        worker: Optional[ParallelWorker] = None,
        checkpoint_store: Optional[InMemoryWaveStore] = None,
        workflow_id: str = "wf",
        max_waves: int = 128,
    ) -> None:
        self.registry = registry
        self.memory = memory
        self.run_budget = run_budget
        self.authority = authority or AuthorityModel()
        self.assumption_context = assumption_context
        self.subtree_replanner = subtree_replanner
        self.policy = concurrency_policy or ConcurrencyPolicy()
        self.footprints = footprints or {}
        self.estimates = estimates or {}
        self.default_estimate = default_estimate or BudgetEstimate()
        self.backend = backend or SynchronousBackend()
        self.review_gate = review_gate
        self.worker = worker or CoordinatedParallelWorker(registry, authority=self.authority)
        self.checkpoint_store = checkpoint_store
        self.workflow_id = workflow_id
        self.max_waves = max_waves

        self.budget_coordinator = SharedBudgetCoordinator(run_budget)
        self.scheduler = ParallelGoalScheduler(
            self.policy, self.footprints,
            assumption_context=assumption_context, review_gate=review_gate,
        )
        self.joiner = DeterministicJoiner(
            memory, assumption_context=assumption_context,
            budget_coordinator=self.budget_coordinator,
            conflict_policy=self.policy.memory_conflict_policy,
            subtree_replanner=subtree_replanner,
        )

    def estimate_for(self, goal: Goal) -> BudgetEstimate:
        return self.estimates.get(goal.goal_id, self.default_estimate)

    def run(self, plan: MissionPlan) -> ParallelHierarchyResult:
        tree = plan.tree
        tree.validate_acyclic()
        trace = ParallelExecutionTrace()
        result = ParallelHierarchyResult(
            workflow_id=self.workflow_id, mission_id=plan.mission_id,
            status=ParallelHierarchyStatus.MISSION_COMPLETED, tree=tree,
            trace=trace, run_budget=self.run_budget,
        )
        if self.run_budget is not None:
            self.run_budget.start()

        last_ckpt_id: Optional[str] = None
        for wave_index in range(self.max_waves):
            if self.run_budget is not None and self.run_budget.is_exhausted():
                result.status = ParallelHierarchyStatus.BUDGET_EXHAUSTED
                break

            wave = self.scheduler.build_wave(
                tree, workflow_id=self.workflow_id, wave_index=wave_index, trace=trace,
            )
            if wave is None:
                break

            # ----- reserve the shared budget (all-or-nothing) -----
            estimates = {gid: self.estimate_for(tree.lookup(gid).goal) for gid in wave.ordered_goal_ids}
            ok, reservations = self.budget_coordinator.reserve_wave(estimates)
            reservation_by_goal = {r.goal_id: r for r in reservations}
            if not ok:
                for r in reservations:
                    if r.ok:
                        trace.record(ParallelEvent.BUDGET_RESERVED, wave_id=wave.wave_id, goal_id=r.goal_id)
                    else:
                        trace.record(ParallelEvent.BUDGET_DENIED, wave_id=wave.wave_id, goal_id=r.goal_id,
                                     reason=r.reason, dimension=r.dimension)
                # reserve_wave already rolled back any tentative reservations.
                wave.transition(WaveStatus.BLOCKED, reason="insufficient budget", logical_seq=trace.next_seq)
                result.waves.append(wave)
                result.status = ParallelHierarchyStatus.BUDGET_EXHAUSTED
                break
            wave.transition(WaveStatus.RESERVED, reason="budget reserved", logical_seq=trace.next_seq)
            for gid in wave.ordered_goal_ids:
                trace.record(ParallelEvent.BUDGET_RESERVED, wave_id=wave.wave_id, goal_id=gid)

            # ----- mark EXECUTING + build dispatch units -----
            wave.transition(WaveStatus.RUNNING, reason="dispatch", logical_seq=trace.next_seq)
            token = CancellationToken()
            worker = self.worker
            if self.policy.failure_policy in (FailurePolicy.FAIL_FAST, FailurePolicy.COMPLETE_IN_FLIGHT):
                worker = _FailurePolicyGuard(self.worker, self.policy.failure_policy)
            units: List[DispatchUnit] = []
            for gid in wave.ordered_goal_ids:
                node = tree.lookup(gid)
                node.transition(GoalStatus.EXECUTING, reason="delegated (parallel)", timestamp=float(wave_index))
                wave.started_goal_ids.append(gid)
                context = self._context_for(node.goal, wave, reservation_by_goal[gid], token, trace)
                units.append(DispatchUnit(goal_id=gid, context=context, worker=worker))
                trace.record(ParallelEvent.GOAL_DISPATCHED, wave_id=wave.wave_id, goal_id=gid,
                             agent=context.agent_id)

            # ----- execute (bounded) -----
            results = self.backend.execute(
                units, concurrency_limit=self.policy.max_concurrent_goals, cancellation_token=token,
            )
            for gid in wave.ordered_goal_ids:
                res = results.get(gid)
                if res is not None:
                    trace.record(ParallelEvent.GOAL_RESULT_PRODUCED, wave_id=wave.wave_id, goal_id=gid,
                                 outcome=res.outcome, digest=res.result_digest)

            # ----- checkpoint results-before-join (recovery point) -----
            if self.checkpoint_store is not None:
                ckpt = self._checkpoint(wave, results, reservation_by_goal, trace,
                                        joined=[], stage="results_produced")
                self.checkpoint_store.compare_and_save(ckpt, expected_latest_id=last_ckpt_id)
                last_ckpt_id = ckpt.checkpoint_id

            # ----- deterministic join -----
            report = self.joiner.join(
                wave, results, reservation_by_goal, tree, trace=trace, timestamp=float(wave_index),
            )
            result.waves.append(wave)
            result.join_reports.append(report)

            # ----- checkpoint post-join (durable barrier) -----
            if self.checkpoint_store is not None:
                ckpt = self._checkpoint(wave, results, reservation_by_goal, trace,
                                        joined=list(report.committed), stage="joined")
                self.checkpoint_store.compare_and_save(ckpt, expected_latest_id=last_ckpt_id)
                last_ckpt_id = ckpt.checkpoint_id

        # ----- finalize -----
        _rollup(tree)
        result.completed_goals = sorted(n.goal.goal_id for n in tree.nodes() if n.status == GoalStatus.COMPLETED)
        result.failed_goals = sorted(n.goal.goal_id for n in tree.nodes() if n.status in _FAILED)
        result.review_goals = sorted(
            n.goal.goal_id for n in tree.nodes()
            if n.status == GoalStatus.BLOCKED
            and n.history and n.history[-1].reason == _REVIEW_REASON
        )
        if self.run_budget is not None and not self.run_budget.is_exhausted():
            self.run_budget.complete()

        if result.status not in (ParallelHierarchyStatus.BUDGET_EXHAUSTED,):
            mandatory_leaves = [n for n in tree.leaves()
                                if n.goal.mandatory and n.status != GoalStatus.ABORTED]
            if all(n.status == GoalStatus.COMPLETED for n in mandatory_leaves):
                result.status = ParallelHierarchyStatus.MISSION_COMPLETED
            elif result.review_goals and not result.failed_goals:
                result.status = ParallelHierarchyStatus.WAITING_FOR_REVIEW
            else:
                result.status = ParallelHierarchyStatus.MISSION_FAILED
        return result

    # ----- helpers -----
    def _context_for(
        self,
        goal: Goal,
        wave: ExecutionWave,
        reservation: BudgetReservation,
        token: CancellationToken,
        trace: ParallelExecutionTrace,
    ) -> ParallelGoalContext:
        fp = self.scheduler.footprint_for(goal)
        mem_view = MemoryView.snapshot(self.memory, fp.read_memory_keys)
        assumption_view = AssumptionView.snapshot(self.assumption_context, fp.assumption_reads)
        iso_budget = None
        if self.run_budget is not None and reservation.ok:
            iso_budget = self.budget_coordinator.isolated_budget(reservation.estimate)
        return ParallelGoalContext(
            goal=goal, workflow_id=self.workflow_id, wave_id=wave.wave_id, agent_id=None,
            reservation=reservation, isolated_budget=iso_budget,
            memory_view=mem_view, assumption_view=assumption_view,
            cancellation_token=token, logical_seq=trace.next_seq,
        )

    def _checkpoint(
        self,
        wave: ExecutionWave,
        results: Dict[str, GoalExecutionResult],
        reservations: Dict[str, BudgetReservation],
        trace: ParallelExecutionTrace,
        *,
        joined: List[str],
        stage: str,
    ) -> WaveCheckpoint:
        mem_versions = {k: _mem_version(self.memory, k) for k in sorted(self.memory.keys())}
        assumption_versions: Dict[str, str] = {}
        if self.assumption_context is not None:
            for a in self.assumption_context.registry.all():
                assumption_versions[a.assumption_id] = a.state
        ckpt = WaveCheckpoint(
            checkpoint_id=f"{wave.wave_id}::{stage}",
            workflow_id=self.workflow_id,
            logical_sequence=trace.next_seq,
            wave=wave.to_dict(),
            concurrency_policy=self.policy.to_dict(),
            reservations={gid: r.to_dict() for gid, r in reservations.items()},
            dispatched_goal_ids=list(wave.started_goal_ids),
            results_not_joined={gid: results[gid].to_dict() for gid in results if gid not in joined},
            joined_goal_ids=list(joined),
            memory_versions=mem_versions,
            assumption_versions=assumption_versions,
            cancellation={"cancelled": False, "reason": None},
            trace=trace.to_list(),
        )
        return ckpt.with_digest()


# ===========================================================================
# Rendering
# ===========================================================================
def format_execution_wave(wave: ExecutionWave) -> str:
    lines = [
        f"ExecutionWave {wave.wave_id}  [{wave.status}]  policy={wave.failure_policy}",
        f"  goals (ordered): {list(wave.ordered_goal_ids)}  limit={wave.concurrency_limit}",
        f"  completed={wave.completed_goal_ids}  failed={wave.failed_goal_ids}",
    ]
    if wave.cancelled_goal_ids:
        lines.append(f"  cancelled={wave.cancelled_goal_ids}")
    if wave.review_goal_ids:
        lines.append(f"  review-held={wave.review_goal_ids}")
    if wave.result_order:
        lines.append(f"  commit order={wave.result_order}")
    return "\n".join(lines)


def format_parallel_trace(result: ParallelHierarchyResult) -> str:
    lines = [
        f"Parallel hierarchy: {result.mission_id} (workflow {result.workflow_id})",
        f"status={result.status}  completed={result.completed_goals}  failed={result.failed_goals}",
        "=" * 64,
    ]
    if result.trace is None:
        return "\n".join(lines)
    for e in result.trace.entries:
        loc = f" goal={e.goal_id}" if e.goal_id else ""
        lines.append(f"  {e.seq:>3} {e.event:<28}{loc}")
    return "\n".join(lines)
