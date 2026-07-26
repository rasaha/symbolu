"""Comparative governance-cost model (Task 10).

Counts structural governance workload — NOT latency or money. Reports totals,
averages, and cost-effectiveness measures (extra governance operations per unsafe
execution prevented; extra human reviews per unsupported assertion contained).
These are workload indicators, never financial ROI.
"""
from __future__ import annotations

from ..schemas.safety import UNSAFE_OUTCOMES
from ..strategies.protocol import COST_KEYS


def cost_totals(results: list) -> dict:
    total = {k: 0 for k in COST_KEYS}
    for r in results:
        for k in COST_KEYS:
            total[k] += r.cost.get(k, 0)
    total["provider_failures"] = sum(r.provider_failures for r in results)
    return total


def _total_ops(total: dict) -> int:
    return sum(total[k] for k in COST_KEYS)


def summarize(results: list, judgements: list) -> dict:
    total = cost_totals(results)
    n = len(results)
    executions = sum(1 for r in results if r.dispatched)
    unsafe = sum(1 for j in judgements if j.safety_outcome in UNSAFE_OUTCOMES)
    return {
        "total": total,
        "total_operations": _total_ops(total),
        "avg_per_scenario": {k: round(v / n, 4) for k, v in total.items()} if n else {},
        "avg_operations_per_scenario": round(_total_ops(total) / n, 4) if n else 0,
        "avg_operations_per_execution": round(_total_ops(total) / executions, 4) if executions else None,
        "executions": executions,
        "unsafe_outcomes": unsafe,
    }


def effectiveness(strategy_summary: dict, strategy_unsafe: int,
                  baseline_summary: dict, baseline_unsafe: int,
                  unsupported_contained: int, human_reviews: int) -> dict:
    """Cost-effectiveness of a strategy relative to the no-governance baseline."""
    prevented = max(0, baseline_unsafe - strategy_unsafe)
    extra_ops = strategy_summary["total_operations"] - baseline_summary["total_operations"]
    return {
        "unsafe_prevented_vs_baseline": prevented,
        "additional_governance_operations": extra_ops,
        "additional_operations_per_unsafe_prevented":
            round(extra_ops / prevented, 4) if prevented else None,
        "additional_human_reviews_per_unsupported_contained":
            round(human_reviews / unsupported_contained, 4) if unsupported_contained else None,
        "note": "structural workload indicators, not financial ROI",
    }
