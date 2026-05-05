"""``RealTimeBudget`` — typed budget contract for AUTOSAR-class deployments.

A :class:`RealTimeBudget` is a frozen dataclass an integrator
copies into their config. Every knob is validated at
construction; AUTOSAR partners override per their tier. See
``REAL_TIME_BUDGET_DESIGN.md`` §2 for the per-field rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from .errors import RealTimeBudgetError


@dataclass(frozen=True)
class RealTimeBudget:
    """The §2 budget contract.

    Defaults target a 100 Hz drone-tier deployment with sensible
    headroom; AUTOSAR-class callers override per their tier.
    """

    #: Target tick rate. Establishes the deadline
    #: ``1000 / target_hz`` ms. Common values: 100 Hz (drone),
    #: 50 Hz (industrial), 10 Hz (automotive).
    target_hz: float = 100.0

    #: 1-in-100 tick budget. The headroom under deadline.
    p99_budget_ms: float = 8.0

    #: 1-in-1000 tick budget. The AUTOSAR-class question.
    p999_budget_ms: float = 9.5

    #: 1-in-10000 tick budget — the deadline itself by design.
    p9999_budget_ms: float = 10.0

    #: Absolute worst-case. A single tick exceeding this is a
    #: hard violation. Default 1.5× deadline.
    max_budget_ms: float = 15.0

    #: Below this sample count, p999 is not reported (n=10
    #: doesn't define a 1-in-1000 percentile). Defaults to
    #: 10× the percentile denominator.
    min_samples_for_p999: int = 1000

    #: Same discipline for p9999 — 10× the denominator.
    min_samples_for_p9999: int = 10000

    #: Ring-buffer capacity for over-budget tick records.
    #: Prevents the audit log from growing unbounded under
    #: sustained violations.
    over_budget_log_capacity: int = 100

    def __post_init__(self) -> None:
        if self.target_hz <= 0:
            raise RealTimeBudgetError(
                f"target_hz must be positive; got {self.target_hz}"
            )
        for name, value in (
            ("p99_budget_ms", self.p99_budget_ms),
            ("p999_budget_ms", self.p999_budget_ms),
            ("p9999_budget_ms", self.p9999_budget_ms),
            ("max_budget_ms", self.max_budget_ms),
        ):
            if value <= 0:
                raise RealTimeBudgetError(
                    f"{name} must be positive; got {value}"
                )
        # Budgets must be monotone non-decreasing as the
        # percentile becomes rarer: a tighter p999 than p99 is a
        # configuration error (p999 includes p99's worst ticks
        # plus the worst 9-in-1000 between them).
        if self.p999_budget_ms < self.p99_budget_ms:
            raise RealTimeBudgetError(
                f"p999_budget_ms ({self.p999_budget_ms}) must be ≥ "
                f"p99_budget_ms ({self.p99_budget_ms}) — rarer "
                "percentiles are at least as loose as more common ones"
            )
        if self.p9999_budget_ms < self.p999_budget_ms:
            raise RealTimeBudgetError(
                f"p9999_budget_ms ({self.p9999_budget_ms}) must be ≥ "
                f"p999_budget_ms ({self.p999_budget_ms})"
            )
        if self.max_budget_ms < self.p9999_budget_ms:
            raise RealTimeBudgetError(
                f"max_budget_ms ({self.max_budget_ms}) must be ≥ "
                f"p9999_budget_ms ({self.p9999_budget_ms}) — the "
                "absolute worst-case must accommodate the bleeding-"
                "edge percentile"
            )
        if self.min_samples_for_p999 < 100:
            raise RealTimeBudgetError(
                f"min_samples_for_p999 ({self.min_samples_for_p999}) "
                "must be ≥ 100 — a smaller sample count produces "
                "statistically meaningless p999 reports"
            )
        if self.min_samples_for_p9999 < 1000:
            raise RealTimeBudgetError(
                f"min_samples_for_p9999 ({self.min_samples_for_p9999}) "
                "must be ≥ 1000"
            )
        if self.over_budget_log_capacity < 1:
            raise RealTimeBudgetError(
                f"over_budget_log_capacity must be ≥ 1; got "
                f"{self.over_budget_log_capacity}"
            )

    @property
    def deadline_ms(self) -> float:
        """The deadline implied by ``target_hz`` (= 1000 / target_hz)."""
        return 1000.0 / self.target_hz

    def to_dict(self) -> dict:
        """Plain-dict view for config-roundtrip + JSON
        serialisation (e.g. carrying the budget into a
        :class:`ReplayBundle`'s ``run_config``)."""
        return {
            "target_hz": float(self.target_hz),
            "p99_budget_ms": float(self.p99_budget_ms),
            "p999_budget_ms": float(self.p999_budget_ms),
            "p9999_budget_ms": float(self.p9999_budget_ms),
            "max_budget_ms": float(self.max_budget_ms),
            "min_samples_for_p999": int(self.min_samples_for_p999),
            "min_samples_for_p9999": int(self.min_samples_for_p9999),
            "over_budget_log_capacity": int(
                self.over_budget_log_capacity
            ),
        }


@dataclass(frozen=True)
class OverBudgetTick:
    """One tick that exceeded a budget tier.

    Recorded by :class:`LatencyMonitor` in a ring buffer (sized
    by ``budget.over_budget_log_capacity``). A recall investigator
    opening a :class:`BudgetSummary` reads these to localise
    which ticks violated which tier — pairs cleanly with
    ``replay_bundle()`` for root-cause investigation of the
    specific code path responsible.
    """

    tick_index: int
    observed_ms: float
    #: One of "p99" / "p999" / "p9999" / "max" — the most-strict
    #: budget tier the observation violated.
    budget_tier: str
    threshold_ms: float


@dataclass(frozen=True)
class AllocationTrace:
    """Advisory per-tick allocation deltas (via ``tracemalloc``).

    Pure-Python "zero allocations" is not achievable inside
    CPython (the interpreter allocates frame objects + intermediate
    references on every call). The framework reports the deltas
    so a deployment partner can diagnose hotspots, but does NOT
    enforce a zero-allocation contract — that's the C++ port's
    surface (out of scope, see ``REAL_TIME_BUDGET_DESIGN.md`` §6 + §8).
    """

    n_observations: int
    mean_bytes_per_tick: float
    p99_bytes_per_tick: float
    max_bytes_per_tick: int


@dataclass(frozen=True)
class BudgetSummary:
    """The verdict of one :meth:`LatencyMonitor.summary` call.

    Fields ``p999_ms`` / ``p9999_ms`` are ``None`` when the
    sample count is below the documented threshold —
    intentional, see ``REAL_TIME_BUDGET_DESIGN.md`` §4. Downstream
    code that ignores ``None`` gets a clear ``TypeError`` rather
    than a fake number; this is the percentile-availability
    discipline.
    """

    n_observations: int
    mean_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    p999_ms: float  # may be None — see § note above (typed Optional below)
    p9999_ms: float  # may be None — see § note above
    max_ms: float
    n_p99_violations: int
    n_p999_violations: int
    n_p9999_violations: int
    n_max_violations: int
    over_budget_ticks: Tuple[OverBudgetTick, ...]
    budget: RealTimeBudget
    meets_budget: bool
    allocation_trace: object = None  # AllocationTrace | None

    def to_dict(self) -> dict:
        """Plain-dict view for JSON serialisation. Carries the
        budget contract + the violation roll-up + the over-
        budget audit trail."""
        return {
            "n_observations": int(self.n_observations),
            "mean_ms": float(self.mean_ms),
            "p50_ms": float(self.p50_ms),
            "p95_ms": float(self.p95_ms),
            "p99_ms": float(self.p99_ms),
            "p999_ms": (
                None if self.p999_ms is None else float(self.p999_ms)
            ),
            "p9999_ms": (
                None if self.p9999_ms is None else float(self.p9999_ms)
            ),
            "max_ms": float(self.max_ms),
            "n_p99_violations": int(self.n_p99_violations),
            "n_p999_violations": int(self.n_p999_violations),
            "n_p9999_violations": int(self.n_p9999_violations),
            "n_max_violations": int(self.n_max_violations),
            "over_budget_ticks": [
                {
                    "tick_index": int(t.tick_index),
                    "observed_ms": float(t.observed_ms),
                    "budget_tier": t.budget_tier,
                    "threshold_ms": float(t.threshold_ms),
                }
                for t in self.over_budget_ticks
            ],
            "budget": self.budget.to_dict(),
            "meets_budget": bool(self.meets_budget),
        }
