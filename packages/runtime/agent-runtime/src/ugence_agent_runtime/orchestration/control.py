"""H22-C — bounded failure propagation and cooperative cancellation control.

This module adds the *orchestration control* surface on top of the H22-B scheduler: a small,
conservative failure-policy matrix, explicit cancellation scopes, and a
:class:`PortfolioController` that ties the scheduler, the audit trace, and the durable
checkpoint together.

Authority boundary (non-negotiable). H22-C decides orchestration *consequences* — "do not
schedule workflows dependent on failed A", "cancel this subgraph". It never reinterprets *why*
a workflow failed and never authorizes a consequential action: it cannot turn a governance
``BLOCK`` into a retry/clear, or a ``FAILED`` into ``COMPLETED``. Cancellation is **cooperative**
— it calls the runtime's own ``cancel_workflow`` and lets the runtime own the task/workflow
state transition; H22-C only records the orchestration decision. There are no threads, no
process termination, and no direct mutation of runtime task status here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..models.workflow import TERMINAL_WORKFLOW_STATUSES, WorkflowStatus
from ..runtime.errors import CheckpointError
from .persistence import PortfolioCheckpoint
from .portfolio import WorkflowPortfolio
from .recovery import build_portfolio_checkpoint, validate_portfolio_checkpoint
from .scheduling import PortfolioScheduler, PortfolioStepReason, PortfolioStepResult, SchedulingPolicy
from .tracing import PortfolioEventType, PortfolioTrace


class PortfolioFailurePolicy(str, Enum):
    """How the portfolio reacts when it observes a workflow's terminal failure.

    Deliberately small and conservative. The default is :attr:`ISOLATE_WORKFLOW` because it is
    the behavior most consistent with live H22-B semantics: H22-B already isolates failure via
    the dependency graph (a failed ``REQUIRES_SUCCESS`` predecessor turns dependents into
    ``BLOCKED_DEPENDENCY`` while independent workflows keep running). Degraded continuation and
    compensation are intentionally out of scope (H22-D)."""

    #: Record the failure; take no further action. Hard-dependents are blocked by the existing
    #: dependency classification; independent workflows continue. (Default.)
    ISOLATE_WORKFLOW = "ISOLATE_WORKFLOW"
    #: Additionally cancel the transitive dependent subgraph of the failed workflow, so its
    #: dependents do not sit indefinitely blocked. Independent workflows continue.
    FAIL_DEPENDENTS = "FAIL_DEPENDENTS"
    #: Cancel every non-terminal workflow and drive the portfolio to a terminal FAILED state;
    #: no further quantum is granted.
    FAIL_PORTFOLIO = "FAIL_PORTFOLIO"


class CancellationScope(str, Enum):
    """The breadth of an explicit cancellation request."""

    #: Cancel only the named workflow. Its dependents are then classified by the dependency
    #: graph (a ``REQUIRES_SUCCESS`` dependent becomes ``BLOCKED_DEPENDENCY``).
    WORKFLOW_ONLY = "WORKFLOW_ONLY"
    #: Cancel the named workflow plus every workflow transitively dependent on it. Independent
    #: workflows are untouched.
    DEPENDENT_SUBGRAPH = "DEPENDENT_SUBGRAPH"
    #: Cancel every non-terminal workflow in the portfolio and drive it to terminal CANCELLED.
    PORTFOLIO_ALL = "PORTFOLIO_ALL"


@dataclass(frozen=True)
class PortfolioCancellationResult:
    """The deterministic outcome of one cancellation request (immutable).

    ``cancelled`` are the workflows this request transitioned to CANCELLED (in registration
    order); ``already_cancelled`` were already cancelled-by-portfolio (idempotent no-ops);
    ``skipped_terminal`` were terminal for another reason (COMPLETED/FAILED) and cannot be
    cancelled. ``targets`` is the full deterministic target set the scope selected."""

    scope: str
    requested: Optional[str]
    targets: Tuple[str, ...]
    cancelled: Tuple[str, ...]
    already_cancelled: Tuple[str, ...]
    skipped_terminal: Tuple[str, ...]


class PortfolioController:
    """Ties the H22-B scheduler to H22-C durability, trace, failure policy, and cancellation.

    The controller owns no execution truth — it drives the scheduler (which reaches execution
    only through the unchanged ``advance_workflow`` seam), records orchestration events on an
    append-only :class:`PortfolioTrace`, applies the configured failure policy when it observes
    a terminal failure, performs cooperative cancellation via the runtime, and commits durable
    portfolio checkpoints that satisfy the self-recoverability invariant before persistence."""

    def __init__(
        self,
        runtime: object,
        portfolio: WorkflowPortfolio,
        *,
        scheduler: Optional[PortfolioScheduler] = None,
        policy: PortfolioFailurePolicy = PortfolioFailurePolicy.ISOLATE_WORKFLOW,
        scheduling_policy: Optional[SchedulingPolicy] = None,
        trace: Optional[PortfolioTrace] = None,
        checkpoint_store: Optional[object] = None,
        emit_created: bool = False,
    ) -> None:
        self._runtime = runtime
        self._portfolio = portfolio
        self._scheduler = scheduler or PortfolioScheduler(runtime, scheduling_policy)
        self._policy = policy
        self._trace = trace or PortfolioTrace(portfolio.portfolio_id)
        self._store = checkpoint_store
        if emit_created and not self._trace.entries:
            self._trace.emit(
                PortfolioEventType.PORTFOLIO_CREATED, portfolio_id=portfolio.portfolio_id
            )

    # -- accessors ----------------------------------------------------------
    @property
    def portfolio(self) -> WorkflowPortfolio:
        return self._portfolio

    @property
    def trace(self) -> PortfolioTrace:
        return self._trace

    @property
    def failure_policy(self) -> PortfolioFailurePolicy:
        return self._policy

    @property
    def scheduler(self) -> PortfolioScheduler:
        return self._scheduler

    # -- setup passthroughs (optional; keep the audit trail complete) -------
    def register_workflow(self, instance_id: str, **kwargs):
        entry = self._portfolio.register(instance_id, runtime=self._runtime, **kwargs)
        self._trace.emit(
            PortfolioEventType.WORKFLOW_REGISTERED,
            instance_id=instance_id,
            priority=entry.priority.value,
            weight=entry.weight,
            registration_sequence=entry.registration_sequence,
        )
        return entry

    def add_dependency(self, dependent_id: str, requires_id: str, dep_type=None):
        from .dependencies import DependencyType

        edge = self._portfolio.add_dependency(
            dependent_id, requires_id, dep_type or DependencyType.REQUIRES_COMPLETION
        )
        self._trace.emit(
            PortfolioEventType.DEPENDENCY_ADDED,
            dependent_id=dependent_id,
            requires_id=requires_id,
            dependency_type=edge.dep_type.value,
        )
        return edge

    # -- scheduling ---------------------------------------------------------
    def step(self) -> PortfolioStepResult:
        """Run one scheduling round, record the orchestration event, then observe failures.

        A terminal portfolio (FAILED / CANCELLED) grants no further quantum — the controller
        short-circuits with an ``ALL_TERMINAL`` result rather than stepping the scheduler."""
        from .portfolio import TERMINAL_PORTFOLIO_STATUSES

        if self._portfolio.status in TERMINAL_PORTFOLIO_STATUSES:
            return PortfolioStepResult(
                portfolio_id=self._portfolio.portfolio_id,
                round=self._portfolio.round,
                reason=PortfolioStepReason.ALL_TERMINAL.value,
            )
        result = self._scheduler.step(self._portfolio)
        if result.granted:
            out = result.advance_outcome
            self._trace.emit(
                PortfolioEventType.QUANTUM_GRANTED,
                instance_id=result.selected_instance_id,
                round=result.round,
                execution_state_digest=(out.execution_state_digest if out else None),
                workflow_checkpoint_digest=(out.checkpoint_digest if out else None),
                stop_reason=(out.stop_reason if out else None),
            )
        elif result.reason == PortfolioStepReason.NO_ELIGIBLE_WORKFLOW.value:
            self._trace.emit(
                PortfolioEventType.NO_ELIGIBLE_WORKFLOW, round=result.round
            )
        elif result.reason == PortfolioStepReason.ALL_TERMINAL.value:
            self._trace.emit(
                PortfolioEventType.PORTFOLIO_COMPLETED, round=result.round
            )
        self.observe_failures()
        return result

    # -- failure propagation ------------------------------------------------
    def observe_failures(self) -> Tuple[str, ...]:
        """Record any newly-observed terminal workflow failure and apply the failure policy.

        Deterministic (registration order). A workflow that is terminal because it was
        CANCELLED is not a failure; only runtime status ``FAILED`` is. The reason a workflow
        failed is never reinterpreted here."""
        newly: List[str] = []
        for entry in self._portfolio.entries():
            iid = entry.instance_id
            if self._portfolio.is_failed(iid) or self._portfolio.is_cancelled(iid):
                continue
            if self._runtime.instance(iid).status is WorkflowStatus.FAILED:
                self._portfolio.record_failure(iid, "WORKFLOW_FAILED")
                self._trace.emit(
                    PortfolioEventType.WORKFLOW_FAILURE_OBSERVED,
                    instance_id=iid,
                    policy=self._policy.value,
                )
                newly.append(iid)
                self._apply_failure_policy(iid)
        return tuple(newly)

    def _apply_failure_policy(self, failed_id: str) -> None:
        if self._policy is PortfolioFailurePolicy.ISOLATE_WORKFLOW:
            return  # dependency classification already isolates; nothing else to do.
        if self._policy is PortfolioFailurePolicy.FAIL_DEPENDENTS:
            # Cancel the transitive dependents (the failed workflow is already terminal).
            dependents = [d for d in self._dependent_subgraph(failed_id) if d != failed_id]
            self._cooperative_cancel(dependents, PortfolioFailurePolicy.FAIL_DEPENDENTS.value)
            return
        if self._policy is PortfolioFailurePolicy.FAIL_PORTFOLIO:
            targets = [e.instance_id for e in self._portfolio.entries()]
            self._cooperative_cancel(targets, PortfolioFailurePolicy.FAIL_PORTFOLIO.value)
            self._portfolio._mark_failed()
            self._trace.emit(
                PortfolioEventType.PORTFOLIO_FAILED, round=self._portfolio.round
            )

    # -- cancellation -------------------------------------------------------
    def cancel(
        self, instance_id: str, scope: CancellationScope = CancellationScope.WORKFLOW_ONLY
    ) -> PortfolioCancellationResult:
        """Cancel a workflow (and, by scope, its dependents or the whole portfolio).

        Cooperative and idempotent: repeated requests neither duplicate side effects nor
        corrupt the trace — an already-cancelled target is a no-op. A workflow WAITING from a
        governance HOLD (or PAUSED from an ESCALATE) may be cancelled by explicit control; that
        is the operator choosing not to continue it, not H22-C overruling governance."""
        if not self._portfolio.is_registered(instance_id):
            raise ValueError(f"unknown workflow {instance_id!r}")
        targets = self._cancellation_targets(instance_id, scope)
        self._trace.emit(
            PortfolioEventType.CANCELLATION_REQUESTED,
            instance_id=instance_id,
            scope=scope.value,
            targets=list(targets),
        )
        cancelled, already, skipped = self._cooperative_cancel(targets, scope.value)
        if scope is CancellationScope.PORTFOLIO_ALL:
            self._portfolio._mark_cancelled()
            self._trace.emit(
                PortfolioEventType.PORTFOLIO_CANCELLED, round=self._portfolio.round
            )
        return PortfolioCancellationResult(
            scope=scope.value,
            requested=instance_id,
            targets=targets,
            cancelled=cancelled,
            already_cancelled=already,
            skipped_terminal=skipped,
        )

    def _cooperative_cancel(
        self, targets: List[str], scope_value: str
    ) -> Tuple[Tuple[str, ...], Tuple[str, ...], Tuple[str, ...]]:
        """Cancel each target in registration order, cooperatively and idempotently.

        Returns ``(cancelled_now, already_cancelled, skipped_terminal)``."""
        cancelled_now: List[str] = []
        already: List[str] = []
        skipped: List[str] = []
        ordered = [i for i in self._portfolio.instance_ids if i in set(targets)]
        for iid in ordered:
            if self._portfolio.is_cancelled(iid):
                already.append(iid)
                continue
            inst = self._runtime.instance(iid)
            if inst.status in TERMINAL_WORKFLOW_STATUSES:
                # Terminal for another reason (COMPLETED / FAILED) — cannot be cancelled.
                skipped.append(iid)
                continue
            # Cooperative: the runtime owns the CANCELLED transition; we only record it.
            self._runtime.cancel_workflow(iid)
            if self._portfolio.record_cancellation(iid, scope_value):
                cancelled_now.append(iid)
                self._trace.emit(
                    PortfolioEventType.WORKFLOW_CANCELLED_BY_PORTFOLIO,
                    instance_id=iid,
                    scope=scope_value,
                )
        return tuple(cancelled_now), tuple(already), tuple(skipped)

    def _cancellation_targets(
        self, instance_id: str, scope: CancellationScope
    ) -> Tuple[str, ...]:
        if scope is CancellationScope.WORKFLOW_ONLY:
            return (instance_id,)
        if scope is CancellationScope.PORTFOLIO_ALL:
            return self._portfolio.instance_ids
        # DEPENDENT_SUBGRAPH
        return self._dependent_subgraph(instance_id)

    def _dependent_subgraph(self, root: str) -> Tuple[str, ...]:
        """``root`` plus every workflow transitively dependent on it, in registration order.

        Deterministic: builds a reverse ("is-required-by") adjacency from the dependency graph
        and traverses it, then returns the reachable set in registration order so the
        cancellation application order is stable regardless of set iteration."""
        graph = self._portfolio.dependency_graph()
        # requires: dependent -> [predecessors]. Reverse: predecessor -> [dependents].
        reverse: Dict[str, List[str]] = {i: [] for i in self._portfolio.instance_ids}
        for edge in graph.edges:
            reverse.setdefault(edge.requires_id, []).append(edge.dependent_id)
        reached = set()
        stack = [root]
        while stack:
            node = stack.pop()
            if node in reached:
                continue
            reached.add(node)
            for dep in reverse.get(node, ()):
                if dep not in reached:
                    stack.append(dep)
        return tuple(i for i in self._portfolio.instance_ids if i in reached)

    # -- durable checkpoint -------------------------------------------------
    def checkpoint(self, *, expected_generation: Optional[int] = None) -> PortfolioCheckpoint:
        """Build, self-validate, and persist a durable portfolio checkpoint.

        Enforces the **portfolio self-recoverability invariant**: the checkpoint is validated
        by the same validator recovery uses, BEFORE any write. A checkpoint that would not
        recover is refused (fail closed) and the store is left unchanged. On success a
        ``PORTFOLIO_CHECKPOINT_COMMITTED`` event is recorded. The checkpoint captures the trace
        sequence anchor as it stands *before* the commit event, so a recovered portfolio
        continues the sequence without collision."""
        if self._store is None:
            raise CheckpointError("no portfolio checkpoint store configured")
        cp = build_portfolio_checkpoint(
            self._portfolio,
            self._runtime,
            failure_policy=self._policy.value,
            trace_sequence=self._trace.last_sequence,
        )
        ok, reason = validate_portfolio_checkpoint(cp)
        if not ok:
            raise CheckpointError(
                f"refusing to persist a non-self-recoverable portfolio checkpoint for "
                f"{self._portfolio.portfolio_id!r}: {reason}"
            )
        if expected_generation is not None:
            gen = self._store.save(cp, expected_generation)
        else:
            gen = self._store.save(cp)
        self._trace.emit(
            PortfolioEventType.PORTFOLIO_CHECKPOINT_COMMITTED,
            portfolio_digest=cp.portfolio_digest,
            generation=gen,
            round=cp.round,
        )
        return cp
