"""
Plan Validity & Assumption Tracking (H13)
=========================================

Elevates the runtime from *replan-whenever-something-changes* (H12) to
*replan-only-when-the-reasoning-behind-the-plan-is-no-longer-valid*.

Every plan explicitly declares the **assumptions** it depends on
(e.g. "database reachable", "approval obtained", "credentials valid").
After each step the runtime evaluates observations **against those
assumptions** and decides:

    Goal → Plan + Assumptions → Observation → Assumption Evaluation
        → Plan Valid?  →  Continue | Replan | Abort | Complete

The runtime reasons about *assumptions*, not raw observations.  An
observation that changes nothing about the assumptions does **not** trigger
replanning.  When an assumption fails, only the *future* steps that depend
on it are reconsidered — completed history and unaffected steps are
preserved.

Integration is strategy-agnostic and additive.  This module does **not**
modify the replanning engine, RunBudget, governance, authorization,
ActionGate, TAP, routing, tool execution, or LLM providers.  It plugs into
the seams ``ReplanningRunner`` already exposes:

* a :class:`~agentic.agentic_framework.replanning.ReplanPolicy`
  (:class:`AssumptionAwareReplanPolicy`) that decides CONTINUE/REVISE/
  ABORT/COMPLETE from plan validity, and
* a replanner strategy (:func:`selective_replanner`) that revises only the
  affected future steps.

Both cooperate through a shared :class:`AssumptionContext`.  Assumption
evaluation runs under the same shared ``RunBudget`` — no new budget objects
are created.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Set, Tuple

from agentic.agentic_framework.replanning import (
    Plan,
    PlanStep,
    PlanObservation,
    ObservationStatus,
    ReplanDecision,
    RuleBasedReplanner,
    DeterministicReplanPolicy,
    ReplanningRunner,
)

__all__ = [
    "AssumptionState",
    "PlanValidity",
    "AssumptionTransition",
    "PlanAssumption",
    "AssumptionRegistry",
    "AssumptionDependency",
    "AssumptionDependencyGraph",
    "AssumptionObservation",
    "AssumptionEvaluation",
    "AssumptionEvaluator",
    "RuleBasedAssumptionEvaluator",
    "PlanValidityResult",
    "PlanValidityEvaluator",
    "ValidityTraceEntry",
    "PlanValidityTrace",
    "AssumptionContext",
    "AssumptionAwareReplanPolicy",
    "selective_replanner",
    "build_assumption_aware_runner",
    "format_assumptions",
    "format_validity_trace",
]


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class AssumptionState:
    """Lifecycle state of a planning assumption."""

    VALID = "VALID"          # believed true, not yet tested this run
    INVALID = "INVALID"      # observed to be false
    UNKNOWN = "UNKNOWN"      # not yet established (e.g. a newly required one)
    SATISFIED = "SATISFIED"  # actively confirmed true by an observation
    EXPIRED = "EXPIRED"      # was valid but its validity window has lapsed


#: States that make dependent future steps unsafe to execute as-is.
_FAILED_STATES = {AssumptionState.INVALID, AssumptionState.EXPIRED}
#: States that are safe to proceed on.
_OK_STATES = {AssumptionState.VALID, AssumptionState.SATISFIED}


class PlanValidity:
    """Outcome of a plan-validity evaluation."""

    PLAN_VALID = "PLAN_VALID"
    PLAN_INVALID = "PLAN_INVALID"
    PLAN_PARTIALLY_VALID = "PLAN_PARTIALLY_VALID"
    PLAN_COMPLETED = "PLAN_COMPLETED"
    PLAN_IMPOSSIBLE = "PLAN_IMPOSSIBLE"


# ---------------------------------------------------------------------------
# Assumption model (append-only)
# ---------------------------------------------------------------------------
@dataclass
class AssumptionTransition:
    """One recorded state change of an assumption (append-only)."""

    from_state: str
    to_state: str
    reason: str = ""
    evidence: List[str] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_state": self.from_state,
            "to_state": self.to_state,
            "reason": self.reason,
            "evidence": list(self.evidence),
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


@dataclass
class PlanAssumption:
    """An explicit assumption a plan depends on.

    Current ``state`` is the latest value; ``history`` is the append-only
    transition trail.  Assumptions themselves are never deleted.
    """

    assumption_id: str
    description: str
    category: str = "general"
    state: str = AssumptionState.VALID
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)
    mandatory: bool = False       # a critical precondition
    recoverable: bool = True      # can a failure be repaired by replanning?
    created_at: float = 0.0
    last_validated_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    history: List[AssumptionTransition] = field(default_factory=list)

    def transition(
        self,
        new_state: str,
        *,
        reason: str = "",
        evidence: Optional[List[str]] = None,
        confidence: Optional[float] = None,
        timestamp: float = 0.0,
    ) -> AssumptionTransition:
        """Record a state change (append-only).  Returns the transition."""
        t = AssumptionTransition(
            from_state=self.state,
            to_state=new_state,
            reason=reason,
            evidence=list(evidence or []),
            confidence=confidence if confidence is not None else self.confidence,
            timestamp=timestamp,
        )
        self.history.append(t)
        self.state = new_state
        if evidence:
            self.evidence.extend(evidence)
        if confidence is not None:
            self.confidence = confidence
        self.last_validated_at = timestamp
        return t

    @property
    def failed(self) -> bool:
        return self.state in _FAILED_STATES

    def to_dict(self) -> Dict[str, Any]:
        return {
            "assumption_id": self.assumption_id,
            "description": self.description,
            "category": self.category,
            "state": self.state,
            "confidence": self.confidence,
            "evidence": list(self.evidence),
            "mandatory": self.mandatory,
            "recoverable": self.recoverable,
            "created_at": self.created_at,
            "last_validated_at": self.last_validated_at,
            "history": [t.to_dict() for t in self.history],
        }


class AssumptionRegistry:
    """Append-only collection of assumptions keyed by id."""

    def __init__(self, assumptions: Optional[List[PlanAssumption]] = None) -> None:
        self._assumptions: Dict[str, PlanAssumption] = {}
        for a in assumptions or []:
            self.add(a)

    def add(self, assumption: PlanAssumption) -> PlanAssumption:
        if assumption.assumption_id in self._assumptions:
            raise ValueError(f"assumption '{assumption.assumption_id}' already registered")
        self._assumptions[assumption.assumption_id] = assumption
        return assumption

    def has(self, assumption_id: str) -> bool:
        return assumption_id in self._assumptions

    def get(self, assumption_id: str) -> Optional[PlanAssumption]:
        return self._assumptions.get(assumption_id)

    def all(self) -> List[PlanAssumption]:
        return list(self._assumptions.values())

    def by_state(self, *states: str) -> List[PlanAssumption]:
        return [a for a in self._assumptions.values() if a.state in states]

    def failed(self) -> List[PlanAssumption]:
        return [a for a in self._assumptions.values() if a.failed]

    def to_dict(self) -> Dict[str, Any]:
        return {aid: a.to_dict() for aid, a in self._assumptions.items()}


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------
@dataclass
class AssumptionDependency:
    """A declared dependency of a plan step on an assumption."""

    step_id: str
    assumption_id: str


class AssumptionDependencyGraph:
    """Maps plan steps ↔ the assumptions they depend on.

    Reads each step's ``metadata['assumptions']`` list (so ``PlanStep`` does
    not need modifying) and/or explicit edges added via :meth:`add`.
    """

    def __init__(self) -> None:
        self._step_to_assumptions: Dict[str, Set[str]] = {}

    @classmethod
    def from_plan(cls, plan: Plan) -> "AssumptionDependencyGraph":
        graph = cls()
        for step in plan.history + plan.future:
            for aid in step.metadata.get("assumptions", []) or []:
                graph.add(step.step_id, aid)
        return graph

    def add(self, step_id: str, assumption_id: str) -> None:
        self._step_to_assumptions.setdefault(step_id, set()).add(assumption_id)

    def assumptions_for_step(self, step_id: str) -> Set[str]:
        return set(self._step_to_assumptions.get(step_id, set()))

    def steps_depending_on(self, assumption_id: str) -> Set[str]:
        return {
            sid for sid, aids in self._step_to_assumptions.items()
            if assumption_id in aids
        }

    def sync_step(self, step: PlanStep) -> None:
        """Refresh edges for *step* from its metadata (for inserted steps)."""
        for aid in step.metadata.get("assumptions", []) or []:
            self.add(step.step_id, aid)


# ---------------------------------------------------------------------------
# Observation that carries assumption signals
# ---------------------------------------------------------------------------
@dataclass
class AssumptionObservation(PlanObservation):
    """A :class:`PlanObservation` that also reports assumption effects.

    ``assumption_signals`` maps assumption ids to their newly-observed state
    (e.g. ``{"db_reachable": "INVALID"}``).  ``introduces`` lists brand-new
    required assumptions the observation revealed.  Being a subclass, it
    flows unchanged through the existing replanning machinery.
    """

    assumption_signals: Dict[str, str] = field(default_factory=dict)
    introduces: List[PlanAssumption] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Assumption evaluation — which assumptions were tested / changed / unchanged
# ---------------------------------------------------------------------------
@dataclass
class AssumptionEvaluation:
    """Result of evaluating one observation against the assumptions."""

    tested: Set[str] = field(default_factory=set)
    changed: Dict[str, str] = field(default_factory=dict)      # id -> new state
    unchanged: Set[str] = field(default_factory=set)
    introduced: List[str] = field(default_factory=list)        # new assumption ids

    def affects_assumptions(self) -> bool:
        return bool(self.changed) or bool(self.introduced)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tested": sorted(self.tested),
            "changed": dict(self.changed),
            "unchanged": sorted(self.unchanged),
            "introduced": list(self.introduced),
        }


class AssumptionEvaluator(Protocol):
    """Maps an observation to assumption effects (deterministic)."""

    def evaluate(
        self,
        observation: PlanObservation,
        executed_step: Optional[PlanStep],
        registry: AssumptionRegistry,
        graph: AssumptionDependencyGraph,
    ) -> AssumptionEvaluation:
        ...


class RuleBasedAssumptionEvaluator:
    """Deterministic evaluator.

    Precedence:

    1. **Explicit signals** — an :class:`AssumptionObservation`'s
       ``assumption_signals`` set the new state directly (and ``introduces``
       adds new assumptions).  This is the precise, test-friendly path.
    2. **Heuristic fallback** — for a plain observation with no signals, the
       assumptions the *executed step* depends on are marked ``SATISFIED``
       on success or ``INVALID`` on failure/blocked.

    An observation that neither carries signals nor tests any step
    assumptions changes nothing — and therefore triggers no replanning.
    """

    def evaluate(
        self,
        observation: PlanObservation,
        executed_step: Optional[PlanStep],
        registry: AssumptionRegistry,
        graph: AssumptionDependencyGraph,
    ) -> AssumptionEvaluation:
        step_assumptions = (
            graph.assumptions_for_step(executed_step.step_id)
            if executed_step is not None else set()
        )
        signals: Dict[str, str] = dict(getattr(observation, "assumption_signals", {}) or {})
        introduces: List[PlanAssumption] = list(getattr(observation, "introduces", []) or [])

        tested: Set[str] = set(step_assumptions) | set(signals.keys())
        changed: Dict[str, str] = {}

        # 1. Explicit signals.
        for aid, new_state in signals.items():
            existing = registry.get(aid)
            if existing is not None and existing.state != new_state:
                changed[aid] = new_state

        # 2. Heuristic fallback for the executed step's assumptions.
        if not signals and executed_step is not None and step_assumptions:
            outcome = (
                AssumptionState.INVALID
                if observation.status in (ObservationStatus.FAILURE, ObservationStatus.BLOCKED)
                else AssumptionState.SATISFIED
            )
            for aid in step_assumptions:
                a = registry.get(aid)
                if a is not None and a.state != outcome:
                    changed[aid] = outcome

        introduced_ids = [a.assumption_id for a in introduces]
        all_ids = {a.assumption_id for a in registry.all()} | set(introduced_ids)
        unchanged = all_ids - set(changed.keys()) - set(introduced_ids)
        return AssumptionEvaluation(
            tested=tested, changed=changed, unchanged=unchanged, introduced=introduced_ids
        )


# ---------------------------------------------------------------------------
# Plan validity evaluator — deterministic
# ---------------------------------------------------------------------------
@dataclass
class PlanValidityResult:
    """Deterministic verdict on the plan's validity."""

    validity: str
    affected_steps: List[PlanStep] = field(default_factory=list)
    failed_assumptions: List[str] = field(default_factory=list)
    required_assumptions: List[str] = field(default_factory=list)  # unsatisfied new mandatory
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validity": self.validity,
            "affected_steps": [s.step_id for s in self.affected_steps],
            "failed_assumptions": list(self.failed_assumptions),
            "required_assumptions": list(self.required_assumptions),
            "reason": self.reason,
        }


