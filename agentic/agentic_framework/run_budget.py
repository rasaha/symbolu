"""
RunBudget — Cumulative Run-Level Resource Governance (H11)
=========================================================

A single, shared budget for one autonomous workflow.

The existing per-invocation ``BudgetPolicy`` (``token_budget.py``) is
evaluated *inside each* ``run_with_trace()`` call and starts fresh every
time.  That is correct for one turn, but an autonomous workflow re-enters
``run_with_trace()`` many times — once per loop iteration and once per
agent handoff — so token/cost limits could be honoured per call yet
blown cumulatively.

``RunBudget`` closes that gap.  It is created **once** when a workflow
begins and shared, unchanged, across:

* iterative execution (observe → decide → act loops)
* retries
* agent handoffs
* nested runtime invocations

Every execution step consumes from the same object.  All counters are
**monotonically increasing** and never reset until the workflow completes.

Enforcement is **reserve-before-execute**:

1. ``reserve()`` checks remaining budget for the requested resources.
2. If any limit would be exceeded it returns a rejected ``Reservation``
   (and, at the model-call seam, raises :class:`BudgetExhausted`) *before*
   the operation runs.
3. Otherwise it reserves (increments) the discrete counters and returns.

Dimensions tracked (:class:`BudgetDimension`):

    model_calls, tool_calls, prompt_tokens, completion_tokens,
    total_tokens, cost, elapsed_time, iterations, handoffs

Enforcement seams:

* **model_calls / prompt_tokens / completion_tokens / total_tokens /
  cost / elapsed_time** — the :class:`BudgetedAdapter` reserves one model
  call *before* each real ``adapter.call()`` and records the tokens/cost
  it produced *after*.  A rejected reservation raises
  :class:`BudgetExhausted`, which unwinds immediately (it derives from
  ``BaseException`` so it passes cleanly through the runtime's internal
  ``except Exception`` fallbacks) and is caught at the workflow boundary.
* **iterations / handoffs** — reserved by the loop / orchestrator before
  the step runs.
* **tool_calls** — recorded from the governed trace's ``actions_executed``
  after each step; the *next* step's reservation gate blocks if the tool
  budget is spent.

This module adds budgeting only.  It does not modify policy, governance,
authorization, routing, or tool/LLM behaviour.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from agentic.agentic_framework.token_budget import estimate_tokens

__all__ = [
    "BudgetDimension",
    "TerminationReason",
    "RunBudgetStatus",
    "RunBudgetLimits",
    "RunBudgetUsage",
    "Reservation",
    "BudgetViolation",
    "BudgetExhausted",
    "RunBudget",
    "BudgetedAdapter",
    "attach_run_budget",
    "format_run_budget",
]


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------
class BudgetDimension:
    """Canonical dimension names (string constants)."""

    MODEL_CALLS = "model_calls"
    TOOL_CALLS = "tool_calls"
    PROMPT_TOKENS = "prompt_tokens"
    COMPLETION_TOKENS = "completion_tokens"
    TOTAL_TOKENS = "total_tokens"
    COST = "cost"
    ELAPSED_TIME = "elapsed_time"
    ITERATIONS = "iterations"
    HANDOFFS = "handoffs"


class TerminationReason:
    """Deterministic termination reasons (string constants)."""

    MODEL_CALL_LIMIT = "MODEL_CALL_LIMIT"
    TOOL_CALL_LIMIT = "TOOL_CALL_LIMIT"
    PROMPT_TOKEN_LIMIT = "PROMPT_TOKEN_LIMIT"
    COMPLETION_TOKEN_LIMIT = "COMPLETION_TOKEN_LIMIT"
    TOKEN_LIMIT = "TOKEN_LIMIT"
    COST_LIMIT = "COST_LIMIT"
    TIME_LIMIT = "TIME_LIMIT"
    ITERATION_LIMIT = "ITERATION_LIMIT"
    HANDOFF_LIMIT = "HANDOFF_LIMIT"


class RunBudgetStatus:
    """Lifecycle status of a RunBudget."""

    ACTIVE = "ACTIVE"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    COMPLETED = "COMPLETED"


# Fixed evaluation order → deterministic "which limit tripped first".
_DIMENSION_ORDER = [
    BudgetDimension.MODEL_CALLS,
    BudgetDimension.TOOL_CALLS,
    BudgetDimension.ITERATIONS,
    BudgetDimension.HANDOFFS,
    BudgetDimension.TOTAL_TOKENS,
    BudgetDimension.PROMPT_TOKENS,
    BudgetDimension.COMPLETION_TOKENS,
    BudgetDimension.COST,
    BudgetDimension.ELAPSED_TIME,
]

_DIMENSION_TO_REASON = {
    BudgetDimension.MODEL_CALLS: TerminationReason.MODEL_CALL_LIMIT,
    BudgetDimension.TOOL_CALLS: TerminationReason.TOOL_CALL_LIMIT,
    BudgetDimension.ITERATIONS: TerminationReason.ITERATION_LIMIT,
    BudgetDimension.HANDOFFS: TerminationReason.HANDOFF_LIMIT,
    BudgetDimension.TOTAL_TOKENS: TerminationReason.TOKEN_LIMIT,
    BudgetDimension.PROMPT_TOKENS: TerminationReason.PROMPT_TOKEN_LIMIT,
    BudgetDimension.COMPLETION_TOKENS: TerminationReason.COMPLETION_TOKEN_LIMIT,
    BudgetDimension.COST: TerminationReason.COST_LIMIT,
    BudgetDimension.ELAPSED_TIME: TerminationReason.TIME_LIMIT,
}


# ---------------------------------------------------------------------------
# Limits (immutable) and usage (monotonic)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RunBudgetLimits:
    """Immutable per-workflow limits.  ``None`` = unconstrained."""

    max_model_calls: Optional[int] = None
    max_tool_calls: Optional[int] = None
    max_prompt_tokens: Optional[int] = None
    max_completion_tokens: Optional[int] = None
    max_total_tokens: Optional[int] = None
    max_cost: Optional[float] = None
    max_elapsed_s: Optional[float] = None
    max_iterations: Optional[int] = None
    max_handoffs: Optional[int] = None

    def limit_for(self, dimension: str) -> Optional[float]:
        return {
            BudgetDimension.MODEL_CALLS: self.max_model_calls,
            BudgetDimension.TOOL_CALLS: self.max_tool_calls,
            BudgetDimension.PROMPT_TOKENS: self.max_prompt_tokens,
            BudgetDimension.COMPLETION_TOKENS: self.max_completion_tokens,
            BudgetDimension.TOTAL_TOKENS: self.max_total_tokens,
            BudgetDimension.COST: self.max_cost,
            BudgetDimension.ELAPSED_TIME: self.max_elapsed_s,
            BudgetDimension.ITERATIONS: self.max_iterations,
            BudgetDimension.HANDOFFS: self.max_handoffs,
        }[dimension]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "max_model_calls": self.max_model_calls,
            "max_tool_calls": self.max_tool_calls,
            "max_prompt_tokens": self.max_prompt_tokens,
            "max_completion_tokens": self.max_completion_tokens,
            "max_total_tokens": self.max_total_tokens,
            "max_cost": self.max_cost,
            "max_elapsed_s": self.max_elapsed_s,
            "max_iterations": self.max_iterations,
            "max_handoffs": self.max_handoffs,
        }


@dataclass
class RunBudgetUsage:
    """Cumulative, monotonically-increasing consumption."""

    model_calls: int = 0
    tool_calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    elapsed_time: float = 0.0
    iterations: int = 0
    handoffs: int = 0

    def value_for(self, dimension: str) -> float:
        return getattr(self, dimension)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "model_calls": self.model_calls,
            "tool_calls": self.tool_calls,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "cost": self.cost,
            "elapsed_time": self.elapsed_time,
            "iterations": self.iterations,
            "handoffs": self.handoffs,
        }


@dataclass
class Reservation:
    """Outcome of a reserve()/can_afford() check."""

    ok: bool
    reason: Optional[str] = None       # TerminationReason.* when not ok
    dimension: Optional[str] = None    # BudgetDimension.* when not ok
    limit: Optional[float] = None
    consumed: Optional[float] = None
    requested: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "reason": self.reason,
            "dimension": self.dimension,
            "limit": self.limit,
            "consumed": self.consumed,
            "requested": self.requested,
        }


@dataclass
class BudgetViolation:
    """A recorded rejection, captured for the trace."""

    dimension: str
    reason: str
    limit: float
    consumed: float
    requested: float
    usage_snapshot: Dict[str, Any] = field(default_factory=dict)


class BudgetExhausted(BaseException):
    """Raised at the model-call seam when a reservation is rejected.

    Subclasses ``BaseException`` (not ``Exception``) on purpose: the
    runtime's decomposition/generation paths wrap work in
    ``except Exception`` fallbacks, and budget termination must *not* be
    swallowed and retried — it must unwind immediately to the workflow
    boundary, which catches it explicitly.
    """

    def __init__(self, reservation: Reservation) -> None:
        self.reservation = reservation
        self.reason = reservation.reason
        self.dimension = reservation.dimension
        super().__init__(
            f"RunBudget exhausted: {reservation.reason} "
            f"(dimension={reservation.dimension}, limit={reservation.limit}, "
            f"consumed={reservation.consumed})"
        )


# ---------------------------------------------------------------------------
# The budget
# ---------------------------------------------------------------------------
class RunBudget:
    """A single cumulative budget shared across an entire workflow.

    Create one at the start of a workflow and pass it to every runtime
    entry point.  Never create a second one for iterations, retries, or
    handoffs — that would reset accounting, which this class exists to
    prevent.

    Args:
        limits: Immutable :class:`RunBudgetLimits`.
        clock: Monotonic time source (injectable for tests). Defaults to
            ``time.monotonic``.
    """

    def __init__(
        self,
        limits: RunBudgetLimits,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._limits = limits
        self._usage = RunBudgetUsage()
        self._clock = clock
        self._start_time: Optional[float] = None
        self._status = RunBudgetStatus.ACTIVE
        self._termination_reason: Optional[str] = None
        self._violations: List[BudgetViolation] = []

    # ----- lifecycle -----
    def start(self) -> "RunBudget":
        """Mark the workflow start (idempotent — first call wins)."""
        if self._start_time is None:
            self._start_time = self._clock()
        return self

    def complete(self) -> None:
        """Mark the workflow finished.  Does not clear counters."""
        if self._status == RunBudgetStatus.ACTIVE:
            self._status = RunBudgetStatus.COMPLETED

    @property
    def limits(self) -> RunBudgetLimits:
        return self._limits

    @property
    def usage(self) -> RunBudgetUsage:
        return self._usage

    @property
    def status(self) -> str:
        return self._status

    @property
    def termination_reason(self) -> Optional[str]:
        return self._termination_reason

    @property
    def violations(self) -> List[BudgetViolation]:
        return list(self._violations)

    def is_exhausted(self) -> bool:
        return self._status == RunBudgetStatus.BUDGET_EXHAUSTED

    # ----- time -----
    def _elapsed(self) -> float:
        if self._start_time is None:
            return 0.0
        return max(0.0, self._clock() - self._start_time)

    def tick(self) -> None:
        """Refresh the elapsed-time counter from the clock (monotonic)."""
        elapsed = self._elapsed()
        if elapsed > self._usage.elapsed_time:
            self._usage.elapsed_time = elapsed
        self._maybe_flag_cumulative()

    # ----- inspection -----
    def remaining(self, dimension: str) -> Optional[float]:
        """Remaining headroom for *dimension* (None = unconstrained).

        Returns an ``int`` for the discrete integer dimensions and a
        ``float`` for cost / elapsed_time, clamped at zero.
        """
        limit = self._limits.limit_for(dimension)
        if limit is None:
            return None
        rem = limit - self._usage.value_for(dimension)
        if rem > 0:
            return rem
        return 0 if isinstance(limit, int) else 0.0

    def _first_violation(self, prospective: Dict[str, float]) -> Optional[Reservation]:
        """Return the first violated dimension (fixed order) or None."""
        for dim in _DIMENSION_ORDER:
            limit = self._limits.limit_for(dim)
            if limit is None:
                continue
            value = prospective.get(dim, self._usage.value_for(dim))
            if value > limit:
                return Reservation(
                    ok=False,
                    reason=_DIMENSION_TO_REASON[dim],
                    dimension=dim,
                    limit=limit,
                    consumed=self._usage.value_for(dim),
                    requested=value - self._usage.value_for(dim),
                )
        return None

    def can_afford(
        self,
        *,
        model_calls: int = 0,
        tool_calls: int = 0,
        iterations: int = 0,
        handoffs: int = 0,
    ) -> Reservation:
        """Non-mutating check of a prospective reservation."""
        self.tick()
        prospective = {
            BudgetDimension.MODEL_CALLS: self._usage.model_calls + model_calls,
            BudgetDimension.TOOL_CALLS: self._usage.tool_calls + tool_calls,
            BudgetDimension.ITERATIONS: self._usage.iterations + iterations,
            BudgetDimension.HANDOFFS: self._usage.handoffs + handoffs,
        }
        violation = self._first_violation(prospective)
        return violation if violation is not None else Reservation(ok=True)

    def reserve(
        self,
        *,
        model_calls: int = 0,
        tool_calls: int = 0,
        iterations: int = 0,
        handoffs: int = 0,
    ) -> Reservation:
        """Reserve discrete resources *before* executing.

        Checks every dimension (including cumulative token/cost/time gates
        from prior recording) in a fixed order.  On the first violation it
        records the violation, flips status to ``BUDGET_EXHAUSTED`` and
        returns a rejected reservation **without mutating** any counter.
        On success it increments the requested discrete counters.
        """
        result = self.can_afford(
            model_calls=model_calls,
            tool_calls=tool_calls,
            iterations=iterations,
            handoffs=handoffs,
        )
        if not result.ok:
            self._record_violation(result)
            return result

        # Reserve (mutate) the discrete counters.
        self._usage.model_calls += model_calls
        self._usage.tool_calls += tool_calls
        self._usage.iterations += iterations
        self._usage.handoffs += handoffs
        return result

    # ----- post-hoc accounting -----
    def record_usage(
        self,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost: float = 0.0,
        tool_calls: int = 0,
    ) -> None:
        """Record consumption known only *after* an operation ran.

        Token counts and cost come from the model call that just
        completed; ``tool_calls`` is recorded from the governed trace.
        All additions are monotonic.  If a cumulative limit is now
        exceeded the status flips to ``BUDGET_EXHAUSTED`` so the *next*
        reservation gate blocks — the operation that produced this usage
        is not retroactively undone.
        """
        if prompt_tokens:
            self._usage.prompt_tokens += prompt_tokens
        if completion_tokens:
            self._usage.completion_tokens += completion_tokens
        self._usage.total_tokens = (
            self._usage.prompt_tokens + self._usage.completion_tokens
        )
        if cost:
            self._usage.cost += cost
        if tool_calls:
            self._usage.tool_calls += tool_calls
        self._maybe_flag_cumulative()

    def _maybe_flag_cumulative(self) -> None:
        """Flip to exhausted if any cumulative gate is now over limit."""
        if self._status == RunBudgetStatus.COMPLETED:
            return
        violation = self._first_violation({})
        if violation is not None and self._status != RunBudgetStatus.BUDGET_EXHAUSTED:
            self._record_violation(violation)

    def _record_violation(self, reservation: Reservation) -> None:
        self._status = RunBudgetStatus.BUDGET_EXHAUSTED
        if self._termination_reason is None:
            self._termination_reason = reservation.reason
        self._violations.append(
            BudgetViolation(
                dimension=reservation.dimension,
                reason=reservation.reason,
                limit=reservation.limit if reservation.limit is not None else 0.0,
                consumed=reservation.consumed if reservation.consumed is not None else 0.0,
                requested=reservation.requested if reservation.requested is not None else 0.0,
                usage_snapshot=self._usage.to_dict(),
            )
        )

    # ----- trace / reporting -----
    def snapshot(self) -> Dict[str, Any]:
        """A complete, JSON-safe reconstruction of budget state."""
        remaining = {
            dim: self.remaining(dim) for dim in _DIMENSION_ORDER
        }
        return {
            "status": self._status,
            "termination_reason": self._termination_reason,
            "limits": self._limits.to_dict(),
            "consumed": self._usage.to_dict(),
            "remaining": remaining,
            "violations": [
                {
                    "dimension": v.dimension,
                    "reason": v.reason,
                    "limit": v.limit,
                    "consumed": v.consumed,
                    "requested": v.requested,
                }
                for v in self._violations
            ],
        }


# ---------------------------------------------------------------------------
# Adapter wrapper — reserve model calls, record tokens/cost
# ---------------------------------------------------------------------------
class BudgetedAdapter:
    """Wrap any LLM adapter so each ``call()`` consumes from a RunBudget.

    Reserves ``model_calls=1`` (and re-checks all cumulative gates)
    *before* delegating; a rejection raises :class:`BudgetExhausted`.
    After a successful call it records the prompt/completion tokens and
    cost (exact from ``get_last_usage()`` when available, else estimated).

    Everything else (``get_last_usage``, ``last_cg_metadata``, ``IS_STUB``,
    ``call_with_messages`` …) is delegated to the wrapped adapter.
    """

    #: Marker so wrapping is idempotent and detectable.
    IS_BUDGETED = True

    def __init__(self, inner: Any, budget: RunBudget) -> None:
        self._inner = inner
        self._run_budget = budget

    def _consume(self, prompt: str, result: str) -> None:
        usage = None
        try:
            usage = self._inner.get_last_usage()
        except Exception:
            usage = None
        if usage:
            prompt_tokens = int(usage.get("input_tokens", 0) or 0)
            completion_tokens = int(usage.get("output_tokens", 0) or 0)
            cost = float(usage.get("cost", 0.0) or 0.0)
            if prompt_tokens == 0 and completion_tokens == 0:
                prompt_tokens = estimate_tokens(prompt)
                completion_tokens = estimate_tokens(result)
        else:
            prompt_tokens = estimate_tokens(prompt)
            completion_tokens = estimate_tokens(result)
            cost = 0.0
        self._run_budget.record_usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost=cost,
        )

    def call(self, prompt: str) -> str:
        reservation = self._run_budget.reserve(model_calls=1)
        if not reservation.ok:
            raise BudgetExhausted(reservation)
        result = self._inner.call(prompt)
        self._consume(prompt, result)
        return result

    def call_stream(self, prompt: str):
        reservation = self._run_budget.reserve(model_calls=1)
        if not reservation.ok:
            raise BudgetExhausted(reservation)
        chunks = []
        for chunk in self._inner.call_stream(prompt):
            chunks.append(chunk)
            yield chunk
        self._consume(prompt, "".join(str(c) for c in chunks))

    def __getattr__(self, name: str) -> Any:
        # Delegate any attribute we don't define to the wrapped adapter.
        return getattr(self._inner, name)


def attach_run_budget(agent: Any, budget: RunBudget) -> None:
    """Install *budget* on *agent* so all its model calls are counted.

    Wraps the agent's shared adapter with a :class:`BudgetedAdapter` and
    repoints both the agent and its reflective generator at the wrapper.
    Idempotent for the same budget; re-points to a new budget cleanly.
    """
    current = getattr(agent, "llm", None)
    if current is None:
        return

    # Already wrapped?
    if getattr(current, "IS_BUDGETED", False):
        if getattr(current, "_run_budget", None) is budget:
            return  # same budget → nothing to do
        inner = getattr(current, "_inner", current)
    else:
        inner = current

    wrapper = BudgetedAdapter(inner, budget)
    agent.llm = wrapper
    generator = getattr(agent, "generator", None)
    if generator is not None and hasattr(generator, "llm"):
        generator.llm = wrapper


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------
def format_run_budget(budget: RunBudget) -> str:
    """Human-readable multi-line summary of a RunBudget's state."""
    snap = budget.snapshot()
    limits = snap["limits"]
    consumed = snap["consumed"]
    lines = [
        "RunBudget",
        "=" * 40,
        f"  status:            {snap['status']}",
        f"  termination:       {snap['termination_reason'] or '(none)'}",
        "",
        "  dimension           consumed / limit    remaining",
        "  " + "-" * 46,
    ]
    label = {
        BudgetDimension.MODEL_CALLS: "model_calls",
        BudgetDimension.TOOL_CALLS: "tool_calls",
        BudgetDimension.ITERATIONS: "iterations",
        BudgetDimension.HANDOFFS: "handoffs",
        BudgetDimension.TOTAL_TOKENS: "total_tokens",
        BudgetDimension.PROMPT_TOKENS: "prompt_tokens",
        BudgetDimension.COMPLETION_TOKENS: "completion_tokens",
        BudgetDimension.COST: "cost",
        BudgetDimension.ELAPSED_TIME: "elapsed_time",
    }
    limit_key = {
        BudgetDimension.MODEL_CALLS: "max_model_calls",
        BudgetDimension.TOOL_CALLS: "max_tool_calls",
        BudgetDimension.ITERATIONS: "max_iterations",
        BudgetDimension.HANDOFFS: "max_handoffs",
        BudgetDimension.TOTAL_TOKENS: "max_total_tokens",
        BudgetDimension.PROMPT_TOKENS: "max_prompt_tokens",
        BudgetDimension.COMPLETION_TOKENS: "max_completion_tokens",
        BudgetDimension.COST: "max_cost",
        BudgetDimension.ELAPSED_TIME: "max_elapsed_s",
    }
    for dim in _DIMENSION_ORDER:
        lim = limits[limit_key[dim]]
        used = consumed[dim]
        rem = snap["remaining"][dim]
        lim_s = "∞" if lim is None else str(lim)
        rem_s = "∞" if rem is None else (f"{rem:.4f}" if isinstance(rem, float) else str(rem))
        used_s = f"{used:.4f}" if isinstance(used, float) else str(used)
        lines.append(f"  {label[dim]:<18} {used_s:>8} / {lim_s:<8}  {rem_s:>10}")
    if snap["violations"]:
        lines.append("")
        lines.append("  violations:")
        for v in snap["violations"]:
            lines.append(f"    - {v['reason']} ({v['dimension']}: {v['consumed']}/{v['limit']})")
    return "\n".join(lines)
