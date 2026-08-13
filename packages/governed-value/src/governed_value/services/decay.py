"""Per-period recompute — ROI is a rate that decays, not a one-time number.

Drift erodes realized value, so governed value should be recomputed each period
with the decay term advanced. :func:`project_periods` re-scores a case across a
horizon, advancing ``periods_elapsed`` so callers can see NGVA fall as drift
accrues and decide when re-tuning is worth its cost.
"""

from __future__ import annotations

from dataclasses import replace

from ..domain.case import AgentValueCase
from .scorer import GovernedValueResult, score_case

__all__ = ["project_periods"]


def project_periods(case: AgentValueCase, horizon: int) -> list[GovernedValueResult]:
    """Score ``case`` at periods ``0..horizon`` inclusive, advancing decay.

    The case's own ``periods_elapsed`` is the starting offset; each projected
    period adds to it, so a case already 2 periods in projects 2, 3, 4, …
    """

    if horizon < 0:
        raise ValueError("horizon must be >= 0")
    base = case.attribution.periods_elapsed
    results: list[GovernedValueResult] = []
    for step in range(horizon + 1):
        attribution = replace(case.attribution, periods_elapsed=base + step)
        results.append(score_case(replace(case, attribution=attribution)))
    return results