class PlanValidityEvaluator:
    """Computes plan validity from assumption states + the dependency graph.

    Deterministic.  Selective: an assumption that fails but is only depended
    on by *completed* steps does not invalidate the plan — only future steps
    that depend on failed assumptions are affected.
    """

    def evaluate(
        self,
        plan: Plan,
        registry: AssumptionRegistry,
        graph: AssumptionDependencyGraph,
        *,
        exclude_step_id: Optional[str] = None,
    ) -> PlanValidityResult:
        future = [s for s in plan.future if s.step_id != exclude_step_id]

        failed = registry.failed()
        failed_ids = {a.assumption_id for a in failed}

        # Mandatory + unrecoverable failure → impossible.
        unrecoverable = [a for a in failed if a.mandatory and not a.recoverable]
        if unrecoverable:
            return PlanValidityResult(
                validity=PlanValidity.PLAN_IMPOSSIBLE,
                affected_steps=list(future),
                failed_assumptions=sorted(failed_ids),
                reason=(
                    "mandatory unrecoverable assumption(s) failed: "
                    + ", ".join(a.assumption_id for a in unrecoverable)
                ),
            )

        # Newly-required, not-yet-satisfied mandatory assumptions.
        required = [
            a for a in registry.all()
            if a.mandatory
            and a.state in (AssumptionState.UNKNOWN, AssumptionState.INVALID)
            and a.metadata.get("introduced")
        ]
        required_ids = [a.assumption_id for a in required]

        # Future steps whose assumptions have failed.
        affected = [
            s for s in future
            if failed_ids & graph.assumptions_for_step(s.step_id)
        ]

        if not failed_ids and not required_ids:
            if not future and not plan.failed_steps():
                return PlanValidityResult(
                    validity=PlanValidity.PLAN_COMPLETED, reason="all steps completed"
                )
            return PlanValidityResult(
                validity=PlanValidity.PLAN_VALID,
                reason="all assumptions valid",
            )

        # Failed assumptions but nothing in the future depends on them, and
        # no new mandatory requirement → the plan is still valid (selective).
        if not affected and not required_ids:
            return PlanValidityResult(
                validity=PlanValidity.PLAN_VALID,
                failed_assumptions=sorted(failed_ids),
                reason="failed assumptions affect no future steps",
            )

        # Something is affected — full vs partial.
        if affected and len(affected) == len(future) and not required_ids:
            validity = PlanValidity.PLAN_INVALID
            reason = "all remaining steps depend on failed assumptions"
        else:
            validity = PlanValidity.PLAN_PARTIALLY_VALID
            reason = "some remaining steps require revision"
        return PlanValidityResult(
            validity=validity,
            affected_steps=affected,
            failed_assumptions=sorted(failed_ids),
            required_assumptions=required_ids,
            reason=reason,
        )


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------
@dataclass
class ValidityTraceEntry:
    """One iteration's assumption-lifecycle record."""

    iteration: int
    step_id: str
    observation: Dict[str, Any]
    evaluation: Dict[str, Any]
    transitions: List[Dict[str, Any]]
    validity: str
    affected_steps: List[str]
    reason: str
    decision: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "step_id": self.step_id,
            "observation": self.observation,
            "evaluation": self.evaluation,
            "transitions": self.transitions,
            "validity": self.validity,
            "affected_steps": self.affected_steps,
            "reason": self.reason,
            "decision": self.decision,
        }


