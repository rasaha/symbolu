"""Cost estimation and a hard execution guard.

Real runs cost money; this computes a dry-run estimate and worst-case spend, and
aborts BEFORE exceeding an explicit cap. In self-test (stub) mode, real API cost
is $0, but the same routine reports the *modeled* cost (registry price x tokens)
so the economics are visible and the guard path is exercised.
"""
from __future__ import annotations

from typing import Any, Dict, List

from common import approx_tokens


class CostCapExceeded(RuntimeError):
    pass


class CostGuard:
    def __init__(self, max_spend_usd: float):
        self.max_spend_usd = max_spend_usd
        self.spent = 0.0

    def check(self, next_cost: float) -> None:
        if self.spent + next_cost > self.max_spend_usd:
            raise CostCapExceeded(f"next call ${next_cost:.4f} would exceed cap "
                                  f"${self.max_spend_usd:.2f} (spent ${self.spent:.4f})")

    def charge(self, cost: float) -> None:
        self.spent += cost


def model_call_cost(model: Dict[str, Any], in_tokens: int, out_tokens: int) -> float:
    price = model["provider_facts"]["pricing_per_mtok"]["value"]
    return (price["in"] * in_tokens + price["out"] * out_tokens) / 1_000_000.0


def estimate_task_cost(model: Dict[str, Any], task: Dict[str, Any], est_out_tokens: int = 200) -> float:
    in_tokens = approx_tokens(task["input_text"]) + 80
    return model_call_cost(model, in_tokens, est_out_tokens)


def dry_run(registry: Dict[str, Any], tasks: List[Dict[str, Any]],
            eligible_fn, worst_case_retries: int = 2) -> Dict[str, Any]:
    """Estimate total and worst-case spend for a full counterfactual over `tasks`."""
    models = registry["models"]
    per_model: Dict[str, float] = {m: 0.0 for m in models}
    total = 0.0
    n_calls = 0
    for task in tasks:
        for mid in eligible_fn(registry, task):
            c = estimate_task_cost(models[mid], task)
            per_model[mid] += c
            total += c
            n_calls += 1
    worst = total * (1 + worst_case_retries)
    return {"estimated_total_usd": round(total, 4), "worst_case_usd": round(worst, 4),
            "n_calls": n_calls, "per_model_usd": {k: round(v, 4) for k, v in per_model.items()},
            "worst_case_retries": worst_case_retries}
