"""
Iterate-Until-Done Loop — Governed Re-Planning for the Agentic Framework
========================================================================

The base :class:`AgenticLLMWrapper` runs a *single* governed turn:
``decompose → generate (reflective) → safety gate → execute actions``.
It does **one** decomposition pass and **one** action pass, and it does
not feed tool results back into the model to decide the next step.

This module adds that missing loop **without weakening governance**.  It
drives an existing agent as the per-step primitive: every iteration is a
full ``run_with_trace()`` call — so cancellation, approval gates, budget
enforcement, safety gating and tracing all still apply — and between
iterations it:

1. Extracts the **observations** (tool results / action outcomes) from
   the step that just ran.
2. Asks a :class:`CompletionChecker` whether the goal is satisfied.
3. If not, feeds the observations back into the next instruction so the
   model can pick the next step.

Safety is preserved by two hard bounds that cannot be disabled:

* ``max_iterations`` — a terminal cap on loop length.
* an optional shared :class:`BudgetPolicy` applied across *all*
  iterations, so a runaway loop hits the same terminal ``BUDGET_EXCEEDED``
  event a single turn would.

The loop is deliberately transparent: every step keeps its full
``AgentRunTrace``, so the whole multi-step run remains auditable.

Quickstart
----------
::

    from agentic.agentic_framework import (
        build_agent, MockLLMAdapter, ToolSpec, ToolRiskLevel,
        IterativeAgentRunner, LLMCompletionChecker,
    )

    agent = build_agent(adapter=MockLLMAdapter(...), tools={...})
    runner = IterativeAgentRunner(
        agent,
        checker=LLMCompletionChecker(MockLLMAdapter(...)),
        max_iterations=5,
    )
    result = runner.run("Research X, then summarise it")
    print(result.final_response, result.stop_reason)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional, Protocol

from agentic.agentic_framework.streaming_events import RUN_COMPLETED, TEXT_CHUNK
from agentic.agentic_framework.tracing import AgentRunTrace
from agentic.agentic_framework.run_budget import (
    RunBudget,
    BudgetExhausted,
    attach_run_budget,
)

__all__ = [
    "Observation",
    "LoopStep",
    "LoopHistory",
    "LoopResult",
    "CompletionVerdict",
    "CompletionChecker",
    "PredicateCompletionChecker",
    "KeywordCompletionChecker",
    "LLMCompletionChecker",
    "IterativeAgentRunner",
    "run_until_done",
]


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass
class Observation:
    """A single tool result / action outcome produced during a step."""

    action_type: str
    description: str
    status: str  # "completed" | "blocked" | "skipped" | ...
    result: Any = None
    error: Optional[str] = None

    def render(self) -> str:
        """One-line human-readable rendering for feedback prompts."""
        if self.status == "completed":
            return f"- [{self.action_type}] {self.description} -> {self.result}"
        detail = self.error or self.status
        return f"- [{self.action_type}] {self.description} -> ({self.status}: {detail})"


@dataclass
class LoopStep:
    """One governed iteration of the loop."""

    iteration: int
    instruction: str
    response: str
    observations: List[Observation] = field(default_factory=list)
    trace: Optional[AgentRunTrace] = None

    @property
    def actions_executed(self) -> int:
        return self.trace.actions_executed if self.trace is not None else 0

    @property
    def total_tokens(self) -> int:
        return self.trace.total_tokens if self.trace is not None else 0


@dataclass
class LoopHistory:
    """Ordered record of every step taken toward a goal."""

    goal: str
    steps: List[LoopStep] = field(default_factory=list)

    def latest(self) -> Optional[LoopStep]:
        return self.steps[-1] if self.steps else None

    def latest_response(self) -> str:
        step = self.latest()
        return step.response if step is not None else ""

    def all_observations(self) -> List[Observation]:
        obs: List[Observation] = []
        for step in self.steps:
            obs.extend(step.observations)
        return obs

    def render_observations(self) -> str:
        """Render every observation so far as a feedback block."""
        obs = self.all_observations()
        if not obs:
            return "(no tool results yet)"
        return "\n".join(o.render() for o in obs)


@dataclass
class LoopResult:
    """Outcome of an iterate-until-done run."""

    goal: str
    done: bool
    stop_reason: str  # "completed" | "max_iterations" | "budget_exceeded" | "budget_exhausted" | "error"
    iterations: int
    history: LoopHistory
    final_response: str
    #: Deterministic RunBudget termination reason (H11), when the shared
    #: run budget stopped the loop (e.g. "MODEL_CALL_LIMIT").
    termination_reason: Optional[str] = None
    #: The shared RunBudget (H11), when one was supplied.
    run_budget: Optional["RunBudget"] = None
    #: Per-step RunBudget snapshots so cumulative usage can be reconstructed.
    budget_timeline: List[dict] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(s.total_tokens for s in self.history.steps)

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "done": self.done,
            "stop_reason": self.stop_reason,
            "iterations": self.iterations,
            "final_response": self.final_response,
            "total_tokens": self.total_tokens,
            "termination_reason": self.termination_reason,
            "run_budget": self.run_budget.snapshot() if self.run_budget is not None else None,
            "budget_timeline": self.budget_timeline,
            "steps": [
                {
                    "iteration": s.iteration,
                    "instruction": s.instruction,
                    "response": s.response,
                    "actions_executed": s.actions_executed,
                    "observations": [o.render() for o in s.observations],
                }
                for s in self.history.steps
            ],
        }


# ---------------------------------------------------------------------------
# Completion checkers — the "is the goal done?" decision
# ---------------------------------------------------------------------------
@dataclass
class CompletionVerdict:
    """Result of a completion check."""

    done: bool
    reason: str = ""
    #: When ``done`` is False, an optional explicit next instruction.
    #: When None, the runner builds a default feedback re-prompt.
    next_instruction: Optional[str] = None


class CompletionChecker(Protocol):
    """Decides whether the goal has been satisfied after a step."""

    def check(self, goal: str, history: LoopHistory) -> CompletionVerdict:
        ...


class PredicateCompletionChecker:
    """Deterministic checker driven by a Python predicate over history.

    Useful for tests and for goals with a programmatic success condition
    (e.g. "stop once the ``compute`` tool has returned a value").
    """

    def __init__(
        self,
        predicate: Callable[[LoopHistory], bool],
        *,
        next_instruction: Optional[Callable[[LoopHistory], str]] = None,
    ) -> None:
        self._predicate = predicate
        self._next = next_instruction

    def check(self, goal: str, history: LoopHistory) -> CompletionVerdict:
        if self._predicate(history):
            return CompletionVerdict(done=True, reason="predicate satisfied")
        nxt = self._next(history) if self._next is not None else None
        return CompletionVerdict(done=False, next_instruction=nxt)


class KeywordCompletionChecker:
    """Stop when a marker string appears in the latest response.

    A lightweight way to let the *agent's own output* signal completion
    (e.g. the model is prompted to end with ``[DONE]`` when finished).
    """

    def __init__(self, done_markers: Optional[List[str]] = None) -> None:
        self.done_markers = [m.lower() for m in (done_markers or ["[done]", "task complete"])]

    def check(self, goal: str, history: LoopHistory) -> CompletionVerdict:
        text = history.latest_response().lower()
        if any(marker in text for marker in self.done_markers):
            return CompletionVerdict(done=True, reason="done marker in response")
        return CompletionVerdict(done=False)


class LLMCompletionChecker:
    """Ask an LLM whether the goal is complete given the observations.

    This is the genuine *feed-results-back-to-the-model* path: the tool
    results from the step that just ran are shown to the model, which
    replies ``DONE`` (goal satisfied) or ``CONTINUE: <next step>``.  A
    ``CONTINUE`` reply's remainder becomes the next instruction, closing
    the observe → decide → act loop.

    The adapter only needs the ``call(prompt) -> str`` protocol, so any
    framework adapter (mock or real) works.
    """

    PROMPT_TEMPLATE = (
        "You are the controller of an autonomous agent working toward a goal.\n"
        "GOAL:\n{goal}\n\n"
        "WORK AND TOOL RESULTS SO FAR:\n{observations}\n\n"
        "LATEST AGENT RESPONSE:\n{response}\n\n"
        "Decide if the goal is fully satisfied.\n"
        "Reply on a single line, exactly one of:\n"
        "  DONE\n"
        "  CONTINUE: <the single next step the agent should take>\n"
    )

    def __init__(
        self,
        adapter: Any,
        *,
        done_token: str = "DONE",
        continue_token: str = "CONTINUE",
    ) -> None:
        self.adapter = adapter
        self.done_token = done_token
        self.continue_token = continue_token

    def check(self, goal: str, history: LoopHistory) -> CompletionVerdict:
        prompt = self.PROMPT_TEMPLATE.format(
            goal=goal,
            observations=history.render_observations(),
            response=history.latest_response(),
        )
        raw = (self.adapter.call(prompt) or "").strip()
        upper = raw.upper()

        # A CONTINUE decision may carry the next instruction after a colon.
        cont_idx = upper.find(self.continue_token.upper())
        done_idx = upper.find(self.done_token.upper())

        # Prefer CONTINUE only when it is the leading decision token.
        if cont_idx != -1 and (done_idx == -1 or cont_idx <= done_idx):
            remainder = raw[cont_idx + len(self.continue_token):].lstrip(" :\t-").strip()
            return CompletionVerdict(
                done=False,
                reason="controller: continue",
                next_instruction=remainder or None,
            )
        if done_idx != -1:
            return CompletionVerdict(done=True, reason="controller: done")

        # Unparseable → fail safe by continuing (bounded by max_iterations).
        return CompletionVerdict(done=False, reason="controller: unparsed")


# ---------------------------------------------------------------------------
# Trace / observation extraction helpers
# ---------------------------------------------------------------------------
def _response_from_trace(trace: AgentRunTrace) -> str:
    """Pull the agent's response text out of a completed trace."""
    for evt in trace.get_events(RUN_COMPLETED):
        result = evt.payload.get("result") if isinstance(evt.payload, dict) else None
        if isinstance(result, dict):
            return result.get("response", "") or ""
    # Fallback: concatenate streamed text chunks.
    chunks = []
    for evt in trace.get_events(TEXT_CHUNK):
        if isinstance(evt.payload, dict):
            chunks.append(str(evt.payload.get("text", "")))
    return "".join(chunks)