class PlanValidityTrace:
    """Append-only log of assumption evaluations and validity decisions."""

    def __init__(self) -> None:
        self.entries: List[ValidityTraceEntry] = []

    def record(self, entry: ValidityTraceEntry) -> None:
        self.entries.append(entry)

    def to_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self.entries]


# ---------------------------------------------------------------------------
# Context — shared state between policy and strategy
# ---------------------------------------------------------------------------
class AssumptionContext:
    """Shared assumption state threaded through a replanning run.

    Holds the registry, dependency graph, evaluators, and the running trace.
    The :class:`AssumptionAwareReplanPolicy` writes the latest validity
    result here during ``decide()``; :func:`selective_replanner` reads it
    during ``revise()``.
    """

    def __init__(
        self,
        registry: AssumptionRegistry,
        graph: AssumptionDependencyGraph,
        *,
        evaluator: Optional[AssumptionEvaluator] = None,
        validity_evaluator: Optional[PlanValidityEvaluator] = None,
    ) -> None:
        self.registry = registry
        self.graph = graph
        self.evaluator = evaluator or RuleBasedAssumptionEvaluator()
        self.validity_evaluator = validity_evaluator or PlanValidityEvaluator()
        self.trace = PlanValidityTrace()
        self.last_validity: Optional[PlanValidityResult] = None
        self._iteration = 0

    def evaluate(
        self, plan: Plan, executed_step: Optional[PlanStep], observation: PlanObservation
    ) -> Tuple[AssumptionEvaluation, PlanValidityResult, List[AssumptionTransition]]:
        """Evaluate the observation against assumptions and compute validity.

        Applies (append-only) assumption transitions, registers any newly
        introduced assumptions and their step dependencies, then computes the
        deterministic plan-validity verdict.  Does not create or reset any
        RunBudget.
        """
        now = float(getattr(observation, "timestamp", self._iteration) or self._iteration)
        evaluation = self.evaluator.evaluate(observation, executed_step, self.registry, self.graph)

        transitions: List[AssumptionTransition] = []

        # 1. Register newly introduced assumptions (append-only).
        for new_a in getattr(observation, "introduces", []) or []:
            if not self.registry.has(new_a.assumption_id):
                new_a.metadata["introduced"] = True
                if new_a.created_at == 0.0:
                    new_a.created_at = now
                self.registry.add(new_a)
                # Wire any declared step dependencies.
                for sid in new_a.metadata.get("steps", []) or []:
                    self.graph.add(sid, new_a.assumption_id)

        # 2. Apply state changes (append-only transitions).
        for aid, new_state in evaluation.changed.items():
            a = self.registry.get(aid)
            if a is not None and a.state != new_state:
                t = a.transition(
                    new_state,
                    reason=f"observation: {observation.summary}" if observation.summary else "observation",
                    evidence=list(observation.evidence),
                    confidence=observation.confidence,
                    timestamp=now,
                )
                transitions.append(t)

        # 3. Compute validity over the FUTURE (excluding the executed step).
        exclude = executed_step.step_id if executed_step is not None else None
        validity = self.validity_evaluator.evaluate(
            plan, self.registry, self.graph, exclude_step_id=exclude
        )
        self.last_validity = validity
        return evaluation, validity, transitions


