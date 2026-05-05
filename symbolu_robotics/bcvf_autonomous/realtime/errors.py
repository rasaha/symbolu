"""Exceptions raised by the real-time-budget surface.

Two layers:

* :class:`RealTimeBudgetError` — base class. A buyer's
  integration-test script can ``except RealTimeBudgetError``
  to catch every budget-specific failure without catching
  unrelated ``ValueError`` slips.
* :class:`BudgetViolationError` — subclass raised by callers
  who choose to escalate a budget violation to an exception
  (e.g. a CI integration test that fails the build on any
  p999 violation). The framework does NOT raise this from
  :meth:`LatencyMonitor.observe` — observation is non-
  fatal so the monitor can capture every violation; the
  caller decides whether a violation halts the pipeline.

The base class is the one a downstream caller catches; the
subclass is the one CI gates assert on.
"""

from __future__ import annotations


class RealTimeBudgetError(Exception):
    """Base class for real-time-budget errors.

    Raised on:

    * Invalid :class:`RealTimeBudget` field combinations at
      construction (e.g. ``p999_budget_ms < p99_budget_ms``,
      negative ms values).
    * Type mismatches in :meth:`LatencyMonitor.observe`
      (non-numeric ``elapsed_ms``).
    """


class BudgetViolationError(RealTimeBudgetError):
    """Raised by callers who choose to escalate a budget
    violation to an exception.

    Not raised by :meth:`LatencyMonitor.observe` itself —
    observation is non-fatal so the monitor can capture every
    violation; the caller decides whether to escalate. A
    typical pattern:

        summary = monitor.summary()
        if not summary.meets_budget:
            raise BudgetViolationError(
                f"{summary.n_p999_violations} p999 violations"
            )
    """
