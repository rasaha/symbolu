"""H22-D — the bounded concurrent portfolio executor (admission coordinator).

This is the top of the H22 stack. Where H22-B answers *which eligible workflow gets the next
quantum* and H22-C makes that coordination durable, H22-D answers:

    Which already-eligible workflows may receive **simultaneous** bounded execution grants
    without conflicting with each other or exceeding shared limits?

It never answers *whether the consequential action inside a workflow is authorized* — governance
stays entirely below H22, inside the unchanged ``advance_workflow`` quantum. The three questions
stay separate: scheduling eligibility (H22-B) → concurrent admission (H22-D) → action
authorization (external governance, below H22-A).

## Model

**Bounded in-process concurrency over independent H22-A workflow quanta.** Not logical
interleaving alone, not distributed cluster scheduling — real threads, capped at
``max_concurrent_quanta``, each running exactly one indivisible H22-A quantum for a *distinct*
workflow. The concurrency unit is ``advance_workflow(instance_id)``; no internal state-machine
phase is ever interleaved, and a workflow never has two quanta in flight at once.

## The barrier discipline

Every round is: **plan → execute → join → reconcile → checkpoint**.

1. *Plan* (single coordinator thread): run the deterministic H22-B batch selection with an
   admission predicate that atomically reserves resources + shared budget. Admission is fully
   deterministic — thread completion timing can never change who was admitted.
2. *Execute*: launch each admitted workflow's H22-A quantum on the execution backend
   (synchronous or bounded thread pool — proven equivalent).
3. *Join*: wait for every admitted quantum to reach its stable, checkpointed boundary. There is
   **no** mid-quantum portfolio checkpoint.
4. *Reconcile* (single coordinator thread, in deterministic admission order): release resources,
   settle/release budget, observe failures via the H22-C controller, coordinate compensation.
5. *Checkpoint* (optional, at the stable boundary only): resources/budget reservations are empty
   here, so the durable checkpoint carries no in-flight state and H22-C's
   ``PORTFOLIO_RUNTIME_CHECKPOINT_DIVERGENCE`` fail-closed contract is preserved untouched.

Workers are narrow: a worker only calls ``advance_workflow`` for one distinct instance and
returns an immutable outcome. Only the coordinator thread mutates portfolio / scheduler /
resource / budget / trace / checkpoint state, so no lock is needed around those aggregates.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, Iterable, List, Optional, Protocol, Tuple

from ..models.results import WorkflowAdvanceOutcome
from .budgets import BudgetCoordinator, BudgetRequirement, PortfolioBudget
from .compensation import CompensationRegistry
from .control import PortfolioController, PortfolioFailurePolicy
from .portfolio import WorkflowPortfolio
from .resources import ResourceClaim, ResourceCoordinator
from .scheduling import (
    AdmissionDecision,
    BatchPlan,
    PortfolioScheduler,
    PortfolioStepReason,
    SchedulingPolicy,
    SelectionReason,
)
from .tracing import PortfolioEventType, PortfolioTrace


# --------------------------------------------------------------------------- #
# Policy                                                                        #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ConcurrencyPolicy:
    """The small, typed knobs for bounded concurrent admission. Pure data; no authority.

    ``max_concurrent_quanta`` is the hard ceiling on how many H22-A quanta may be in flight at
    once — a positive integer, never derived from CPU count (hardware is not a hidden authority).
    ``resource_conflict_policy`` is ``DEFER`` (the only mode): a resource-conflicted candidate is
    deferred to a later round, never run concurrently. Executor implementation details (the thread
    pool class, worker counts) are deliberately NOT part of the policy surface."""

    max_concurrent_quanta: int = 4
    resource_conflict_policy: str = "DEFER"

    def __post_init__(self) -> None:
        if (
            not isinstance(self.max_concurrent_quanta, int)
            or isinstance(self.max_concurrent_quanta, bool)
            or self.max_concurrent_quanta < 1
        ):
            raise ValueError("max_concurrent_quanta must be a positive integer")
        if self.resource_conflict_policy != "DEFER":
            raise ValueError("resource_conflict_policy must be 'DEFER' (the only supported mode)")

    def to_dict(self) -> Dict[str, object]:
        return {
            "max_concurrent_quanta": self.max_concurrent_quanta,
            "resource_conflict_policy": self.resource_conflict_policy,
        }


class ConcurrentStepReason(str, Enum):
    """Why one concurrent round ended — a deterministic, bounded stop reason."""

    #: A non-empty batch of quanta was admitted and executed this round.
    BATCH_EXECUTED = "BATCH_EXECUTED"
    #: Eligible work exists, but every eligible candidate was resource/budget deferred — the
    #: portfolio is *concurrently quiescent* this round (not complete). No busy loop.
    NO_CONCURRENTLY_ADMISSIBLE_WORKFLOW = "NO_CONCURRENTLY_ADMISSIBLE_WORKFLOW"
    #: No workflow is eligible this round (all WAITING/PAUSED/dependency-blocked).
    NO_ELIGIBLE_WORKFLOW = "NO_ELIGIBLE_WORKFLOW"
    #: Every registered workflow is terminal — the portfolio is complete.
    ALL_TERMINAL = "ALL_TERMINAL"
    #: The portfolio has no registrations.
    EMPTY_PORTFOLIO = "EMPTY_PORTFOLIO"
    #: The portfolio is in a terminal orchestration state (FAILED / CANCELLED) — no quantum granted.
    PORTFOLIO_TERMINAL = "PORTFOLIO_TERMINAL"


# --------------------------------------------------------------------------- #
# Immutable results                                                             #
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class QuantumOutcome:
    """The immutable outcome of one admitted concurrent quantum, reconciled by the coordinator.

    Identity (``batch_id`` / ``admission_sequence`` / ``instance_id``) is assigned deterministically
    **before** launch, so it never depends on completion timing. ``advance_outcome`` is the frozen
    H22-A result (which references runtime state by digest only); ``error`` is set only for an H22-D
    *infrastructure* failure (a worker/executor fault) — never confused with a workflow provider
    failure, which is a normal ``advance_outcome`` with ``status_after == FAILED``. No thread or
    future handle is ever exposed."""

    instance_id: str
    batch_id: str
    admission_sequence: int
    advance_outcome: Optional[WorkflowAdvanceOutcome] = None
    error: Optional[str] = None
    budget_settlement: Optional[Dict[str, object]] = None
    resource_released: bool = False

    @property
    def infrastructure_failure(self) -> bool:
        return self.error is not None

    def to_dict(self) -> Dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "batch_id": self.batch_id,
            "admission_sequence": self.admission_sequence,
            "advance_outcome": self.advance_outcome.to_dict() if self.advance_outcome else None,
            "error": self.error,
            "budget_settlement": self.budget_settlement,
            "resource_released": self.resource_released,
        }


@dataclass(frozen=True)
class ConcurrentPortfolioStepResult:
    """The immutable, read-only outcome of one concurrent scheduling round (Section 22).

    Exposes selection/admission reasons for inspection and NO thread/future objects.
    ``admitted`` is the deterministic admission order; ``deferred_resource`` / ``deferred_budget``
    carry structured deferral evidence; ``deferred_capacity`` are eligible workflows the
    concurrency limit kept out; ``outcomes`` are the per-quantum reconciled results in admission
    order (completion order is intentionally not treated as authoritative)."""

    portfolio_id: str
    round: int
    batch_id: str
    reason: str
    candidates: Tuple[str, ...] = ()
    admitted: Tuple[str, ...] = ()
    admitted_reasons: Dict[str, SelectionReason] = field(default_factory=dict)
    deferred_resource: Tuple[Dict[str, object], ...] = ()
    deferred_budget: Tuple[Dict[str, object], ...] = ()
    deferred_capacity: Tuple[str, ...] = ()
    outcomes: Tuple[QuantumOutcome, ...] = ()
    classifications: Tuple[Tuple[str, str], ...] = ()

    @property
    def granted(self) -> bool:
        return self.reason == ConcurrentStepReason.BATCH_EXECUTED.value

    def to_dict(self) -> Dict[str, object]:
        return {
            "portfolio_id": self.portfolio_id,
            "round": self.round,
            "batch_id": self.batch_id,
            "reason": self.reason,
            "candidates": list(self.candidates),
            "admitted": list(self.admitted),
            "admitted_reasons": {k: v.to_dict() for k, v in self.admitted_reasons.items()},
            "deferred_resource": list(self.deferred_resource),
            "deferred_budget": list(self.deferred_budget),
            "deferred_capacity": list(self.deferred_capacity),
            "outcomes": [o.to_dict() for o in self.outcomes],
            "classifications": [list(c) for c in self.classifications],
        }


# --------------------------------------------------------------------------- #
# Execution backends (proven equivalent — determinism guard)                    #
# --------------------------------------------------------------------------- #
class ExecutionBackend(Protocol):
    """Runs a list of no-argument thunks and returns their results in **submission order**.

    Each thunk is written by the executor to never raise (it captures faults into its returned
    outcome), so a backend simply collects results positionally. The synchronous and thread-pool
    backends must return identical results for the same inputs — that equivalence is the
    determinism guard for concurrency."""

    def run(self, thunks: List[Callable[[], "QuantumOutcome"]]) -> List["QuantumOutcome"]:
        ...


class SynchronousExecutionBackend:
    """Runs quanta sequentially in admission order. Fully deterministic; the reference backend."""

    def run(self, thunks: List[Callable[[], "QuantumOutcome"]]) -> List["QuantumOutcome"]:
        return [t() for t in thunks]


class ThreadPoolExecutionBackend:
    """Runs quanta on a bounded thread pool for genuine host-level concurrency.

    Results are returned in **submission order** (via a positional map), so completion timing
    never reorders reconciliation. The pool is sized to the batch (bounded by the executor's
    concurrency limit upstream). A submission fault is surfaced to the executor as a raised
    exception from :meth:`run` only if the pool itself cannot accept work — individual quantum
    faults are already captured inside each thunk."""

    def run(self, thunks: List[Callable[[], "QuantumOutcome"]]) -> List["QuantumOutcome"]:
        if not thunks:
            return []
        workers = max(1, len(thunks))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(t) for t in thunks]
            return [f.result() for f in futures]  # positional: submission order preserved


# --------------------------------------------------------------------------- #
# The executor                                                                  #
# --------------------------------------------------------------------------- #
#: A resolver supplies a workflow's declared resource claims for the upcoming quantum. It must be
#: available BEFORE the quantum begins so admission can be decided safely.
ClaimsResolver = Callable[[str], Iterable[ResourceClaim]]
#: A resolver supplies a workflow's declared maximum budget requirement for the upcoming quantum.
BudgetResolver = Callable[[str], BudgetRequirement]


class ExecutorInfrastructureError(Exception):
    """Raised when H22-D's own execution infrastructure fails (e.g. the backend cannot run a
    batch) — distinct from a workflow/provider failure. The executor fails closed rather than
    fabricating a workflow outcome."""


class ConcurrentPortfolioExecutor:
    """Bounded concurrent multi-workflow execution over one portfolio (H22-D).

    Composes the H22-B scheduler (batch selection + fairness), an H22-C
    :class:`PortfolioController` (durable trace, failure policy, cooperative cancellation,
    checkpoint), a :class:`ResourceCoordinator`, a :class:`BudgetCoordinator`, and a
    :class:`CompensationRegistry`. It reaches execution only through the unchanged
    ``advance_workflow`` seam and never authorizes a task."""

    def __init__(
        self,
        runtime: object,
        portfolio: WorkflowPortfolio,
        *,
        policy: Optional[ConcurrencyPolicy] = None,
        controller: Optional[PortfolioController] = None,
        scheduler: Optional[PortfolioScheduler] = None,
        scheduling_policy: Optional[SchedulingPolicy] = None,
        failure_policy: PortfolioFailurePolicy = PortfolioFailurePolicy.ISOLATE_WORKFLOW,
        trace: Optional[PortfolioTrace] = None,
        event_store: Optional[object] = None,
        checkpoint_store: Optional[object] = None,
        resource_coordinator: Optional[ResourceCoordinator] = None,
        budget: Optional[PortfolioBudget] = None,
        budget_coordinator: Optional[BudgetCoordinator] = None,
        compensation_registry: Optional[CompensationRegistry] = None,
        backend: Optional[ExecutionBackend] = None,
        claims_resolver: Optional[ClaimsResolver] = None,
        budget_resolver: Optional[BudgetResolver] = None,
    ) -> None:
        self._runtime = runtime
        self._portfolio = portfolio
        self._policy = policy or ConcurrencyPolicy()
        self._controller = controller or PortfolioController(
            runtime,
            portfolio,
            scheduler=scheduler or PortfolioScheduler(runtime, scheduling_policy),
            policy=failure_policy,
            trace=trace,
            event_store=event_store,
            checkpoint_store=checkpoint_store,
        )
        self._resources = resource_coordinator or ResourceCoordinator()
        if budget_coordinator is not None:
            self._budget = budget_coordinator
        else:
            self._budget = BudgetCoordinator(budget)
        self._compensations = compensation_registry or CompensationRegistry()
        self._backend = backend or SynchronousExecutionBackend()
        self._claims_resolver = claims_resolver
        self._budget_resolver = budget_resolver
        # Compensation configuration: origin instance_id -> (compensation_workflow_id, trigger).
        self._compensation_specs: Dict[str, Tuple[str, str]] = {}

    # -- accessors ----------------------------------------------------------
    @property
    def portfolio(self) -> WorkflowPortfolio:
        return self._portfolio

    @property
    def policy(self) -> ConcurrencyPolicy:
        return self._policy

    @property
    def controller(self) -> PortfolioController:
        return self._controller

    @property
    def trace(self) -> PortfolioTrace:
        return self._controller.trace

    @property
    def resources(self) -> ResourceCoordinator:
        return self._resources

    @property
    def budget(self) -> BudgetCoordinator:
        return self._budget

    @property
    def compensations(self) -> CompensationRegistry:
        return self._compensations

    # -- declared-intent configuration -------------------------------------
    def set_resource_claims(self, instance_id: str, claims: Iterable[ResourceClaim]) -> None:
        """Declare a workflow's static resource claims (an alternative to a claims resolver)."""
        self._static_claims_setdefault()[instance_id] = tuple(claims)

    def set_budget_requirement(self, instance_id: str, requirement: BudgetRequirement) -> None:
        """Declare a workflow's static budget requirement (an alternative to a budget resolver)."""
        self._static_budget_setdefault()[instance_id] = requirement

    def configure_compensation(
        self, origin_instance_id: str, compensation_workflow_id: str,
        trigger=None,
    ) -> None:
        """Configure the compensation workflow to register when ``origin_instance_id`` fails.

        This only records the *relationship*; the compensation workflow is scheduled by the
        application as an ordinary workflow (fresh governance) if/when the trigger fires."""
        from .compensation import CompensationTrigger

        trig = trigger or CompensationTrigger.ON_WORKFLOW_FAILURE
        self._compensation_specs[origin_instance_id] = (compensation_workflow_id, trig.value)

    def _static_claims_setdefault(self) -> Dict[str, Tuple[ResourceClaim, ...]]:
        if not hasattr(self, "_static_claims"):
            self._static_claims: Dict[str, Tuple[ResourceClaim, ...]] = {}
        return self._static_claims

    def _static_budget_setdefault(self) -> Dict[str, BudgetRequirement]:
        if not hasattr(self, "_static_budget"):
            self._static_budget: Dict[str, BudgetRequirement] = {}
        return self._static_budget

    def _claims_for(self, instance_id: str) -> Tuple[ResourceClaim, ...]:
        if self._claims_resolver is not None:
            return tuple(self._claims_resolver(instance_id))
        return self._static_claims_setdefault().get(instance_id, ())

    def _budget_for(self, instance_id: str) -> BudgetRequirement:
        if self._budget_resolver is not None:
            return self._budget_resolver(instance_id)
        return self._static_budget_setdefault().get(instance_id, BudgetRequirement())

    # -- cancellation (cooperative; delegated to the H22-C controller) ------
    def cancel(self, instance_id: str, scope=None):
        """Cooperatively cancel a workflow (and, by scope, its dependents / the whole portfolio).

        Cancellation never interrupts an in-flight indivisible H22-A quantum: a quantum already
        admitted this round runs to its stable boundary; the cancellation applies to *future*
        quanta (the runtime checks the cancellation token at the start of the next quantum). This
        method is intended to be called between rounds; when the portfolio is idle it takes effect
        immediately."""
        from .control import CancellationScope

        return self._controller.cancel(instance_id, scope or CancellationScope.WORKFLOW_ONLY)

    # -- one concurrent round ----------------------------------------------
    def step_concurrent(self) -> ConcurrentPortfolioStepResult:
        """Plan → execute → join → reconcile one bounded concurrent batch. Returns an immutable
        :class:`ConcurrentPortfolioStepResult`. Does not checkpoint (call :meth:`checkpoint` at the
        stable boundary if durability is wanted)."""
        from .portfolio import TERMINAL_PORTFOLIO_STATUSES

        if self._portfolio.status in TERMINAL_PORTFOLIO_STATUSES:
            return ConcurrentPortfolioStepResult(
                portfolio_id=self._portfolio.portfolio_id,
                round=self._portfolio.round,
                batch_id=self._batch_id(self._portfolio.round),
                reason=ConcurrentStepReason.PORTFOLIO_TERMINAL.value,
            )

        # 1) PLAN — deterministic batch selection with atomic resource+budget admission.
        plan = self._controller.scheduler.plan_batch(
            self._portfolio,
            max_concurrency=self._policy.max_concurrent_quanta,
            admit=self._admit,
        )
        batch_id = self._batch_id(plan.round)
        deferred_resource, deferred_budget = self._split_deferrals(plan)

        if not plan.admitted:
            return self._quiescent_result(plan, batch_id, deferred_resource, deferred_budget)

        # Deterministic admission audit (emitted in admission order, before any execution).
        self._emit_plan(plan, batch_id, deferred_resource, deferred_budget)

        # 2) EXECUTE — one indivisible H22-A quantum per admitted workflow, on the backend.
        thunks: List[Callable[[], QuantumOutcome]] = [
            self._make_quantum_thunk(iid, batch_id, seq)
            for seq, iid in enumerate(plan.admitted)
        ]
        try:
            results = self._backend.run(thunks)
        except Exception as exc:  # backend/executor infrastructure failure — fail closed.
            # Do not fabricate any workflow outcome; release every reservation taken for this batch.
            for iid in plan.admitted:
                self._budget.release(iid)
                self._resources.release(iid)
            raise ExecutorInfrastructureError(
                f"concurrent execution backend failed for batch {batch_id!r}: {exc}"
            ) from exc

        # 3) JOIN + 4) RECONCILE — deterministic, in admission order (single coordinator thread).
        outcomes = self._reconcile(plan.admitted, results, batch_id)

        # Failure observation + compensation coordination (bounded; policy applies to future rounds).
        self._controller.observe_failures()
        self._coordinate_compensation()

        self._controller.trace.emit(
            PortfolioEventType.CONCURRENT_BATCH_RECONCILED,
            batch_id=batch_id, round=plan.round, admitted=list(plan.admitted),
        )
        return ConcurrentPortfolioStepResult(
            portfolio_id=self._portfolio.portfolio_id,
            round=plan.round,
            batch_id=batch_id,
            reason=ConcurrentStepReason.BATCH_EXECUTED.value,
            candidates=plan.ordered,
            admitted=plan.admitted,
            admitted_reasons=dict(plan.admitted_reasons),
            deferred_resource=deferred_resource,
            deferred_budget=deferred_budget,
            deferred_capacity=plan.capacity_deferred,
            outcomes=outcomes,
            classifications=plan.classifications,
        )

    def run_concurrent(self, max_rounds: int = 1000) -> List[ConcurrentPortfolioStepResult]:
        """Step concurrently until the portfolio is quiescent, complete, or terminal (bounded).

        Stops the moment a round is not ``BATCH_EXECUTED`` (nothing admitted). ``max_rounds`` is a
        hard bound so this never spins."""
        if max_rounds <= 0:
            raise ValueError("max_rounds must be positive")
        out: List[ConcurrentPortfolioStepResult] = []
        for _ in range(max_rounds):
            result = self.step_concurrent()
            out.append(result)
            if not result.granted:
                break
        return out

    # -- durable checkpoint (stable batch boundary only) --------------------
    def checkpoint(self, *, expected_generation: Optional[int] = None):
        """Commit a durable portfolio checkpoint at a stable batch boundary.

        Enforces the H22-D stable-boundary invariant BEFORE building anything: there must be no
        active resource reservation and no active budget reservation (a checkpoint taken with
        in-flight reservations would not be self-recoverable). It then delegates to the H22-C
        controller's self-validating checkpoint path, extended with the durable H22-D state
        (budget limits + consumed, compensation registrations). Reservations and thread handles
        are never persisted."""
        if not self._resources.is_empty:
            raise ValueError(
                "refusing to checkpoint with active resource reservations "
                f"({self._resources.active_instance_ids()}): not a stable batch boundary"
            )
        if self._budget.has_active_reservations:
            raise ValueError(
                "refusing to checkpoint with active budget reservations "
                f"({self._budget.active_instance_ids()}): not a stable batch boundary"
            )
        return self._controller.checkpoint(
            expected_generation=expected_generation,
            concurrency_state=self._h22d_checkpoint_state(),
        )

    def _h22d_checkpoint_state(self) -> Dict[str, object]:
        return {
            "budget": self._budget.budget_state(),
            "compensations": self._compensations.registry_state(),
        }

    # -- internals ----------------------------------------------------------
    def _batch_id(self, rnd: int) -> str:
        """Deterministic batch identity assigned before launch (never from completion timing)."""
        return f"{self._portfolio.portfolio_id}#batch-{rnd}"

    def _admit(self, entry) -> AdmissionDecision:
        """The admission predicate the scheduler calls in SWRR order. Atomically reserves the
        candidate's resources then its budget; rolls the resource reservation back if the budget
        is short, so admission is truly all-or-none across both coordinators."""
        iid = entry.instance_id
        claims = self._claims_for(iid)
        req = self._budget_for(iid)
        r_ok, conflict = self._resources.reserve(iid, claims)
        if not r_ok:
            return AdmissionDecision(False, "RESOURCE_CONFLICT", conflict.to_dict())
        b_ok, shortfall = self._budget.reserve(iid, req)
        if not b_ok:
            self._resources.release(iid)  # roll back — nothing half-reserved survives
            return AdmissionDecision(False, "BUDGET_UNAVAILABLE", shortfall.to_dict())
        return AdmissionDecision(
            True,
            detail={
                "claims": [c.to_dict() for c in self._resources.active_claims(iid)],
                "budget": req.to_dict(),
            },
        )

    @staticmethod
    def _split_deferrals(plan: BatchPlan):
        deferred_resource: List[Dict[str, object]] = []
        deferred_budget: List[Dict[str, object]] = []
        for iid, reason, detail in plan.deferred:
            record = dict(detail)
            record.setdefault("instance_id", iid)
            if reason == "BUDGET_UNAVAILABLE":
                deferred_budget.append(record)
            else:
                deferred_resource.append(record)
        return tuple(deferred_resource), tuple(deferred_budget)

    def _quiescent_result(self, plan, batch_id, deferred_resource, deferred_budget):
        if plan.stop_reason == PortfolioStepReason.EMPTY_PORTFOLIO.value:
            reason = ConcurrentStepReason.EMPTY_PORTFOLIO
        elif plan.stop_reason == PortfolioStepReason.ALL_TERMINAL.value:
            reason = ConcurrentStepReason.ALL_TERMINAL
            self._controller.trace.emit(
                PortfolioEventType.PORTFOLIO_COMPLETED, round=plan.round
            )
        elif deferred_resource or deferred_budget or plan.capacity_deferred:
            # Eligible work exists but nothing was concurrently admissible this round.
            reason = ConcurrentStepReason.NO_CONCURRENTLY_ADMISSIBLE_WORKFLOW
            self._emit_deferrals(plan, batch_id, deferred_resource, deferred_budget)
        else:
            reason = ConcurrentStepReason.NO_ELIGIBLE_WORKFLOW
            self._controller.trace.emit(
                PortfolioEventType.NO_ELIGIBLE_WORKFLOW, round=plan.round
            )
        return ConcurrentPortfolioStepResult(
            portfolio_id=self._portfolio.portfolio_id,
            round=plan.round,
            batch_id=batch_id,
            reason=reason.value,
            candidates=plan.ordered,
            deferred_resource=deferred_resource,
            deferred_budget=deferred_budget,
            deferred_capacity=plan.capacity_deferred,
            classifications=plan.classifications,
        )

    def _emit_plan(self, plan, batch_id, deferred_resource, deferred_budget):
        self._controller.trace.emit(
            PortfolioEventType.CONCURRENT_BATCH_PLANNED,
            batch_id=batch_id, round=plan.round,
            max_concurrent=self._policy.max_concurrent_quanta,
            candidates=list(plan.ordered), admitted=list(plan.admitted),
            deferred_capacity=list(plan.capacity_deferred),
        )
        for seq, iid in enumerate(plan.admitted):
            detail = plan.admitted_reasons.get(iid)
            self._controller.trace.emit(
                PortfolioEventType.QUANTUM_ADMITTED,
                instance_id=iid, batch_id=batch_id, admission_sequence=seq, round=plan.round,
                selection_reason=detail.to_dict() if detail else None,
            )
            claims = [c.to_dict() for c in self._resources.active_claims(iid)]
            if claims:
                self._controller.trace.emit(
                    PortfolioEventType.RESOURCE_RESERVED,
                    instance_id=iid, batch_id=batch_id, claims=claims,
                )
            req = self._budget_for(iid)
            if not req.is_empty:
                self._controller.trace.emit(
                    PortfolioEventType.BUDGET_RESERVED,
                    instance_id=iid, batch_id=batch_id, amounts=req.to_dict(),
                )
        self._emit_deferrals(plan, batch_id, deferred_resource, deferred_budget)

    def _emit_deferrals(self, plan, batch_id, deferred_resource, deferred_budget):
        for rec in deferred_resource:
            self._controller.trace.emit(
                PortfolioEventType.QUANTUM_DEFERRED_RESOURCE, batch_id=batch_id,
                round=plan.round, **rec,
            )
        for rec in deferred_budget:
            self._controller.trace.emit(
                PortfolioEventType.QUANTUM_DEFERRED_BUDGET, batch_id=batch_id,
                round=plan.round, **rec,
            )
        for iid in plan.capacity_deferred:
            self._controller.trace.emit(
                PortfolioEventType.QUANTUM_DEFERRED_CAPACITY, batch_id=batch_id,
                round=plan.round, instance_id=iid,
            )

    def _make_quantum_thunk(self, instance_id: str, batch_id: str, seq: int):
        """Build a narrow worker thunk: advance ONE distinct workflow by one H22-A quantum and
        return an immutable outcome. A raw exception is captured as an infrastructure error rather
        than propagated (so one worker fault never corrupts the coordinator or another worker's
        result)."""
        runtime = self._runtime

        def _thunk() -> QuantumOutcome:
            try:
                advance_outcome = runtime.advance_workflow(instance_id)
                return QuantumOutcome(
                    instance_id=instance_id, batch_id=batch_id, admission_sequence=seq,
                    advance_outcome=advance_outcome,
                )
            except Exception as exc:  # infrastructure fault for THIS quantum — never fabricate.
                return QuantumOutcome(
                    instance_id=instance_id, batch_id=batch_id, admission_sequence=seq,
                    error=f"{type(exc).__name__}: {exc}",
                )

        return _thunk

    def _reconcile(
        self, admitted: Tuple[str, ...], results: List[QuantumOutcome], batch_id: str
    ) -> Tuple[QuantumOutcome, ...]:
        """Reconcile every admitted quantum in deterministic admission order (Section 46 option B).

        Releases resources always; settles budget when the quantum actually ran a provider (a
        completed/failed task), otherwise releases it (a HOLD/ESCALATE/no-op/cancellation/infra
        fault consumed nothing). Emits the reconciliation trace in admission order regardless of
        the order the quanta actually completed in."""
        by_id = {o.instance_id: o for o in results}
        reconciled: List[QuantumOutcome] = []
        for seq, iid in enumerate(admitted):
            outcome = by_id.get(iid)
            settlement = self._settle_budget(iid, outcome)
            released = self._resources.release(iid)
            if released:
                self._controller.trace.emit(
                    PortfolioEventType.RESOURCE_RELEASED, instance_id=iid, batch_id=batch_id,
                )
            final = QuantumOutcome(
                instance_id=iid, batch_id=batch_id, admission_sequence=seq,
                advance_outcome=outcome.advance_outcome if outcome else None,
                error=outcome.error if outcome else "missing worker result",
                budget_settlement=settlement,
                resource_released=released,
            )
            reconciled.append(final)
            self._controller.trace.emit(
                PortfolioEventType.CONCURRENT_QUANTUM_COMPLETED,
                instance_id=iid, batch_id=batch_id, admission_sequence=seq,
                status_after=(final.advance_outcome.status_after if final.advance_outcome else None),
                stop_reason=(final.advance_outcome.stop_reason if final.advance_outcome else None),
                infrastructure_failure=final.infrastructure_failure,
            )
        return tuple(reconciled)

    def _settle_budget(self, instance_id: str, outcome: Optional[QuantumOutcome]):
        """Settle (charge, conservatively) when a provider ran, else release (no charge)."""
        provider_ran = bool(
            outcome
            and outcome.advance_outcome is not None
            and outcome.error is None
            and outcome.advance_outcome.task_id is not None
            and outcome.advance_outcome.task_status
            in (
                # A task that reached COMPLETED or FAILED ran (or attempted) its provider.
                "COMPLETED",
                "FAILED",
            )
        )
        if provider_ran:
            settlement = self._budget.settle(instance_id)  # conservative: charge reservation
            self._controller.trace.emit(
                PortfolioEventType.BUDGET_SETTLED, instance_id=instance_id,
                charged=dict(settlement.charged), released=dict(settlement.released),
                actual_known=settlement.actual_known,
            )
            return settlement.to_dict()
        # No provider consumption (HOLD/ESCALATE/no-op/cancel/infra) — release the reservation.
        if self._budget.release(instance_id):
            self._controller.trace.emit(
                PortfolioEventType.BUDGET_SETTLED, instance_id=instance_id, released=True,
            )
        return None

    def _coordinate_compensation(self) -> None:
        """Register (idempotently) a compensation intent for any configured origin workflow that
        has been observed to fail. Never executes the compensation; only records the intent with
        origin lineage and emits one event the first time."""
        from .compensation import CompensationSpec, CompensationTrigger

        for iid, (comp_wf_id, trigger_value) in sorted(self._compensation_specs.items()):
            if not self._portfolio.is_failed(iid):
                continue
            spec = CompensationSpec(
                origin_instance_id=iid,
                compensation_workflow_id=comp_wf_id,
                trigger=CompensationTrigger(trigger_value),
                reason="observed_workflow_failure",
            )
            reg, created = self._compensations.register(spec)
            if created:
                self._controller.trace.emit(
                    PortfolioEventType.COMPENSATION_REGISTERED,
                    **{k: v for k, v in reg.to_dict().items() if v is not None},
                )