# ---------------------------------------------------------------------------
# Assumption-aware decision policy (implements ReplanPolicy)
# ---------------------------------------------------------------------------
class AssumptionAwareReplanPolicy:
    """A :class:`ReplanPolicy` that decides from *plan validity*.

    Completion / impossibility from the raw observation still take
    precedence (a goal reported done is done); otherwise the CONTINUE vs
    REVISE choice is made **only** from whether assumptions invalidate the
    plan.  An observation that changes no assumption ⇒ CONTINUE (no
    replanning), even if it carried new constraints.
    """

    def __init__(
        self,
        context: AssumptionContext,
        *,
        base_policy: Optional[DeterministicReplanPolicy] = None,
    ) -> None:
        self.context = context
        self.base_policy = base_policy or DeterministicReplanPolicy()

    def decide(
        self, goal: str, plan: Plan, observation: PlanObservation
    ) -> Tuple[str, str]:
        executed_step = plan.next_step()  # the step that just ran (not yet marked)
        evaluation, validity, transitions = self.context.evaluate(
            plan, executed_step, observation
        )

        # Raw-observation completion / impossibility take precedence.
        base_decision, base_reason = self.base_policy.decide(goal, plan, observation)
        if base_decision == ReplanDecision.COMPLETE:
            decision, reason = ReplanDecision.COMPLETE, base_reason
        elif base_decision == ReplanDecision.ABORT:
            decision, reason = ReplanDecision.ABORT, base_reason
        elif validity.validity == PlanValidity.PLAN_IMPOSSIBLE:
            decision, reason = ReplanDecision.ABORT, validity.reason
        elif validity.validity == PlanValidity.PLAN_COMPLETED:
            decision, reason = ReplanDecision.COMPLETE, validity.reason
        elif validity.validity in (
            PlanValidity.PLAN_INVALID,
            PlanValidity.PLAN_PARTIALLY_VALID,
        ):
            decision, reason = ReplanDecision.REVISE, validity.reason
        else:  # PLAN_VALID
            decision, reason = ReplanDecision.CONTINUE, validity.reason

        # Record the assumption-lifecycle trace entry.
        self.context.trace.record(ValidityTraceEntry(
            iteration=self.context._iteration,
            step_id=executed_step.step_id if executed_step else "",
            observation=observation.to_dict(),
            evaluation=evaluation.to_dict(),
            transitions=[t.to_dict() for t in transitions],
            validity=validity.validity,
            affected_steps=[s.step_id for s in validity.affected_steps],
            reason=reason,
            decision=decision,
        ))
        self.context._iteration += 1
        return decision, reason


