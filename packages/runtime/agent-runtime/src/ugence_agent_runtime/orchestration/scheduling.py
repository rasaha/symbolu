"""The H22-B deterministic portfolio scheduler.

Given a :class:`~.portfolio.WorkflowPortfolio` of prepared workflows and an
:class:`~..runtime.engine.AgentRuntime` that owns their execution, the scheduler answers
one question per round:

    "Which eligible workflow receives the next H22-A execution quantum, and why?"

It does so deterministically — the choice is reproducible from explicit portfolio state
alone, with no dependence on wall-clock, object identity, dict iteration order, threads, or
randomness. One ``step`` classifies every workflow, orders the eligible ones by a single
stable key, updates fairness and aging, selects one workflow, and grants it **exactly one**
bounded quantum via ``runtime.advance_workflow`` — the unchanged H22-A seam.

Governance boundary (unchanged, and never touched here):

    scheduler.step  →  "workflow B gets the next quantum"
                         │
                         ▼
    runtime.advance_workflow(B)  →  build proposal → fresh governance →
        CLEAR/HOLD/BLOCK/ESCALATE → exact-action check → provider (iff allowed) →
        transition → canonical execution state → checkpoint

The scheduler NEVER authorizes a task, caches/manufactures a CLEAR, reinterprets a HOLD,
downgrades a BLOCK, auto-resumes an ESCALATE, mutates a proposal, or calls a provider. A
governance HOLD (runtime WAITING) or ESCALATE (runtime PAUSED) simply makes a workflow
non-eligible; the scheduler never resumes it — that remains the explicit job of
``resume_workflow`` outside H22-B.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..models.results import WorkflowAdvanceOutcome
from ..models.workflow import TERMINAL_WORKFLOW_STATUSES, WorkflowStatus
from .dependencies import DependencyState
from .portfolio import (
    PortfolioStatus,
    PortfolioWorkflowEntry,
    WorkflowPortfolio,
    WorkflowPriority,
    priority_rank,
)


class WorkflowEligibility(str, Enum):
    """Deterministic orchestration classification of a registered workflow this round.

    Mapped one-to-one from the workflow's current runtime ``WorkflowStatus`` and its
    dependency verdict. Only ``ELIGIBLE`` workflows are candidates for a quantum.
    """

    #: Runtime RUNNING and all dependencies satisfied — a candidate for a quantum.
    ELIGIBLE = "ELIGIBLE"
    #: A prerequisite is not yet met (predecessor not terminal). Not eligible; does not age.
    WAITING_DEPENDENCY = "WAITING_DEPENDENCY"
    #: A hard success-prerequisite failed (predecessor terminal but not COMPLETED).
    #: Not eligible; fail-closed; does not age.
    BLOCKED_DEPENDENCY = "BLOCKED_DEPENDENCY"
    #: Runtime WAITING (a governance HOLD). Not eligible; H22-B never self-resolves it; does
    #: not age.
    WAITING_RUNTIME = "WAITING_RUNTIME"
    #: Runtime PAUSED (a governance ESCALATE or an explicit pause). Not eligible; H22-B never
    #: auto-resumes it; does not age.
    PAUSED = "PAUSED"
    #: Runtime terminal (COMPLETED / FAILED / CANCELLED). Not eligible; does not age.
    TERMINAL = "TERMINAL"


class PortfolioStepReason(str, Enum):
    """Why a scheduling ``step`` ended — a deterministic, bounded stop reason."""

    #: One eligible workflow was selected and granted exactly one bounded quantum.
    QUANTUM_GRANTED = "QUANTUM_GRANTED"
    #: Non-terminal work exists, but no workflow is eligible this round (all are
    #: WAITING/PAUSED/dependency-blocked). The portfolio is *quiescent*, not complete.
    NO_ELIGIBLE_WORKFLOW = "NO_ELIGIBLE_WORKFLOW"
    #: Every registered workflow is terminal — the portfolio is complete.
    ALL_TERMINAL = "ALL_TERMINAL"
    #: The portfolio has no registrations.
    EMPTY_PORTFOLIO = "EMPTY_PORTFOLIO"


@dataclass(frozen=True)
class SchedulingPolicy:
    """The deterministic knobs that shape ordering. Pure data; no behavior/authority.

    ``aging_cap`` bounds how far a runnable-but-unselected workflow's age can lower its
    effective rank (starvation prevention stays bounded). ``critical_never_ages`` reserves
    the ``CRITICAL`` class as absolute — aging never lets a lower class reach it.
    """

    aging_cap: int = 500
    critical_never_ages: bool = True

    def effective_rank(self, entry: PortfolioWorkflowEntry) -> int:
        """Lower = more preferred. ``base_rank - min(age, aging_cap)``, floored so a
        non-critical workflow can climb above its peers but never reaches the CRITICAL
        floor; CRITICAL is absolute and never ages."""
        base = priority_rank(entry.priority)
        if self.critical_never_ages and entry.priority is WorkflowPriority.CRITICAL:
            return base
        bonus = min(entry.age, self.aging_cap)
        # Floor at 1 so no non-critical workflow can reach the CRITICAL rank (0).
        return max(1, base - bonus)


@dataclass(frozen=True)
class SelectionReason:
    """Structured, inspectable explanation of why a specific workflow was selected.

    Enough to answer "why B instead of A?" without free-form prose: the effective rank the
    selection turned on, the base priority, the accumulated age, the dependency depth, the
    fairness deficit, and the tie-breaking registration sequence.
    """

    instance_id: str
    effective_rank: int
    base_priority: str
    age: int
    dependency_depth: int
    fairness_deficit: float
    registration_sequence: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "effective_rank": self.effective_rank,
            "base_priority": self.base_priority,
            "age": self.age,
            "dependency_depth": self.dependency_depth,
            "fairness_deficit": self.fairness_deficit,
            "registration_sequence": self.registration_sequence,
        }


@dataclass(frozen=True)
class PortfolioStepResult:
    """The immutable, read-only outcome of one scheduling round.

    References the granted quantum's outcome by value (``advance_outcome`` is itself a
    frozen H22-A ``WorkflowAdvanceOutcome`` that points at runtime state *by digest*); the
    scheduler exposes no mutable runtime handle. ``eligible`` is the ordered candidate list
    (best first); ``classifications`` records every workflow's eligibility this round.
    """

    portfolio_id: str
    round: int
    reason: str
    selected_instance_id: Optional[str] = None
    selection_reason: Optional[SelectionReason] = None
    eligible: Tuple[str, ...] = ()
    classifications: Tuple[Tuple[str, str], ...] = ()
    advance_outcome: Optional[WorkflowAdvanceOutcome] = None

    @property
    def granted(self) -> bool:
        return self.reason == PortfolioStepReason.QUANTUM_GRANTED.value

    def blocked(self) -> Tuple[Tuple[str, str], ...]:
        """Registered workflows that are non-terminal but not eligible this round."""
        return tuple(
            (iid, cls)
            for iid, cls in self.classifications
            if cls not in (
                WorkflowEligibility.ELIGIBLE.value,
                WorkflowEligibility.TERMINAL.value,
            )
        )

    def to_dict(self) -> Dict[str, object]:
        return {
            "portfolio_id": self.portfolio_id,
            "round": self.round,
            "reason": self.reason,
            "selected_instance_id": self.selected_instance_id,
            "selection_reason": (
                self.selection_reason.to_dict() if self.selection_reason else None
            ),
            "eligible": list(self.eligible),
            "classifications": [list(c) for c in self.classifications],
            "advance_outcome": (
                self.advance_outcome.to_dict() if self.advance_outcome else None
            ),
        }


class PortfolioScheduler:
    """Deterministically grants H22-A quanta to portfolio workflows, one per step.

    The scheduler binds one live :class:`AgentRuntime` (the executor it advances workflows
    through) and a :class:`SchedulingPolicy`. It holds no per-portfolio mutable state of its
    own — all fairness/aging/round state lives on the portfolio, keeping a step reproducible
    from explicit state.
    """

    def __init__(self, runtime: object, policy: Optional[SchedulingPolicy] = None) -> None:
        self._runtime = runtime
        self._policy = policy or SchedulingPolicy()

    @property
    def policy(self) -> SchedulingPolicy:
        return self._policy

    # -- read-only classification (invokes NO provider / NO governance) -----
    def _status_of(self, instance_id: str) -> WorkflowStatus:
        return self._runtime.instance(instance_id).status

    def classify(
        self, portfolio: WorkflowPortfolio
    ) -> List[Tuple[PortfolioWorkflowEntry, WorkflowEligibility]]:
        """Classify every registered workflow deterministically (registration order).

        Reads runtime status and dependency verdicts only — it performs no advancement, so
        it invokes zero provider calls and zero governance evaluations. Terminal status
        dominates; then a failed hard dependency; then a pending dependency; otherwise the
        runtime status decides eligibility.
        """
        graph = portfolio.dependency_graph()
        statuses: Dict[str, WorkflowStatus] = {
            e.instance_id: self._status_of(e.instance_id) for e in portfolio.entries()
        }
        out: List[Tuple[PortfolioWorkflowEntry, WorkflowEligibility]] = []
        for entry in portfolio.entries():
            out.append((entry, self._classify_one(entry, graph, statuses)))
        return out

    def _classify_one(
        self,
        entry: PortfolioWorkflowEntry,
        graph,
        statuses: Dict[str, WorkflowStatus],
    ) -> WorkflowEligibility:
        status = statuses[entry.instance_id]
        if status in TERMINAL_WORKFLOW_STATUSES:
            return WorkflowEligibility.TERMINAL
        dep = graph.classify_dependencies(entry.instance_id, statuses)
        if dep is DependencyState.FAILED:
            return WorkflowEligibility.BLOCKED_DEPENDENCY
        if dep is DependencyState.PENDING:
            return WorkflowEligibility.WAITING_DEPENDENCY
        # Dependencies satisfied — the runtime status decides.
        if status is WorkflowStatus.RUNNING:
            return WorkflowEligibility.ELIGIBLE
        if status is WorkflowStatus.WAITING:
            return WorkflowEligibility.WAITING_RUNTIME
        if status is WorkflowStatus.PAUSED:
            return WorkflowEligibility.PAUSED
        # CREATED/READY are internal to setup and not expected after prepare_workflow;
        # treat conservatively as not-yet-runnable rather than eligible.
        return WorkflowEligibility.WAITING_RUNTIME

    # -- one deterministic scheduling round ---------------------------------
    def step(self, portfolio: WorkflowPortfolio) -> PortfolioStepResult:
        """Run exactly one scheduling round and grant at most one bounded quantum.

        Sequence: begin a logical round → classify every workflow → if none eligible return
        a deterministic stop reason → otherwise accrue fairness, order by the stable key,
        select the best, age the unselected, reset the selected, and grant one quantum via
        ``advance_workflow``. Returns a frozen :class:`PortfolioStepResult`.
        """
        graph = portfolio.dependency_graph()
        entries = portfolio.entries()
        rnd = portfolio._begin_round()

        if not entries:
            return PortfolioStepResult(
                portfolio_id=portfolio.portfolio_id,
                round=rnd,
                reason=PortfolioStepReason.EMPTY_PORTFOLIO.value,
            )

        classification = self.classify(portfolio)
        classifications = tuple(
            (e.instance_id, c.value) for e, c in classification
        )
        eligible = [e for e, c in classification if c is WorkflowEligibility.ELIGIBLE]

        if not eligible:
            all_terminal = all(
                c is WorkflowEligibility.TERMINAL for _, c in classification
            )
            if all_terminal:
                portfolio._mark_completed()
                reason = PortfolioStepReason.ALL_TERMINAL
            else:
                reason = PortfolioStepReason.NO_ELIGIBLE_WORKFLOW
            return PortfolioStepResult(
                portfolio_id=portfolio.portfolio_id,
                round=rnd,
                reason=reason.value,
                classifications=classifications,
            )

        # Fairness: every eligible workflow accrues its weight this round (deficit RR).
        for e in eligible:
            e.deficit += e.weight

        # Deterministic ordering key (select the minimum). Lower effective_rank preferred;
        # then more-upstream (lower dependency_depth); then higher fairness deficit
        # (negated); then earliest registration; then instance_id — a total order with no
        # dependence on wall-clock, identity, dict order, or randomness.
        def key(e: PortfolioWorkflowEntry):
            return (
                self._policy.effective_rank(e),
                graph.depth(e.instance_id),
                -e.deficit,
                e.registration_sequence,
                e.instance_id,
            )

        ordered = sorted(eligible, key=key)
        selected = ordered[0]

        # Aging: every eligible-but-NOT-selected workflow ages (bounded); the selected one
        # resets. Only runnable-but-unselected workflows age — non-eligible workflows
        # (dependency-blocked / WAITING / PAUSED / terminal) are not in `eligible` and are
        # never aged here.
        for e in eligible:
            if e.instance_id == selected.instance_id:
                continue
            e.age = min(e.age + 1, self._policy.aging_cap)

        reason_obj = SelectionReason(
            instance_id=selected.instance_id,
            effective_rank=self._policy.effective_rank(selected),
            base_priority=selected.priority.value,
            age=selected.age,
            dependency_depth=graph.depth(selected.instance_id),
            fairness_deficit=selected.deficit,
            registration_sequence=selected.registration_sequence,
        )

        # Fairness cost + age reset happen AFTER the reason snapshot so the reason reflects
        # the state the selection turned on.
        selected.deficit -= 1.0
        selected.age = 0

        # Grant exactly one bounded quantum through the unchanged H22-A seam. This is the
        # ONLY place the scheduler touches execution — governance/exact-action/provider all
        # happen inside here, below H22, never observable between CLEAR and provider.
        outcome = self._runtime.advance_workflow(selected.instance_id)

        return PortfolioStepResult(
            portfolio_id=portfolio.portfolio_id,
            round=rnd,
            reason=PortfolioStepReason.QUANTUM_GRANTED.value,
            selected_instance_id=selected.instance_id,
            selection_reason=reason_obj,
            eligible=tuple(e.instance_id for e in ordered),
            classifications=classifications,
            advance_outcome=outcome,
        )

    def run(
        self, portfolio: WorkflowPortfolio, max_rounds: int = 1000
    ) -> List[PortfolioStepResult]:
        """Convenience: step until the portfolio is quiescent or complete (bounded).

        Steps repeatedly while quanta are being granted, stopping the moment a step returns
        anything other than ``QUANTUM_GRANTED`` (``NO_ELIGIBLE_WORKFLOW`` / ``ALL_TERMINAL``
        / ``EMPTY_PORTFOLIO``) or ``max_rounds`` is reached. ``max_rounds`` is a hard,
        explicit bound so this never spins. The core primitive remains the single-quantum
        :meth:`step`; this only loops it.
        """
        if max_rounds <= 0:
            raise ValueError("max_rounds must be positive")
        results: List[PortfolioStepResult] = []
        for _ in range(max_rounds):
            result = self.step(portfolio)
            results.append(result)
            if not result.granted:
                break
        return results
