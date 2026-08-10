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

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

from ..models.results import WorkflowAdvanceOutcome
from ..models.workflow import TERMINAL_WORKFLOW_STATUSES, WorkflowStatus
from .dependencies import DependencyState
from .portfolio import (
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
    smooth-weighted-round-robin ``fairness_credit`` that won the within-tier tie, and the
    tie-breaking registration sequence.
    """

    instance_id: str
    effective_rank: int
    base_priority: str
    age: int
    dependency_depth: int
    fairness_credit: float
    registration_sequence: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "instance_id": self.instance_id,
            "effective_rank": self.effective_rank,
            "base_priority": self.base_priority,
            "age": self.age,
            "dependency_depth": self.dependency_depth,
            "fairness_credit": self.fairness_credit,
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


@dataclass(frozen=True)
class AdmissionDecision:
    """The verdict of an admission predicate for one candidate quantum (H22-B-neutral).

    ``admitted`` grants the candidate a slot in the concurrent batch. ``reason`` / ``detail``
    are **opaque to the scheduler** — the H22-D admission coordinator fills them with a
    structured resource/budget deferral explanation that flows straight through into the batch
    result. The scheduler never interprets them; it only decides fairness/ordering and calls the
    predicate in smooth-weighted-round-robin order. This is the seam that keeps *scheduling
    eligibility* (H22-B) and *concurrent admission* (H22-D) separate: H22-B asks "may this
    fairness-preferred candidate take a slot?"; it never asks whether the candidate's task is
    authorized (that stays below H22, inside ``advance_workflow``)."""

    admitted: bool
    reason: Optional[str] = None
    detail: Optional[Dict[str, object]] = None


def _always_admit(_entry: PortfolioWorkflowEntry) -> AdmissionDecision:
    """The trivial predicate: admit every candidate (used for the max_concurrency=1,
    no-resource/no-budget case, which is then semantically bounded H22-B execution)."""
    return AdmissionDecision(True)


@dataclass(frozen=True)
class BatchPlan:
    """The deterministic outcome of one batch-selection round (immutable, read-only).

    Produced by :meth:`PortfolioScheduler.plan_batch`. It records which fairness-preferred
    eligible workflows were admitted a concurrent quantum this round and, for every workflow
    held back, *why* — with enough structure to answer "why did A and C run while B did not?"
    without free-form prose:

    * ``admitted`` — instance ids granted a slot, in deterministic admission (SWRR) order;
    * ``admitted_reasons`` — the :class:`SelectionReason` each grant turned on (the effective
      rank, base priority, age, dependency depth, and SWRR fairness credit at selection);
    * ``deferred`` — ``(instance_id, reason, detail)`` for each candidate the admission
      predicate rejected (a resource conflict or budget shortfall — the ``detail`` carries the
      structured evidence);
    * ``capacity_deferred`` — eligible workflows never evaluated because the concurrency limit
      was already filled (they keep their fairness credit; they are not charged and not aged as
      served);
    * ``ordered`` — the full ranked eligible list (best first);
    * ``classifications`` — every registered workflow's eligibility this round;
    * ``round`` — the logical scheduler round;
    * ``stop_reason`` — set (to a :class:`PortfolioStepReason` value) only when nothing was
      admitted (empty / all-terminal / no eligible / nothing concurrently admissible).

    The fairness accounting (SWRR credit + bounded aging) for the admitted set is **already
    committed** on the portfolio when this is returned — admission *is* service. Execution of
    the admitted quanta is the caller's job and happens after (and outside) this call."""

    portfolio_id: str
    round: int
    admitted: Tuple[str, ...]
    admitted_reasons: Dict[str, SelectionReason]
    deferred: Tuple[Tuple[str, str, Dict[str, object]], ...]
    capacity_deferred: Tuple[str, ...]
    ordered: Tuple[str, ...]
    classifications: Tuple[Tuple[str, str], ...]
    stop_reason: Optional[str] = None

    @property
    def granted(self) -> bool:
        return bool(self.admitted)


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
        a deterministic stop reason → otherwise compute effective ranks, form the top
        *contention tier* (the eligible workflows sharing the best
        ``(effective_rank, dependency_depth)``), run **smooth weighted round-robin (SWRR)**
        within that tier to pick the workflow most owed service, age the eligible workflows
        held back *below* the tier (cross-priority starvation prevention), and grant one
        quantum via ``advance_workflow``. Returns a frozen :class:`PortfolioStepResult`.

        Two orthogonal mechanisms, so weighted fairness and aging never fight each other:

        * **Fairness (within a tier):** SWRR. Each round every contender's ``fair_credit``
          gains its ``weight``; the max-credit contender is selected and pays back the tier's
          total weight. This is the classic smooth weighted round-robin — service is exactly
          proportional to weight, deterministic, and starvation-free for every positive
          weight (a weight-1 workflow is never starved by a weight-3 one).
        * **Aging (across tiers):** only an eligible workflow *below* the top tier — held
          back by a higher-priority or more-upstream peer — ages, bounded by ``aging_cap``,
          lowering its effective rank until it eventually joins the tier. Contenders are not
          starved (SWRR serves them), so they never age; the selected workflow resets its
          age. Non-eligible workflows (dependency-blocked / WAITING / PAUSED / terminal) never
          age.
        """
        graph = portfolio.dependency_graph()
        entries = portfolio.entries()
        rnd = portfolio._begin_round(activate=bool(entries))

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

        # Contention key per eligible workflow (lower = more preferred). Priority (via the
        # aging-adjusted effective rank) dominates, then dependency depth (upstream first).
        # Everything below is deterministic — no wall-clock, identity, dict order, or randomness.
        rank = {e.instance_id: self._policy.effective_rank(e) for e in eligible}
        depth = {e.instance_id: graph.depth(e.instance_id) for e in eligible}

        def contention_key(e: PortfolioWorkflowEntry):
            return (rank[e.instance_id], depth[e.instance_id])

        tier_key = min(contention_key(e) for e in eligible)
        tier = [e for e in eligible if contention_key(e) == tier_key]
        tier_ids = {e.instance_id for e in tier}

        # SWRR fairness WITHIN the tier: accrue weight, select the workflow most owed
        # service, then charge it the tier's total weight. Proportional and starvation-free.
        for e in tier:
            e.fair_credit += e.weight
        tier_weight = sum(e.weight for e in tier)
        selected = min(
            tier,
            key=lambda e: (-e.fair_credit, e.registration_sequence, e.instance_id),
        )

        # Full deterministic ordering of the eligible set for the result (best first).
        ordered = sorted(
            eligible,
            key=lambda e: (
                rank[e.instance_id],
                depth[e.instance_id],
                -e.fair_credit,
                e.registration_sequence,
                e.instance_id,
            ),
        )

        reason_obj = SelectionReason(
            instance_id=selected.instance_id,
            effective_rank=rank[selected.instance_id],
            base_priority=selected.priority.value,
            age=selected.age,
            dependency_depth=depth[selected.instance_id],
            fairness_credit=selected.fair_credit,
            registration_sequence=selected.registration_sequence,
        )

        # SWRR cost (charge the selected the tier total) + aging update happen AFTER the
        # reason snapshot so the reason reflects the state the selection turned on.
        selected.fair_credit -= tier_weight
        for e in eligible:
            if e.instance_id == selected.instance_id:
                e.age = 0                     # served this round — not starved
            elif e.instance_id not in tier_ids:
                # Eligible but held BELOW the top tier -> age it toward contention (bounded).
                e.age = min(e.age + 1, self._policy.aging_cap)
            # else: a non-selected tier member — SWRR will serve it in turn, so it never ages.

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

    # -- batch selection seam (H22-D concurrent admission) ------------------
    def plan_batch(
        self,
        portfolio: WorkflowPortfolio,
        *,
        max_concurrency: int = 1,
        admit=None,
    ) -> BatchPlan:
        """Select a mutually-compatible *batch* of eligible workflows for concurrent quanta.

        This is the additive H22-D seam over the *same* deterministic H22-B fairness core the
        single-quantum :meth:`step` uses. It advances one logical round, classifies every
        workflow, and then repeatedly runs a single smooth-weighted-round-robin (SWRR) tier pick
        — the identical mechanism as :meth:`step` — asking the caller-supplied ``admit``
        predicate whether the fairness winner may take a concurrent slot. A candidate the
        predicate rejects is **deferred** (removed from this round's contention, but **never
        charged SWRR credit and never aged as served**, so its starvation protection is fully
        preserved — a resource-conflicted workflow stays exactly as owed as before); the scan
        then continues to the next fairness-preferred candidate. Selection stops when
        ``max_concurrency`` slots are filled or no eligible candidate remains.

        Fairness is committed for exactly the admitted set: each admission performs one real SWRR
        pick (accrue each live tier member's weight, charge the winner the tier's total weight,
        reset the winner's age), and — after the batch — every eligible workflow held strictly
        *below* the lowest served tier ages (bounded by ``aging_cap``), exactly as in a
        single-quantum round. **At ``max_concurrency == 1`` with an always-admit predicate the
        committed fairness/aging state is identical to :meth:`step`** (proven by test), so
        concurrency=1 is semantically bounded H22-B execution.

        The scheduler NEVER touches execution here — no ``advance_workflow``, no provider, no
        governance. It returns an immutable :class:`BatchPlan`; the caller executes the admitted
        workflows' quanta (each an unchanged, indivisible H22-A quantum) however it likes. The
        ``admit`` predicate is opaque coordination glue: the scheduler passes its ``reason`` /
        ``detail`` straight into the plan and interprets neither.
        """
        if not isinstance(max_concurrency, int) or isinstance(max_concurrency, bool) or max_concurrency < 1:
            raise ValueError("max_concurrency must be a positive integer")
        admit = admit or _always_admit
        graph = portfolio.dependency_graph()
        entries = portfolio.entries()
        rnd = portfolio._begin_round(activate=bool(entries))

        if not entries:
            return BatchPlan(
                portfolio_id=portfolio.portfolio_id, round=rnd, admitted=(),
                admitted_reasons={}, deferred=(), capacity_deferred=(), ordered=(),
                classifications=(), stop_reason=PortfolioStepReason.EMPTY_PORTFOLIO.value,
            )

        classification = self.classify(portfolio)
        classifications = tuple((e.instance_id, c.value) for e, c in classification)
        eligible = [e for e, c in classification if c is WorkflowEligibility.ELIGIBLE]

        if not eligible:
            all_terminal = all(c is WorkflowEligibility.TERMINAL for _, c in classification)
            if all_terminal:
                portfolio._mark_completed()
                stop = PortfolioStepReason.ALL_TERMINAL
            else:
                stop = PortfolioStepReason.NO_ELIGIBLE_WORKFLOW
            return BatchPlan(
                portfolio_id=portfolio.portfolio_id, round=rnd, admitted=(),
                admitted_reasons={}, deferred=(), capacity_deferred=(), ordered=(),
                classifications=classifications, stop_reason=stop.value,
            )

        # Per-round contention keys, snapshotted on the round's starting state (lower = more
        # preferred). Priority (via aging-adjusted effective rank) dominates, then dependency
        # depth. Deterministic — no wall-clock, identity, dict order, or randomness.
        rank = {e.instance_id: self._policy.effective_rank(e) for e in eligible}
        depth = {e.instance_id: graph.depth(e.instance_id) for e in eligible}

        def contention_key(e: PortfolioWorkflowEntry) -> Tuple[int, int]:
            return (rank[e.instance_id], depth[e.instance_id])

        ordered = tuple(
            e.instance_id
            for e in sorted(
                eligible,
                key=lambda e: (
                    rank[e.instance_id], depth[e.instance_id], -e.fair_credit,
                    e.registration_sequence, e.instance_id,
                ),
            )
        )

        pool: List[PortfolioWorkflowEntry] = list(eligible)
        admitted: List[str] = []
        admitted_reasons: Dict[str, SelectionReason] = {}
        deferred: List[Tuple[str, str, Dict[str, object]]] = []
        served_keys: List[Tuple[int, int]] = []

        while pool and len(admitted) < max_concurrency:
            tkey = min(contention_key(e) for e in pool)
            tier = [e for e in pool if contention_key(e) == tkey]
            # SWRR order within the tier by the SAME key step() selects on (max post-accrual
            # credit, then registration sequence, then id). post-accrual = current + weight.
            swrr_order = sorted(
                tier,
                key=lambda e: (-(e.fair_credit + e.weight), e.registration_sequence, e.instance_id),
            )
            winner: Optional[PortfolioWorkflowEntry] = None
            for cand in swrr_order:
                decision = admit(cand)
                if decision.admitted:
                    winner = cand
                    break
                # Deferred: not served. Leaves this round's contention but is neither charged
                # SWRR credit nor age-reset — its owed-ness is preserved for the next round.
                deferred.append(
                    (cand.instance_id, decision.reason or "DEFERRED", dict(decision.detail or {}))
                )
                pool.remove(cand)
            if winner is None:
                # The whole top tier was inadmissible this round; the pool shrank, so the next
                # loop iteration moves on to the next tier. No accrual, no charge occurred.
                continue
            # Commit exactly ONE real SWRR pick over the LIVE tier (post-deferral removals).
            live_tier = [e for e in pool if contention_key(e) == tkey]
            for e in live_tier:
                e.fair_credit += e.weight
            tier_weight = sum(e.weight for e in live_tier)
            # SelectionReason snapshot: post-accrual, pre-charge, pre-age-reset — the exact
            # instant step() snapshots its reason.
            admitted_reasons[winner.instance_id] = SelectionReason(
                instance_id=winner.instance_id,
                effective_rank=rank[winner.instance_id],
                base_priority=winner.priority.value,
                age=winner.age,
                dependency_depth=depth[winner.instance_id],
                fairness_credit=winner.fair_credit,
                registration_sequence=winner.registration_sequence,
            )
            winner.fair_credit -= tier_weight
            admitted.append(winner.instance_id)
            served_keys.append(tkey)
            pool.remove(winner)

        # Whatever remains in the pool was never evaluated because the concurrency limit filled
        # first — capacity-deferred. It keeps its fairness credit (owed) and is not charged.
        capacity_deferred = tuple(e.instance_id for e in pool)

        # Aging (cross-tier starvation prevention): the admitted reset to 0; every eligible
        # workflow held strictly BELOW the lowest served tier ages (bounded). Tier-peers of a
        # served tier never age (SWRR owes them). Identical to step() when one workflow is served.
        admitted_set = set(admitted)
        if served_keys:
            worst_served = max(served_keys)
            for e in eligible:
                if e.instance_id in admitted_set:
                    e.age = 0
                elif contention_key(e) > worst_served:
                    e.age = min(e.age + 1, self._policy.aging_cap)
                # else: a tier-peer at/above the served frontier — unchanged.

        stop_reason = None
        if not admitted:
            # Eligible work exists but nothing was concurrently admissible (all deferred by the
            # predicate). Deterministically quiescent — the caller must not busy-loop.
            stop_reason = PortfolioStepReason.NO_ELIGIBLE_WORKFLOW.value

        return BatchPlan(
            portfolio_id=portfolio.portfolio_id, round=rnd, admitted=tuple(admitted),
            admitted_reasons=admitted_reasons, deferred=tuple(deferred),
            capacity_deferred=capacity_deferred, ordered=ordered,
            classifications=classifications, stop_reason=stop_reason,
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