# ---------------------------------------------------------------------------
# Selective replanner strategy
# ---------------------------------------------------------------------------
def selective_replanner(
    context: AssumptionContext,
    *,
    repair: Optional[
        Callable[[Plan, PlanObservation, PlanValidityResult], List[PlanStep]]
    ] = None,
) -> RuleBasedReplanner:
    """A replanner that revises **only** the affected future steps.

    Reads the latest :class:`PlanValidityResult` from *context* and:

    * preserves future steps that do **not** depend on failed assumptions;
    * for each unsatisfied newly-required mandatory assumption, inserts a
      ``satisfy_<id>`` step (declaring that assumption as a dependency);
    * re-queues the affected steps after the satisfy steps (or replaces them
      via the optional *repair* callback);
    * never touches completed history.
    """

    def strategy(plan: Plan, observation: PlanObservation) -> List[PlanStep]:
        result = context.last_validity
        future = list(plan.future)
        if result is None:
            return future

        affected_ids = {s.step_id for s in result.affected_steps}
        preserved = [s for s in future if s.step_id not in affected_ids]
        affected = [s for s in future if s.step_id in affected_ids]

        # Satisfy steps for newly-required mandatory assumptions.
        satisfy_steps: List[PlanStep] = []
        for aid in result.required_assumptions:
            a = context.registry.get(aid)
            desc = a.description if a is not None else aid
            step = PlanStep(
                step_id=f"satisfy_{aid}",
                objective=f"satisfy assumption: {desc}",
                action=f"satisfy assumption {aid}",
                metadata={"assumptions": [aid], "inserted": True},
            )
            context.graph.sync_step(step)
            satisfy_steps.append(step)

        if repair is not None:
            replacement = list(repair(plan, observation, result))
        else:
            # Default: re-queue the affected steps after their assumption is
            # re-established (satisfy steps run first).
            replacement = affected

        new_future = satisfy_steps + replacement + preserved
        # Keep the dependency graph aware of any inserted steps.
        for s in new_future:
            context.graph.sync_step(s)
        return new_future

    return RuleBasedReplanner(strategy)


