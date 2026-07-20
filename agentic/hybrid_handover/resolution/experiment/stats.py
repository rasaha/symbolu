#!/usr/bin/env python3
"""
Deterministic paired statistics for the Exploratory Resolver Study v0.1.

  * exact McNemar (paired binary correctness) — exact binomial two-sided p
  * paired bootstrap 95% CI for a paired macro/metric difference — FIXED resample
    seed (recorded in the manifest); byte-identical across repetitions
  * Holm step-down multiple-comparison correction over secondary endpoints

No stochastic dependence on wall-clock or process state: the bootstrap uses a
`random.Random(seed)` with a preregistered constant seed, so two runs are
byte-identical. Significance is reported; it is never conflated with practical
significance.
"""

from __future__ import annotations

import math
import random
from itertools import combinations

BOOTSTRAP_SEED = 20240601      # preregistered constant (recorded in the manifest)
BOOTSTRAP_ITERS = 10000
CI_ALPHA = 0.05


# --------------------------------------------------------------------------- #
# exact McNemar
# --------------------------------------------------------------------------- #
def _binom_pmf(k, n, p=0.5):
    return math.comb(n, k) * (p ** k) * ((1 - p) ** (n - k))


def mcnemar_exact(a_correct: list[bool], b_correct: list[bool]) -> dict:
    """
    Exact McNemar on paired binary correctness vectors (a = candidate, b = base).
    b01 = a wrong, b right; b10 = a right, b wrong. Two-sided exact binomial
    p-value on the discordant pairs (n = b01 + b10, p = 0.5).
    """
    assert len(a_correct) == len(b_correct)
    b10 = sum(1 for a, b in zip(a_correct, b_correct) if a and not b)   # a fixes
    b01 = sum(1 for a, b in zip(a_correct, b_correct) if b and not a)   # a breaks
    n = b10 + b01
    if n == 0:
        p = 1.0
    else:
        k = min(b10, b01)
        # two-sided exact: sum of probabilities of outcomes at least as extreme
        tail = sum(_binom_pmf(i, n) for i in range(0, k + 1))
        p = min(1.0, 2 * tail)
    return {"b10_candidate_fixes": b10, "b01_candidate_breaks": b01,
            "n_discordant": n, "p_value": round(p, 6),
            "net": b10 - b01}


# --------------------------------------------------------------------------- #
# paired bootstrap CI for a difference of means of paired per-case scores
# --------------------------------------------------------------------------- #
def paired_bootstrap_diff(a_scores: list[float], b_scores: list[float],
                          iters: int = BOOTSTRAP_ITERS,
                          seed: int = BOOTSTRAP_SEED) -> dict:
    """
    95% percentile bootstrap CI for mean(a) - mean(b) over paired per-case scores.
    Resamples case indices with replacement (paired). Deterministic given seed.
    """
    assert len(a_scores) == len(b_scores)
    n = len(a_scores)
    obs = (sum(a_scores) - sum(b_scores)) / n if n else 0.0
    if n == 0:
        return {"observed_diff": 0.0, "ci95": [0.0, 0.0], "n": 0, "iters": iters}
    rng = random.Random(seed)
    diffs = []
    idx = range(n)
    for _ in range(iters):
        s = [rng.randrange(n) for _ in idx]
        da = sum(a_scores[i] for i in s) / n
        db = sum(b_scores[i] for i in s) / n
        diffs.append(da - db)
    diffs.sort()
    lo = diffs[int((CI_ALPHA / 2) * iters)]
    hi = diffs[int((1 - CI_ALPHA / 2) * iters) - 1]
    return {"observed_diff": round(obs, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "n": n, "iters": iters, "seed": seed,
            "excludes_zero": bool(lo > 0 or hi < 0)}


def cohens_h(p1: float, p2: float) -> float:
    """Effect size for two proportions (paired-agnostic magnitude)."""
    def phi(p):
        p = min(max(p, 0.0), 1.0)
        return 2 * math.asin(math.sqrt(p))
    return round(phi(p1) - phi(p2), 4)


# --------------------------------------------------------------------------- #
# Holm step-down correction
# --------------------------------------------------------------------------- #
def holm(pvalues: dict[str, float], alpha: float = 0.05) -> dict:
    """
    Holm-Bonferroni step-down over a family of secondary-endpoint p-values.
    Returns per-key adjusted threshold, adjusted p, and reject flag.
    """
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    out = {}
    prev_adj = 0.0
    running_reject = True
    for rank, (k, p) in enumerate(items):
        thresh = alpha / (m - rank)
        adj = min(1.0, max(prev_adj, p * (m - rank)))
        prev_adj = adj
        if not (p <= thresh) or not running_reject:
            running_reject = False
        out[k] = {"raw_p": round(p, 6), "holm_threshold": round(thresh, 6),
                  "holm_adjusted_p": round(adj, 6), "reject_null": running_reject}
    return out


# --------------------------------------------------------------------------- #
# convenience: pairwise McNemar across a set of resolvers on one binary metric
# --------------------------------------------------------------------------- #
def pairwise_mcnemar(binary_by_resolver: dict[str, list[bool]]) -> dict:
    out = {}
    for a, b in combinations(binary_by_resolver, 2):
        out[f"{a}__vs__{b}"] = mcnemar_exact(binary_by_resolver[a], binary_by_resolver[b])
    return out
