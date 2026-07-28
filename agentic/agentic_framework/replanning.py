"""
Observation-Driven Replanning (H12)
===================================

Bounded *adaptive* autonomous execution.  Where the iterate-until-done loop
(``iterate_loop.py``) re-runs the same instruction until a checker says
done, this module lets the runtime **change its future plan based on what
it observes** — while never rewriting execution history and staying inside
the shared :class:`RunBudget` from H11.

The execution model::

    Goal → Plan → Execute Step → Observation → Evaluate
                                                   │
                        ┌──────────────┬───────────┼───────────┐
                     CONTINUE        REVISE      ABORT       COMPLETE
                   (plan valid)  (change future)(impossible)(goal met)

Three things are kept strictly separate:

* **History** — completed / failed / removed steps.  Immutable.  Revision
  never touches them.
* **Future** — pending steps.  The replanning engine may reorder, remove,
  insert, or modify *only these*.
* **Decision** — a deterministic verdict (CONTINUE / REVISE / ABORT /
  COMPLETE) derived solely from the structured :class:`PlanObservation`.

This module adds replanning only.  It does not modify governance,
authorization, ActionGate, TAP, routing, tool execution, LLM providers, or
the budget implementation.  Execution still flows through the governed
``run_with_trace()`` path; planning and execution consume the same
:class:`RunBudget`.

Scope excluded (by design): parallel agents, graph orchestration,
negotiation, shared memory, distributed planning, learning / RL.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple

from agentic.agentic_framework.streaming_events import RUN_COMPLETED, TEXT_CHUNK
from agentic.agentic_framework.tracing import AgentRunTrace
from agentic.agentic_framework.run_budget import (
    RunBudget,
    BudgetExhausted,
    attach_run_budget,
)

__all__ = [
    "ObservationStatus",
    "PlanStepState",
    "ReplanDecision",
    "StopReason",
    "PlanObservation",
    "PlanStep",
    "Plan",
    "PlanRevision",
    "ReplanPolicy",
    "DeterministicReplanPolicy",
    "Replanner",
    "RuleBasedReplanner",
    "ObservationBuilder",
    "ScriptedObservationBuilder",
    "DefaultObservationBuilder",
    "StagnationConfig",
    "StagnationDetector",
    "ReplanningResult",
    "ReplanningRunner",
    "format_plan",
    "format_replanning_trace",
]


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class ObservationStatus:
    """Status of a structured observation."""

    SUCCESS = "success"      # step achieved its expected outcome
    PARTIAL = "partial"      # some progress, plan still valid
    FAILURE = "failure"      # step failed; future likely needs to change
    BLOCKED = "blocked"      # governance / tool blocked the step
    CONSTRAINT = "constraint"  # a new restriction was discovered
    IMPOSSIBLE = "impossible"  # the goal cannot be achieved


class PlanStepState:
    """Lifecycle state of a plan step."""

    PENDING = "pending"       # not yet executed (future)
    COMPLETED = "completed"   # executed successfully (immutable history)
    FAILED = "failed"         # executed, did not succeed (immutable history)
    REMOVED = "removed"       # dropped during revision (immutable history)


class ReplanDecision:
    """Deterministic verdict produced after each observation."""

    CONTINUE = "CONTINUE"   # current plan remains valid
    REVISE = "REVISE"       # future steps should change
    ABORT = "ABORT"         # goal is impossible
    COMPLETE = "COMPLETE"   # goal achieved


class StopReason:
    """Explicit, deterministic termination reasons."""

    GOAL_COMPLETED = "GOAL_COMPLETED"
    GOAL_IMPOSSIBLE = "GOAL_IMPOSSIBLE"
    NO_VALID_PLAN = "NO_VALID_PLAN"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    ITERATION_LIMIT = "ITERATION_LIMIT"
    REPEATED_FAILURES = "REPEATED_FAILURES"
    NO_PROGRESS = "NO_PROGRESS"
    STAGNATION_DETECTED = "STAGNATION_DETECTED"


# ---------------------------------------------------------------------------
# Structured observation
# ---------------------------------------------------------------------------
@dataclass
class PlanObservation:
    """The single structured input that drives every replanning decision.

    Nothing else influences whether the plan changes — the decision engine
    and stagnation detector read only this object.
    """

    status: str = ObservationStatus.SUCCESS
    summary: str = ""
    evidence: List[str] = field(default_factory=list)
    tool_results: List[Any] = field(default_factory=list)
    goal_progress: float = 0.0          # [0.0, 1.0]
    new_constraints: List[str] = field(default_factory=list)
    confidence: float = 1.0             # [0.0, 1.0]
    timestamp: float = 0.0              # sequence index or wall time

    def signature(self) -> Tuple:
        """A hashable fingerprint used for stagnation detection.

        Deliberately excludes ``timestamp`` and ``confidence`` so that a
        genuinely repeated observation compares equal across iterations.
        """
        return (
            self.status,
            self.summary,
            tuple(self.new_constraints),
            round(self.goal_progress, 4),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "summary": self.summary,
            "evidence": list(self.evidence),
            "tool_results": list(self.tool_results),
            "goal_progress": self.goal_progress,
            "new_constraints": list(self.new_constraints),
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Plan representation
# ---------------------------------------------------------------------------
@dataclass
class PlanStep:
    """One explicit, inspectable step in a plan."""

    step_id: str
    objective: str
    action: str
    expected_outcome: str = ""
    state: str = PlanStepState.PENDING
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    #: The observation recorded when this step was executed (history only).
    observation: Optional[PlanObservation] = None

    @property
    def inserted(self) -> bool:
        return bool(self.metadata.get("inserted"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "objective": self.objective,
            "action": self.action,
            "expected_outcome": self.expected_outcome,
            "state": self.state,
            "dependencies": list(self.dependencies),
            "inserted": self.inserted,
            "metadata": dict(self.metadata),
            "observation": self.observation.to_dict() if self.observation else None,
        }


@dataclass
class Plan:
    """An explicit plan split into immutable *history* and mutable *future*.

    * ``history`` — completed / failed / removed steps, append-only.  Their
      content is never modified once recorded.
    * ``future`` — pending steps, ordered.  The replanning engine operates
      here and only here.
    """

    goal: str
    history: List[PlanStep] = field(default_factory=list)
    future: List[PlanStep] = field(default_factory=list)

    # ----- construction -----
    @classmethod
    def from_steps(cls, goal: str, steps: List[PlanStep]) -> "Plan":
        return cls(goal=goal, history=[], future=list(steps))

    # ----- inspection -----
    def completed_steps(self) -> List[PlanStep]:
        return [s for s in self.history if s.state == PlanStepState.COMPLETED]

    def failed_steps(self) -> List[PlanStep]:
        return [s for s in self.history if s.state == PlanStepState.FAILED]

    def removed_steps(self) -> List[PlanStep]:
        return [s for s in self.history if s.state == PlanStepState.REMOVED]

    def pending_steps(self) -> List[PlanStep]:
        return list(self.future)

    def inserted_steps(self) -> List[PlanStep]:
        return [s for s in (self.history + self.future) if s.inserted]

    def _completed_ids(self) -> set:
        return {s.step_id for s in self.completed_steps()}

    def next_step(self) -> Optional[PlanStep]:
        """First pending step whose dependencies are all completed."""
        done = self._completed_ids()
        for step in self.future:
            if all(dep in done for dep in step.dependencies):
                return step
        return None

    def is_exhausted(self) -> bool:
        """True when no pending steps remain."""
        return not self.future

    # ----- execution transitions (history is append-only) -----
    def mark_executed(self, step: PlanStep, state: str) -> None:
        """Move *step* from future into immutable history with *state*."""
        if step in self.future:
            self.future.remove(step)
        step.state = state
        self.history.append(step)

    # ----- revision (future only) -----
    def apply_revision(self, new_future: List[PlanStep]) -> None:
        """Replace the future with *new_future*.

        Pending steps that are dropped become ``REMOVED`` history (so the
        audit trail keeps them); genuinely new steps are flagged
        ``inserted``.  History is never rewritten — only appended to.
        """
        keep_ids = {s.step_id for s in new_future}
        # Drop pending steps not carried forward → record as REMOVED.
        for step in list(self.future):
            if step.step_id not in keep_ids:
                step.state = PlanStepState.REMOVED
                self.history.append(step)
        known_ids = {s.step_id for s in self.history} | {
            s.step_id for s in self.future
        }
        for step in new_future:
            if step.step_id not in known_ids:
                step.metadata["inserted"] = True
                step.state = PlanStepState.PENDING
        self.future = list(new_future)

    # ----- serialisation -----
    def signature(self) -> Tuple:
        """Fingerprint of the *future* (for repeated-plan stagnation)."""
        return tuple((s.step_id, s.action) for s in self.future)

    def snapshot(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "history": [s.to_dict() for s in self.history],
            "future": [s.to_dict() for s in self.future],
            "completed": [s.step_id for s in self.completed_steps()],
            "pending": [s.step_id for s in self.future],
            "removed": [s.step_id for s in self.removed_steps()],
            "inserted": [s.step_id for s in self.inserted_steps()],
        }


@dataclass
class PlanRevision:
    """A recorded plan revision, for trace reconstruction."""

    iteration: int
    decision: str
    reason: str
    observation: Dict[str, Any]
    plan_before: Dict[str, Any]
    plan_after: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "decision": self.decision,
            "reason": self.reason,
            "observation": self.observation,
            "plan_before": self.plan_before,
            "plan_after": self.plan_after,
        }


# ---------------------------------------------------------------------------
# Decision policy — deterministic
# ---------------------------------------------------------------------------
class ReplanPolicy(Protocol):
    """Maps an observation to a deterministic decision."""

    def decide(
        self, goal: str, plan: Plan, observation: PlanObservation
    ) -> Tuple[str, str]:
        ...


class DeterministicReplanPolicy:
    """Rule-based decision engine — fully deterministic.

    Reads only the observation (plus whether pending steps remain):

    * ``IMPOSSIBLE``                         → ABORT
    * ``SUCCESS`` and goal_progress ≥ thresh → COMPLETE
    * ``SUCCESS`` with no pending steps left → COMPLETE
    * ``FAILURE`` / ``BLOCKED`` / ``CONSTRAINT`` (or new_constraints) → REVISE
    * otherwise                              → CONTINUE
    """

    def __init__(self, *, completion_threshold: float = 1.0) -> None:
        self.completion_threshold = completion_threshold

    def decide(
        self, goal: str, plan: Plan, observation: PlanObservation
    ) -> Tuple[str, str]:
        st = observation.status
        if st == ObservationStatus.IMPOSSIBLE:
            return ReplanDecision.ABORT, "observation reports goal impossible"
        if st == ObservationStatus.SUCCESS and observation.goal_progress >= self.completion_threshold:
            return ReplanDecision.COMPLETE, (
                f"goal_progress {observation.goal_progress:.2f} ≥ "
                f"{self.completion_threshold:.2f}"
            )
        if st == ObservationStatus.SUCCESS and plan.is_exhausted():
            return ReplanDecision.COMPLETE, "all steps completed successfully"
        if observation.new_constraints:
            return ReplanDecision.REVISE, (
                f"new constraints: {', '.join(observation.new_constraints)}"
            )
        if st in (ObservationStatus.FAILURE, ObservationStatus.BLOCKED, ObservationStatus.CONSTRAINT):
            return ReplanDecision.REVISE, f"observation status={st}"
        return ReplanDecision.CONTINUE, "current plan remains valid"


# ---------------------------------------------------------------------------
# Replanning engine — bounded, future-only
# ---------------------------------------------------------------------------
class Replanner(Protocol):
    """Produces the new *future* step list for a plan being revised."""

    def revise(
        self, goal: str, plan: Plan, observation: PlanObservation
    ) -> List[PlanStep]:
        ...


class RuleBasedReplanner:
    """Deterministic replanner driven by a caller-supplied strategy.

    The strategy receives the plan and the triggering observation and
    returns the new list of *future* (pending) steps.  It must only shape
    the future — the engine guarantees history is preserved regardless of
    what the strategy returns.

    When no strategy is given, a conservative default is used: on a step
    failure, keep the remaining future unchanged (drop nothing); when the
    observation carries an ``alternative`` step in its evidence/metadata,
    insert it ahead of the rest.
    """

    def __init__(
        self,
        strategy: Optional[
            Callable[[Plan, PlanObservation], List[PlanStep]]
        ] = None,
    ) -> None:
        self._strategy = strategy

    def revise(
        self, goal: str, plan: Plan, observation: PlanObservation
    ) -> List[PlanStep]:
        if self._strategy is not None:
            return list(self._strategy(plan, observation))
        # Default: preserve remaining future untouched.
        return list(plan.future)


# ---------------------------------------------------------------------------
# Observation building
# ---------------------------------------------------------------------------
class ObservationBuilder(Protocol):
    """Turns an executed step + governed trace into a structured observation."""

    def build(
        self,
        goal: str,
        step: PlanStep,
        trace: Optional[AgentRunTrace],
        agent: Any,
        iteration: int,
    ) -> PlanObservation:
        ...


class ScriptedObservationBuilder:
    """Returns pre-scripted observations in sequence.

    Deterministic — the primary tool for tests and demos, and the mechanism
    that makes "same goal, different observations → different plans"
    reproducible without depending on a live model.
    """

    def __init__(self, observations: List[PlanObservation]) -> None:
        self._observations = list(observations)
        self._i = 0

    def build(self, goal, step, trace, agent, iteration) -> PlanObservation:
        if self._i < len(self._observations):
            obs = self._observations[self._i]
        else:
            # Exhausted script → neutral partial observation.
            obs = PlanObservation(status=ObservationStatus.PARTIAL, summary="(no more scripted observations)")
        self._i += 1
        obs.timestamp = iteration
        return obs


class DefaultObservationBuilder:
    """Derives a best-effort observation from the governed trace + agent.

    Heuristic and dependency-free: success unless the trace errored or the
    action was safety-blocked; tool results pulled from the agent's last
    goal-state actions; goal_progress estimated from completed fraction.
    """

    def build(self, goal, step, trace, agent, iteration) -> PlanObservation:
        error = bool(getattr(trace, "error_occurred", False))
        blocked = bool(getattr(trace, "safety_blocked", False))
        actions_executed = int(getattr(trace, "actions_executed", 0) or 0)

        tool_results: List[Any] = []
        goal_state = getattr(agent, "goal_state", None)
        if goal_state is not None:
            for action in getattr(goal_state, "actions", []) or []:
                if action.result is not None:
                    tool_results.append(action.result)

        if error:
            status = ObservationStatus.FAILURE
        elif blocked:
            status = ObservationStatus.BLOCKED
        elif actions_executed > 0 or tool_results:
            status = ObservationStatus.SUCCESS
        else:
            status = ObservationStatus.PARTIAL

        return PlanObservation(
            status=status,
            summary=f"executed step '{step.step_id}' ({step.objective})",
            tool_results=tool_results,
            goal_progress=0.0,
            confidence=1.0,
            timestamp=iteration,
        )


# ---------------------------------------------------------------------------
# Stagnation detection
# ---------------------------------------------------------------------------
@dataclass
class StagnationConfig:
    """Thresholds for deterministic stagnation detection."""

    max_repeated_observations: int = 3   # identical observation N times → STAGNATION
    max_consecutive_failures: int = 3    # same failure streak N times → REPEATED_FAILURES
    max_no_progress: int = 3             # goal_progress flat for N steps → NO_PROGRESS
    max_repeated_plans: int = 3          # identical revised plan N times → STAGNATION


class StagnationDetector:
    """Deterministically flags repeated ineffective execution.

    Ingests each observation (and, on revision, the new plan signature) and
    returns a :class:`StopReason` when a threshold is crossed, else ``None``.
    """

    def __init__(self, config: Optional[StagnationConfig] = None) -> None:
        self.config = config or StagnationConfig()
        self._last_obs_sig: Optional[Tuple] = None
        self._obs_repeats = 1
        self._failure_streak = 0
        self._best_progress = -1.0
        self._no_progress = 0
        self._last_plan_sig: Optional[Tuple] = None
        self._plan_repeats = 1

    def observe(self, observation: PlanObservation) -> Optional[str]:
        # 1. Repeated identical observation.
        sig = observation.signature()
        if sig == self._last_obs_sig:
            self._obs_repeats += 1
        else:
            self._obs_repeats = 1
            self._last_obs_sig = sig
        if self._obs_repeats >= self.config.max_repeated_observations:
            return StopReason.STAGNATION_DETECTED

        # 2. Consecutive failures.
        if observation.status in (ObservationStatus.FAILURE, ObservationStatus.BLOCKED):
            self._failure_streak += 1
        else:
            self._failure_streak = 0
        if self._failure_streak >= self.config.max_consecutive_failures:
            return StopReason.REPEATED_FAILURES

        # 3. No measurable progress.
        if observation.goal_progress > self._best_progress:
            self._best_progress = observation.goal_progress
            self._no_progress = 0
        else:
            self._no_progress += 1
        if self._no_progress >= self.config.max_no_progress:
            return StopReason.NO_PROGRESS

        return None

    def observe_plan(self, plan: Plan) -> Optional[str]:
        """Detect the same revised plan being produced repeatedly."""
        sig = plan.signature()
        if sig == self._last_plan_sig:
            self._plan_repeats += 1
        else:
            self._plan_repeats = 1
            self._last_plan_sig = sig
        if self._plan_repeats >= self.config.max_repeated_plans:
            return StopReason.STAGNATION_DETECTED
        return None


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------
@dataclass
class ReplanningResult:
    """Outcome of an observation-driven replanning run."""

    goal: str
    stop_reason: str
    done: bool
    iterations: int
    plan: Plan
    observations: List[PlanObservation] = field(default_factory=list)
    revisions: List[PlanRevision] = field(default_factory=list)
    decisions: List[Tuple[str, str]] = field(default_factory=list)
    trace: List[Dict[str, Any]] = field(default_factory=list)
    run_budget: Optional[RunBudget] = None
    budget_timeline: List[dict] = field(default_factory=list)

    @property
    def revision_count(self) -> int:
        return len(self.revisions)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal": self.goal,
            "stop_reason": self.stop_reason,
            "done": self.done,
            "iterations": self.iterations,
            "revision_count": self.revision_count,
            "final_plan": self.plan.snapshot(),
            "decisions": [{"decision": d, "reason": r} for d, r in self.decisions],
            "revisions": [r.to_dict() for r in self.revisions],
            "trace": self.trace,
            "run_budget": self.run_budget.snapshot() if self.run_budget is not None else None,
            "budget_timeline": self.budget_timeline,
        }


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------
def _response_from_trace(trace: AgentRunTrace) -> str:
    for evt in trace.get_events(RUN_COMPLETED):
        result = evt.payload.get("result") if isinstance(evt.payload, dict) else None
        if isinstance(result, dict):
            return result.get("response", "") or ""
    chunks = []
    for evt in trace.get_events(TEXT_CHUNK):
        if isinstance(evt.payload, dict):
            chunks.append(str(evt.payload.get("text", "")))
    return "".join(chunks)


class ReplanningRunner:
    """Execute a plan step-by-step, adapting the future from observations.

    Loop: pick the next pending step → execute it under governance →
    build a structured observation → decide (CONTINUE/REVISE/ABORT/
    COMPLETE) → optionally revise the *future* → check stagnation / bounds
    → continue.  Completed steps are never modified; every revision is
    recorded for reconstruction; all execution consumes the shared
    :class:`RunBudget`.

    Args:
        agent: A governed ``AgenticLLMWrapper``.
        policy: Deterministic decision engine (default
            :class:`DeterministicReplanPolicy`).
        replanner: Future-only revision engine (default
            :class:`RuleBasedReplanner`).
        observation_builder: Builds a :class:`PlanObservation` per step
            (default :class:`DefaultObservationBuilder`).
        max_iterations: Hard cap on executed steps (terminal).
        max_revisions: Hard cap on plan revisions (terminal → NO_VALID_PLAN
            when exceeded).
        run_budget: Shared :class:`RunBudget` (H11).  Never re-created here.
        stagnation: :class:`StagnationConfig` thresholds.
        on_step: Optional callback ``(iteration, step, observation,
            decision) -> None``.
        fresh_session: Start a fresh agent session for the whole run.
    """

    def __init__(
        self,
        agent: Any,
        *,
        policy: Optional[ReplanPolicy] = None,
        replanner: Optional[Replanner] = None,
        observation_builder: Optional[ObservationBuilder] = None,
        max_iterations: int = 12,
        max_revisions: int = 6,
        run_budget: Optional[RunBudget] = None,
        budget_policy: Optional[Any] = None,
        stagnation: Optional[StagnationConfig] = None,
        on_step: Optional[Callable[[int, PlanStep, PlanObservation, str], None]] = None,
        fresh_session: bool = True,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        if max_revisions < 0:
            raise ValueError("max_revisions must be >= 0")
        self.agent = agent
        self.policy = policy or DeterministicReplanPolicy()
        self.replanner = replanner or RuleBasedReplanner()
        self.observation_builder = observation_builder or DefaultObservationBuilder()
        self.max_iterations = max_iterations
        self.max_revisions = max_revisions
        self.run_budget = run_budget
        self.budget_policy = budget_policy
        self.stagnation = StagnationDetector(stagnation)
        self.on_step = on_step
        self.fresh_session = fresh_session

    def run(self, goal: str, plan: Plan) -> ReplanningResult:
        """Execute *plan* toward *goal*, adapting as observations arrive."""
        if self.fresh_session and hasattr(self.agent, "new_session"):
            self.agent.new_session()
        if self.run_budget is not None:
            attach_run_budget(self.agent, self.run_budget)
            self.run_budget.start()

        result = ReplanningResult(
            goal=goal, stop_reason=StopReason.ITERATION_LIMIT, done=False,
            iterations=0, plan=plan, run_budget=self.run_budget,
        )
        revisions_used = 0

        for i in range(self.max_iterations):
            # H11: reserve this iteration BEFORE executing.
            if self.run_budget is not None:
                res = self.run_budget.reserve(iterations=1)
                if not res.ok:
                    result.stop_reason = StopReason.BUDGET_EXHAUSTED
                    break

            step = plan.next_step()
            if step is None:
                # Nothing left to do.
                result.stop_reason = (
                    StopReason.GOAL_COMPLETED
                    if plan.is_exhausted() and not plan.failed_steps()
                    else StopReason.NO_VALID_PLAN
                )
                break

            # --- execute the step under governance ---
            try:
                trace = self.agent.run_with_trace(
                    step.action, budget_policy=self.budget_policy
                )
            except BudgetExhausted:
                result.stop_reason = StopReason.BUDGET_EXHAUSTED
                break

            observation = self.observation_builder.build(
                goal, step, trace, self.agent, i
            )
            observation.timestamp = i
            result.observations.append(observation)

            # --- deterministic decision ---
            decision, reason = self.policy.decide(goal, plan, observation)
            result.decisions.append((decision, reason))

            plan_before = plan.snapshot()

            # Record the executed step into immutable history.
            executed_state = (
                PlanStepState.COMPLETED
                if observation.status in (ObservationStatus.SUCCESS, ObservationStatus.PARTIAL)
                else PlanStepState.FAILED
            )
            step.observation = observation
            plan.mark_executed(step, executed_state)

            revised = False
            if decision == ReplanDecision.REVISE:
                if revisions_used >= self.max_revisions:
                    result.stop_reason = StopReason.NO_VALID_PLAN
                    self._record_trace(result, i, step, observation, decision,
                                       reason, plan_before, plan.snapshot(), False)
                    self._append_budget(result)
                    break
                new_future = self.replanner.revise(goal, plan, observation)
                plan.apply_revision(new_future)
                revisions_used += 1
                revised = True
                # Repeated-plan stagnation.
                plan_stag = self.stagnation.observe_plan(plan)
                if plan.is_exhausted() and not decision == ReplanDecision.COMPLETE:
                    # Revision produced nothing to do.
                    self._record_trace(result, i, step, observation, decision,
                                       reason, plan_before, plan.snapshot(), True)
                    result.revisions.append(PlanRevision(
                        i, decision, reason, observation.to_dict(),
                        plan_before, plan.snapshot()))
                    result.stop_reason = StopReason.NO_VALID_PLAN
                    self._append_budget(result)
                    break

            self._record_trace(result, i, step, observation, decision, reason,
                               plan_before, plan.snapshot(), revised)
            if revised:
                result.revisions.append(PlanRevision(
                    i, decision, reason, observation.to_dict(),
                    plan_before, plan.snapshot()))

            if self.on_step is not None:
                self.on_step(i, step, observation, decision)

            # --- terminal decisions ---
            if decision == ReplanDecision.COMPLETE:
                result.stop_reason = StopReason.GOAL_COMPLETED
                result.done = True
                self._append_budget(result)
                break
            if decision == ReplanDecision.ABORT:
                result.stop_reason = StopReason.GOAL_IMPOSSIBLE
                self._append_budget(result)
                break

            # --- stagnation (observation-driven) ---
            stag = self.stagnation.observe(observation)
            if stag is not None:
                result.stop_reason = stag
                self._append_budget(result)
                break
            if revised:
                plan_stag = self.stagnation.observe_plan(plan)
                if plan_stag is not None:
                    result.stop_reason = plan_stag
                    self._append_budget(result)
                    break

            # --- budget / completion checks ---
            if self.run_budget is not None:
                self.run_budget.record_usage(tool_calls=trace.actions_executed)
                self.run_budget.tick()
                self._append_budget(result)
                if self.run_budget.is_exhausted():
                    result.stop_reason = StopReason.BUDGET_EXHAUSTED
                    break

            if plan.is_exhausted():
                result.stop_reason = (
                    StopReason.GOAL_COMPLETED
                    if not plan.failed_steps()
                    else StopReason.NO_VALID_PLAN
                )
                result.done = result.stop_reason == StopReason.GOAL_COMPLETED
                break

        result.iterations = len(result.observations)
        if self.run_budget is not None and not self.run_budget.is_exhausted():
            self.run_budget.complete()
        return result

    # ----- helpers -----
    @staticmethod
    def _record_trace(result, iteration, step, observation, decision, reason,
                      plan_before, plan_after, revised) -> None:
        result.trace.append({
            "iteration": iteration,
            "step": {"step_id": step.step_id, "action": step.action,
                     "objective": step.objective},
            "observation": observation.to_dict(),
            "decision": decision,
            "reason": reason,
            "revised": revised,
            "plan_before": plan_before,
            "plan_after": plan_after,
        })

    def _append_budget(self, result: ReplanningResult) -> None:
        if self.run_budget is not None:
            result.budget_timeline.append(self.run_budget.snapshot())


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_plan(plan: Plan) -> str:
    """Human-readable plan with per-step state."""
    lines = [f"Plan: {plan.goal}", "-" * 48]
    for s in plan.history:
        flag = " (inserted)" if s.inserted else ""
        lines.append(f"  [{s.state:<9}] {s.step_id}: {s.objective}{flag}")
    for s in plan.future:
        flag = " (inserted)" if s.inserted else ""
        lines.append(f"  [{'pending':<9}] {s.step_id}: {s.objective}{flag}")
    return "\n".join(lines)


def format_replanning_trace(result: ReplanningResult) -> str:
    """Reconstruct the Original Plan → Observation → Decision → Revised Plan story."""
    lines = [
        f"Replanning trace: {result.goal}",
        f"stop_reason={result.stop_reason}  done={result.done}  "
        f"iterations={result.iterations}  revisions={result.revision_count}",
        "=" * 60,
    ]
    for entry in result.trace:
        obs = entry["observation"]
        lines.append(
            f"  iter {entry['iteration']}: step={entry['step']['step_id']} "
            f"({entry['step']['action']})"
        )
        lines.append(
            f"    observation: status={obs['status']} "
            f"progress={obs['goal_progress']:.2f} "
            f"constraints={obs['new_constraints']}"
        )
        lines.append(f"    decision:    {entry['decision']} — {entry['reason']}")
        if entry["revised"]:
            after_pending = entry["plan_after"]["pending"]
            lines.append(f"    revised →    pending now: {after_pending}")
    return "\n".join(lines)