# ---------------------------------------------------------------------------
# Convenience builder
# ---------------------------------------------------------------------------
def build_assumption_aware_runner(
    agent: Any,
    context: AssumptionContext,
    *,
    repair: Optional[
        Callable[[Plan, PlanObservation, PlanValidityResult], List[PlanStep]]
    ] = None,
    observation_builder: Optional[Any] = None,
    max_iterations: int = 12,
    max_revisions: int = 6,
    run_budget: Optional[Any] = None,
    budget_policy: Optional[Any] = None,
    stagnation: Optional[Any] = None,
    on_step: Optional[Any] = None,
) -> ReplanningRunner:
    """Wire an assumption-aware :class:`ReplanningRunner`.

    Composes the existing runner with an :class:`AssumptionAwareReplanPolicy`
    and a :func:`selective_replanner`, sharing *context*.  The replanning
    engine, RunBudget and governance are used unmodified.
    """
    return ReplanningRunner(
        agent,
        policy=AssumptionAwareReplanPolicy(context),
        replanner=selective_replanner(context, repair=repair),
        observation_builder=observation_builder,
        max_iterations=max_iterations,
        max_revisions=max_revisions,
        run_budget=run_budget,
        budget_policy=budget_policy,
        stagnation=stagnation,
        on_step=on_step,
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_assumptions(registry: AssumptionRegistry) -> str:
    lines = ["Assumptions", "-" * 48]
    for a in registry.all():
        flag = " [mandatory]" if a.mandatory else ""
        lines.append(
            f"  {a.assumption_id}: {a.state:<9} ({a.category}) — {a.description}{flag}"
        )
        for t in a.history:
            lines.append(f"      {t.from_state} → {t.to_state}  @{t.timestamp}  {t.reason}")
    return "\n".join(lines)


def format_validity_trace(context: AssumptionContext) -> str:
    lines = ["Plan validity trace", "=" * 60]
    for e in context.trace.entries:
        lines.append(f"  iter {e.iteration}: step={e.step_id}")
        lines.append(
            f"    evaluation: changed={e.evaluation['changed']} "
            f"introduced={e.evaluation['introduced']}"
        )
        lines.append(f"    validity:   {e.validity} — {e.reason}")
        if e.affected_steps:
            lines.append(f"    affected:   {e.affected_steps}")
        lines.append(f"    decision:   {e.decision}")
    return "\n".join(lines)
