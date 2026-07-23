"""Routing arms A, B, C, D, E and the policy arms F1, F2, G.

Baselines A-E are regime-invariant references. B/D/E consult a fixed benchmark
snapshot (the full dev evaluation). Policy arms are produced by policy.route and
swept across regimes in the harness.
"""
from __future__ import annotations

from typing import Any, Dict, List

from model_selection_pilot import policy as pol

FIXED_DEFAULT = "medium_general"
STATIC_RULES = {
    "structured_extraction": "medium_general",
    "schema_constrained_generation": "medium_general",
    "classification": "fast_small",
    "summarization": "long_context",
    "long_document_qa": "long_context",
    "grounded_comparison": "strong_reason",
    "clause_identification": "strong_reason",
}


def _tech_eligible(registry, task) -> List[str]:
    view = pol.routing_view(task)
    ent = registry["enterprise_policy"]
    return [mid for mid, m in registry["models"].items()
            if pol.hard_and_technical_filter(mid, m, view, ent)[0]]


def _bench_quality(benchmark, mid, tc):
    cell = benchmark.get(mid, {}).get(tc)
    return cell["quality_mean"] if (cell and cell["quality_mean"] is not None) else None


def _bench_overall(benchmark, mid):
    vals = [c["quality_mean"] for tc, c in benchmark.get(mid, {}).items()
            if isinstance(c, dict) and c.get("quality_mean") is not None]
    return sum(vals) / len(vals) if vals else None


def _rec(arm, task, selected, fallback=None, abstained=False, reason=None):
    return {"arm": arm, "task_id": task["task_id"], "selected": selected,
            "fallback_chain": fallback or [], "abstained": abstained, "abstain_reason": reason}


def arm_A(registry, task, benchmark):
    return _rec("A", task, FIXED_DEFAULT)  # no eligibility check (naive)


def arm_B(registry, task, benchmark):
    elig = _tech_eligible(registry, task)
    if not elig:
        return _rec("B", task, None, abstained=True, reason="no eligible model")
    ranked = sorted(elig, key=lambda m: (-(_bench_overall(benchmark, m) or 0.0),
                                         pol.estimate_cost(registry["models"][m], pol.routing_view(task))))
    return _rec("B", task, ranked[0], ranked[1:])


def arm_C(registry, task, benchmark):
    elig = _tech_eligible(registry, task)
    if not elig:
        return _rec("C", task, None, abstained=True, reason="no eligible model")
    view = pol.routing_view(task)
    ranked = sorted(elig, key=lambda m: (pol.estimate_cost(registry["models"][m], view), m))
    return _rec("C", task, ranked[0], ranked[1:])


def arm_D(registry, task, benchmark):
    elig = _tech_eligible(registry, task)
    if not elig:
        return _rec("D", task, None, abstained=True, reason="no eligible model")
    pref = STATIC_RULES.get(task["task_class"], FIXED_DEFAULT)
    sel = pref if pref in elig else (FIXED_DEFAULT if FIXED_DEFAULT in elig else sorted(elig)[0])
    return _rec("D", task, sel, [m for m in elig if m != sel])


def arm_E(registry, task, benchmark):
    elig = _tech_eligible(registry, task)
    if not elig:
        return _rec("E", task, None, abstained=True, reason="no eligible model")
    tc = task["task_class"]
    ranked = sorted(elig, key=lambda m: (-(_bench_quality(benchmark, m, tc) or 0.0), m))
    return _rec("E", task, ranked[0], ranked[1:])


BASELINES = {"A": arm_A, "B": arm_B, "C": arm_C, "D": arm_D, "E": arm_E}
