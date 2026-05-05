"""``LatencyMonitor`` — per-tick latency observer with budget enforcement.

Designed for the hot-path-adjacent role: the planner times
itself; the monitor wraps the per-tick measurement, classifies
each tick against the budget, records over-budget violations,
and computes percentile statistics on demand.

The monitor is intentionally NOT integrated into the planner's
internal hot path by default — the planner keeps its existing
``solve_time_ms`` capture; the monitor wraps from outside. See
``REAL_TIME_BUDGET_DESIGN.md`` §3 for the rationale.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Deque, List, Optional

import numpy as np

from .budget import (
    AllocationTrace,
    BudgetSummary,
    OverBudgetTick,
    RealTimeBudget,
)
from .errors import RealTimeBudgetError


class LatencyMonitor:
    """Per-tick latency observer.

    Args:
        budget: the :class:`RealTimeBudget` to enforce.
        track_allocations: when ``True``, the monitor uses
            :mod:`tracemalloc` to record per-tick allocation
            deltas. Advisory — see
            ``REAL_TIME_BUDGET_DESIGN.md`` §6 for the framing
            (no-allocation in pure Python is not achievable;
            the framework reports, doesn't enforce).

    Usage::

        monitor = LatencyMonitor(budget=RealTimeBudget())
        for tick_index in range(n_ticks):
            start = time.perf_counter()
            planner.plan()
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            monitor.observe(elapsed_ms, tick_index=tick_index)

        summary = monitor.summary()
        if not summary.meets_budget:
            log.warning("budget violations: %s", summary.over_budget_ticks)
    """

    def __init__(
        self,
        budget: RealTimeBudget,
        *,
        track_allocations: bool = False,
    ) -> None:
        if not isinstance(budget, RealTimeBudget):
            raise RealTimeBudgetError(
                f"budget must be a RealTimeBudget; got "
                f"{type(budget).__name__}"
            )
        self._budget = budget
        self._track_allocations = bool(track_allocations)
        self._observations: List[float] = []
        # Per-tier violation counters incremented in observe()
        # so summary() is O(1) for the violation-count fields.
        self._n_p99_violations: int = 0
        self._n_p999_violations: int = 0
        self._n_p9999_violations: int = 0
        self._n_max_violations: int = 0
        self._over_budget: Deque[OverBudgetTick] = deque(
            maxlen=budget.over_budget_log_capacity
        )
        # Allocation tracking — lazy-initialised tracemalloc
        # instance per monitor (don't enable globally).
        self._alloc_deltas: List[int] = []
        # Audit-fix Finding 3: track whether THIS monitor enabled
        # tracemalloc, so close() only stops it if we own it. A
        # monitor that finds tracemalloc already running (started
        # by the caller or another component) leaves it running
        # on close.
        self._we_started_tracemalloc: bool = False
        if self._track_allocations:
            import tracemalloc
            self._tracemalloc = tracemalloc
            if not tracemalloc.is_tracing():
                tracemalloc.start()
                self._we_started_tracemalloc = True
            self._alloc_baseline = tracemalloc.get_traced_memory()[0]
        else:
            self._tracemalloc = None
            self._alloc_baseline = 0

    # ----- public properties ----- #

    @property
    def budget(self) -> RealTimeBudget:
        return self._budget

    @property
    def n_observations(self) -> int:
        return len(self._observations)

    @property
    def track_allocations(self) -> bool:
        return self._track_allocations

    # ----- observation ----- #

    def observe(self, elapsed_ms: float, *, tick_index: int) -> None:
        """Record one per-tick latency observation.

        ``elapsed_ms`` must be a non-negative number; ``tick_index``
        is the caller's tick identifier (typically a monotonically
        increasing per-episode counter).

        The observation is non-fatal: a tick that violates a
        budget tier increments the corresponding counter +
        appends to the over-budget ring buffer, but does NOT
        raise. The caller decides whether to escalate (via the
        :meth:`summary` ``meets_budget`` check + an explicit
        :class:`BudgetViolationError`).
        """
        # Audit-fix Finding 4: reject bool — `True isinstance int`
        # is True in Python, so the previous guard let
        # ``mon.observe(True, tick_index=i)`` slip through and
        # contribute 1.0 to the latency series. Accept numpy
        # scalars (np.int64, np.floating) explicitly because
        # ``arr[i]`` produces those when iterating an ndarray.
        if isinstance(elapsed_ms, bool) or not isinstance(
            elapsed_ms, (int, float, np.floating, np.integer)
        ):
            raise RealTimeBudgetError(
                f"elapsed_ms must be a number; got "
                f"{type(elapsed_ms).__name__}"
            )
        elapsed_ms = float(elapsed_ms)
        # Audit-fix Finding 2: reject NaN + ±Inf. NaN comparisons
        # are all False, so a NaN tick used to pass every tier
        # check + leave meets_budget=True while polluting
        # mean_ms / max_ms / p99_ms with NaN. The CI gate would
        # silently pass — exactly the failure mode the framework
        # exists to prevent.
        if not math.isfinite(elapsed_ms):
            raise RealTimeBudgetError(
                f"elapsed_ms must be finite; got {elapsed_ms} "
                "(NaN / Inf would silently corrupt every percentile)"
            )
        if elapsed_ms < 0:
            raise RealTimeBudgetError(
                f"elapsed_ms must be ≥ 0; got {elapsed_ms}"
            )
        self._observations.append(elapsed_ms)

        # Classify against the most-strict tier first. Each
        # observation increments at most ONE tier counter — the
        # tightest one it violated. This way the summary's
        # n_p99_violations counts ticks that exceeded p99 but
        # not p999, n_p999_violations counts ticks that
        # exceeded p999 but not p9999, etc. Mutually-exclusive
        # tiers make the audit trail unambiguous.
        if elapsed_ms > self._budget.max_budget_ms:
            self._n_max_violations += 1
            self._over_budget.append(OverBudgetTick(
                tick_index=int(tick_index),
                observed_ms=elapsed_ms,
                budget_tier="max",
                threshold_ms=self._budget.max_budget_ms,
            ))
        elif elapsed_ms > self._budget.p9999_budget_ms:
            self._n_p9999_violations += 1
            self._over_budget.append(OverBudgetTick(
                tick_index=int(tick_index),
                observed_ms=elapsed_ms,
                budget_tier="p9999",
                threshold_ms=self._budget.p9999_budget_ms,
            ))
        elif elapsed_ms > self._budget.p999_budget_ms:
            self._n_p999_violations += 1
            self._over_budget.append(OverBudgetTick(
                tick_index=int(tick_index),
                observed_ms=elapsed_ms,
                budget_tier="p999",
                threshold_ms=self._budget.p999_budget_ms,
            ))
        elif elapsed_ms > self._budget.p99_budget_ms:
            self._n_p99_violations += 1
            self._over_budget.append(OverBudgetTick(
                tick_index=int(tick_index),
                observed_ms=elapsed_ms,
                budget_tier="p99",
                threshold_ms=self._budget.p99_budget_ms,
            ))

        # Allocation tracking — record the per-tick delta against
        # the baseline. Note: this measures the cumulative
        # tracemalloc-tracked bytes, NOT the GC'd transient
        # allocations of this single tick (Python's transient
        # allocations are released before tracemalloc samples
        # them). Useful for long-term leak detection; not for
        # per-tick allocation profiling. See
        # REAL_TIME_BUDGET_DESIGN.md §6 + §8 for the
        # advisory-not-contractual framing.
        if self._tracemalloc is not None:
            current = self._tracemalloc.get_traced_memory()[0]
            delta = current - self._alloc_baseline
            self._alloc_deltas.append(max(0, delta))
            self._alloc_baseline = current

    def observe_series(
        self,
        series,  # np.ndarray | Sequence[float]
        *,
        tick_offset: int = 0,
    ) -> None:
        """Bulk-observe a per-tick latency series. Convenience
        for replaying a recorded ``EpisodeDiagnostics.solve_times_ms``
        through the monitor without a manual loop.

        ``tick_offset`` is added to each tick's index so a caller
        replaying multiple episodes through one monitor can
        keep tick indices unique across episodes.
        """
        arr = np.asarray(series, dtype=np.float64)
        if arr.ndim != 1:
            raise RealTimeBudgetError(
                f"series must be 1-D; got shape {arr.shape}"
            )
        # Audit-fix Finding 2 (companion): reject NaN / Inf at
        # the bulk-ingest gate so a single bad sample doesn't
        # silently pollute every downstream percentile.
        if not np.isfinite(arr).all():
            raise RealTimeBudgetError(
                "series contains non-finite values (NaN / Inf); "
                "latency must be finite"
            )
        if (arr < 0).any():
            raise RealTimeBudgetError(
                "series contains negative values; latency must be ≥ 0"
            )
        for i, val in enumerate(arr):
            self.observe(float(val), tick_index=tick_offset + i)

    # ----- summary ----- #

    def summary(self) -> BudgetSummary:
        """Compute the typed verdict.

        Percentile-availability discipline: ``p999_ms`` is
        ``None`` when ``n < min_samples_for_p999``; same for
        ``p9999_ms``. Downstream code that ignores ``None``
        gets a clear ``TypeError`` rather than a fake number.
        See ``REAL_TIME_BUDGET_DESIGN.md`` §4.
        """
        n = len(self._observations)
        if n == 0:
            # Audit-fix Finding 6: empty-monitor percentiles must
            # be None (not 0.0). The %4 percentile-availability
            # discipline already returns None for p999/p9999
            # below the sample-count threshold; an empty monitor
            # is a stronger version of the same case. Returning
            # 0.0 used to silently pass a CI gate of the form
            # ``if summary.p99_ms > budget.p99_budget_ms``
            # when no observations had been recorded.
            return BudgetSummary(
                n_observations=0,
                mean_ms=None,
                p50_ms=None,
                p95_ms=None,
                p99_ms=None,
                p999_ms=None,
                p9999_ms=None,
                max_ms=None,
                n_p99_violations=0,
                n_p999_violations=0,
                n_p9999_violations=0,
                n_max_violations=0,
                over_budget_ticks=tuple(self._over_budget),
                budget=self._budget,
                meets_budget=True,
                allocation_trace=self._allocation_trace(),
            )
        arr = np.asarray(self._observations, dtype=np.float64)
        # Percentile-availability gate: don't report p999 / p9999
        # below the documented sample-count threshold.
        p999 = (
            float(np.percentile(arr, 99.9))
            if n >= self._budget.min_samples_for_p999
            else None
        )
        p9999 = (
            float(np.percentile(arr, 99.99))
            if n >= self._budget.min_samples_for_p9999
            else None
        )
        meets = (
            self._n_p99_violations == 0
            and self._n_p999_violations == 0
            and self._n_p9999_violations == 0
            and self._n_max_violations == 0
        )
        return BudgetSummary(
            n_observations=n,
            mean_ms=float(arr.mean()),
            p50_ms=float(np.percentile(arr, 50)),
            p95_ms=float(np.percentile(arr, 95)),
            p99_ms=float(np.percentile(arr, 99)),
            p999_ms=p999,
            p9999_ms=p9999,
            max_ms=float(arr.max()),
            n_p99_violations=self._n_p99_violations,
            n_p999_violations=self._n_p999_violations,
            n_p9999_violations=self._n_p9999_violations,
            n_max_violations=self._n_max_violations,
            over_budget_ticks=tuple(self._over_budget),
            budget=self._budget,
            meets_budget=meets,
            allocation_trace=self._allocation_trace(),
        )

    def _allocation_trace(self) -> Optional[AllocationTrace]:
        if not self._track_allocations or not self._alloc_deltas:
            return None
        arr = np.asarray(self._alloc_deltas, dtype=np.int64)
        return AllocationTrace(
            n_observations=len(arr),
            mean_bytes_per_tick=float(arr.mean()),
            p99_bytes_per_tick=float(np.percentile(arr, 99)),
            max_bytes_per_tick=int(arr.max()),
        )

    # ----- ops ----- #

    def reset(self) -> None:
        """Clear all observations + violation counts + the
        over-budget ring buffer. Use between episodes if a
        caller wants per-episode summaries instead of cross-
        episode aggregates.

        Does NOT change the budget itself — re-instantiate the
        monitor to swap budgets. Does NOT stop tracemalloc — call
        :meth:`close` for that.
        """
        self._observations = []
        self._n_p99_violations = 0
        self._n_p999_violations = 0
        self._n_p9999_violations = 0
        self._n_max_violations = 0
        self._over_budget.clear()
        self._alloc_deltas = []
        if self._tracemalloc is not None and self._tracemalloc.is_tracing():
            self._alloc_baseline = self._tracemalloc.get_traced_memory()[0]
        else:
            self._alloc_baseline = 0

    def close(self) -> None:
        """Release the monitor's tracemalloc resource (if any).

        Audit-fix Finding 3: ``tracemalloc.start()`` is a global
        enable; without an explicit ``close()`` the tracer
        stayed on for the rest of the process even after the
        monitor went out of scope. ``close()`` stops tracemalloc
        only if THIS monitor enabled it (other components that
        had it running keep theirs).

        Idempotent: calling ``close()`` twice is a no-op on the
        second call. After ``close()``, ``observe()`` still
        works but allocation tracking is disabled.
        """
        if (
            self._we_started_tracemalloc
            and self._tracemalloc is not None
            and self._tracemalloc.is_tracing()
        ):
            self._tracemalloc.stop()
        self._we_started_tracemalloc = False
        self._tracemalloc = None
        self._alloc_baseline = 0
        self._track_allocations = False

    def __enter__(self) -> "LatencyMonitor":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
