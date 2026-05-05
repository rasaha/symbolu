"""Real-time / no-allocation hot path + p999 budget framework.

Public surface (provisional, see ``API_STABILITY.md`` §2.2 +
``REAL_TIME_BUDGET_DESIGN.md`` §9):

* :class:`RealTimeBudget` — typed budget contract (target_hz +
  per-tier ms thresholds + sample-count gates).
* :class:`LatencyMonitor` — per-tick observer with budget
  enforcement, percentile reporting, over-budget audit trail.
* :class:`BudgetSummary` — typed verdict from
  :meth:`LatencyMonitor.summary`.
* :class:`OverBudgetTick` — one row of the over-budget audit log.
* :class:`AllocationTrace` — advisory per-tick allocation
  deltas (via tracemalloc; see §6).
* :class:`RealTimeBudgetError` /
  :class:`BudgetViolationError` — exception hierarchy.

See ``REAL_TIME_BUDGET_DESIGN.md`` for the full design.
"""

from .budget import (
    AllocationTrace,
    BudgetSummary,
    OverBudgetTick,
    RealTimeBudget,
)
from .errors import BudgetViolationError, RealTimeBudgetError
from .monitor import LatencyMonitor


__all__ = [
    # Budget contract
    "RealTimeBudget",
    "OverBudgetTick",
    "AllocationTrace",
    "BudgetSummary",
    # Monitor
    "LatencyMonitor",
    # Errors
    "RealTimeBudgetError",
    "BudgetViolationError",
]