def _observations_from_agent(agent: Any) -> List[Observation]:
    """Read the executed actions off the agent's last goal state."""
    goal_state = getattr(agent, "goal_state", None)
    if goal_state is None:
        return []
    obs: List[Observation] = []
    for action in getattr(goal_state, "actions", []) or []:
        # Only surface actions the runtime actually touched.
        if action.status == "pending":
            continue
        obs.append(
            Observation(
                action_type=action.action_type,
                description=action.description,
                status=action.status,
                result=action.result,
                error=action.error,
            )
        )
    return obs


# ---------------------------------------------------------------------------
# The runner
# ---------------------------------------------------------------------------
class IterativeAgentRunner:
    """Drive a governed agent in an observe → decide → act loop.

    Each iteration runs the full governed pipeline via
    ``agent.run_with_trace(...)``; between iterations the observations are
    fed back and a :class:`CompletionChecker` decides whether to stop.

    Args:
        agent: An ``AgenticLLMWrapper`` (typically from ``build_agent``).
        checker: Decides goal completion.  Defaults to a
            :class:`KeywordCompletionChecker` (stops on a ``[DONE]``
            marker in the response).
        max_iterations: Hard cap on loop length (terminal, non-optional).
        budget_policy: Optional per-invocation ``BudgetPolicy`` passed
            into each governed step (resets every step — legacy R9 path).
        run_budget: Optional shared :class:`RunBudget` (H11).  Created once
            by the caller and consumed cumulatively across every iteration
            — model calls, tokens, cost and iterations are reserved from
            the same object and never reset until the workflow completes.
            When a limit is hit the loop terminates deterministically with
            ``stop_reason="budget_exhausted"`` and ``termination_reason``.
        reprompt: Optional builder ``(goal, history) -> str`` for the next
            instruction when the checker gives no explicit one.
        on_step: Optional callback invoked with each completed
            :class:`LoopStep` (for progress display).
        fresh_session: When True (default) a new session is started so
            the whole loop shares one memory context.
    """

    def __init__(
        self,
        agent: Any,
        *,
        checker: Optional[CompletionChecker] = None,
        max_iterations: int = 6,
        budget_policy: Optional[Any] = None,
        run_budget: Optional[RunBudget] = None,
        reprompt: Optional[Callable[[str, LoopHistory], str]] = None,
        on_step: Optional[Callable[[LoopStep], None]] = None,
        fresh_session: bool = True,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        self.agent = agent
        self.checker = checker or KeywordCompletionChecker()
        self.max_iterations = max_iterations
        self.budget_policy = budget_policy
        #: Shared cumulative RunBudget (H11).  When provided it persists
        #: across every iteration — it is never re-created inside the loop.
        self.run_budget = run_budget
        self.reprompt = reprompt or self._default_reprompt
        self.on_step = on_step
        self.fresh_session = fresh_session

    @staticmethod
    def _default_reprompt(goal: str, history: LoopHistory) -> str:
        """Fold observations back into the next instruction."""
        return (
            f"Goal: {goal}\n\n"
            f"Progress and tool results so far:\n{history.render_observations()}\n\n"
            "Take the next step toward the goal. If it is already "
            "satisfied, say so explicitly."
        )

    def run(self, goal: str) -> LoopResult:
        """Run the loop until the checker says done or a bound is hit."""
        if self.fresh_session and hasattr(self.agent, "new_session"):
            self.agent.new_session()

        # H11: install the shared budget on the agent (idempotent) and
        # mark the workflow start.  The budget is NOT re-created here.
        if self.run_budget is not None:
            attach_run_budget(self.agent, self.run_budget)
            self.run_budget.start()

        history = LoopHistory(goal=goal)
        instruction = goal
        done = False
        stop_reason = "max_iterations"
        termination_reason: Optional[str] = None
        budget_timeline: List[dict] = []

        for i in range(self.max_iterations):
            # H11: reserve this iteration BEFORE executing it.  A rejected
            # reservation stops the loop before any work is done.
            if self.run_budget is not None:
                res = self.run_budget.reserve(iterations=1)
                if not res.ok:
                    stop_reason = "budget_exhausted"
                    termination_reason = res.reason
                    break

            # H11: a model-call reservation may reject mid-step; that raises
            # BudgetExhausted (BaseException), which unwinds here.
            try:
                trace = self.agent.run_with_trace(
                    instruction,
                    budget_policy=self.budget_policy,
                )
            except BudgetExhausted as exc:
                stop_reason = "budget_exhausted"
                termination_reason = exc.reason
                break

            step = LoopStep(
                iteration=i,
                instruction=instruction,
                response=_response_from_trace(trace),
                observations=_observations_from_agent(self.agent),
                trace=trace,
            )
            history.steps.append(step)

            # H11: record post-hoc consumption (tool calls from the governed
            # trace; tokens/cost were recorded by the budgeted adapter).
            if self.run_budget is not None:
                self.run_budget.record_usage(tool_calls=trace.actions_executed)
                self.run_budget.tick()
                budget_timeline.append(self.run_budget.snapshot())

            if self.on_step is not None:
                self.on_step(step)

            # Terminal governance events end the loop immediately.
            if trace.budget_exceeded:
                stop_reason = "budget_exceeded"
                break
            if trace.error_occurred:
                stop_reason = "error"
                break

            # H11: a cumulative gate (tokens/cost/tool/time) crossed during
            # this step blocks the next one.
            if self.run_budget is not None and self.run_budget.is_exhausted():
                stop_reason = "budget_exhausted"
                termination_reason = self.run_budget.termination_reason
                break

            verdict = self.checker.check(goal, history)
            if verdict.done:
                done = True
                stop_reason = "completed"
                break

            instruction = verdict.next_instruction or self.reprompt(goal, history)

        if self.run_budget is not None and not self.run_budget.is_exhausted():
            self.run_budget.complete()

        return LoopResult(
            goal=goal,
            done=done,
            stop_reason=stop_reason,
            iterations=len(history.steps),
            history=history,
            final_response=history.latest_response(),
            termination_reason=termination_reason,
            run_budget=self.run_budget,
            budget_timeline=budget_timeline,
        )


def run_until_done(
    agent: Any,
    goal: str,
    *,
    checker: Optional[CompletionChecker] = None,
    max_iterations: int = 6,
    budget_policy: Optional[Any] = None,
    run_budget: Optional[RunBudget] = None,
    on_step: Optional[Callable[[LoopStep], None]] = None,
) -> LoopResult:
    """Convenience one-call wrapper around :class:`IterativeAgentRunner`."""
    runner = IterativeAgentRunner(
        agent,
        checker=checker,
        max_iterations=max_iterations,
        budget_policy=budget_policy,
        run_budget=run_budget,
        on_step=on_step,
    )
    return runner.run(goal)
