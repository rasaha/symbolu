"""Paired strategy comparisons (Task 14).

Every strategy runs the same scenarios, so comparisons are paired per scenario.
Reports counts and per-scenario differences (no overstated statistics from 90
synthetic scenarios). A fixed-seed bootstrap CI is offered for the headline
unsafe-outcome difference only.
"""
from __future__ import annotations

from ..schemas.safety import UNSAFE_OUTCOMES

_PAIRS = (
    ("full_governance", "no_governance"),
    ("full_governance", "action_only"),
    ("full_governance", "assertion_only"),
    ("action_only", "no_governance"),
    ("assertion_only", "no_governance"),
)


def _unsafe_map(judgements_by_strategy: dict) -> dict:
    out = {}
    for sid, judgements in judgements_by_strategy.items():
        out[sid] = {j.scenario_id: (j.safety_outcome in UNSAFE_OUTCOMES) for j in judgements}
    return out


def _bootstrap_ci(diffs: list, seed: int, iters: int = 1000):
    """Deterministic paired bootstrap CI for the mean difference (fixed seed)."""
    n = len(diffs)
    if n == 0:
        return None
    state = seed & 0xFFFFFFFF
    means = []
    for _ in range(iters):
        total = 0
        for _i in range(n):
            state = (1103515245 * state + 12345) & 0x7FFFFFFF   # deterministic LCG
            total += diffs[state % n]
        means.append(total / n)
    means.sort()
    lo = means[int(0.025 * iters)]
    hi = means[int(0.975 * iters)]
    return {"mean": round(sum(diffs) / n, 4), "ci95_low": round(lo, 4),
            "ci95_high": round(hi, 4), "iters": iters, "seed": seed}


def paired_analysis(judgements_by_strategy: dict, *, seed: int = 12345) -> dict:
    unsafe = _unsafe_map(judgements_by_strategy)
    out = {}
    for a, b in _PAIRS:
        ids = sorted(unsafe[a])
        # difference in "is unsafe" per scenario (b_unsafe - a_unsafe): positive means
        # a prevented an unsafe outcome that b allowed
        diffs = [int(unsafe[b][sid]) - int(unsafe[a][sid]) for sid in ids]
        a_unsafe = sum(unsafe[a][sid] for sid in ids)
        b_unsafe = sum(unsafe[b][sid] for sid in ids)
        prevented = sum(1 for d in diffs if d > 0)
        regressed = sum(1 for d in diffs if d < 0)
        out[f"{a}_vs_{b}"] = {
            "scenarios": len(ids),
            f"{a}_unsafe": a_unsafe, f"{b}_unsafe": b_unsafe,
            "unsafe_prevented_by_first": prevented,
            "unsafe_introduced_by_first": regressed,
            "net_unsafe_reduction": b_unsafe - a_unsafe,
            "bootstrap_ci_mean_unsafe_reduction": _bootstrap_ci(diffs, seed),
        }
    return out
