"""Stratified metrics + bootstrap confidence intervals for the naturalistic study.

Adds, on top of metrics.aggregate: stratification by partition/domain/action-type/
split, redundancy-only critical fraction, held-out extractor instability, a
context-length distribution, and percentile-bootstrap CIs. Deterministic
(fixed-seed resampling).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from . import metrics
from .corpus.schema import HELDOUT


def _median(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return 0.0
    m = n // 2
    return xs[m] if n % 2 else (xs[m - 1] + xs[m]) / 2.0


def _percentile(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0.0
    k = (len(xs) - 1) * p
    lo = int(k)
    hi = min(lo + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def stratify(items, runs, keyfn) -> dict:
    groups: dict = {}
    for it, run in zip(items, runs):
        groups.setdefault(keyfn(it), []).append(run)
    return {k: metrics.aggregate(v) for k, v in sorted(groups.items())}


def redundancy_only_fraction(runs) -> float:
    tot = sum(r.ctx.total_tokens for r in runs) or 1
    red = 0
    for r in runs:
        single = r.decision_units | r.envelope_units | r.assurance_units | r.structure_units
        for uid in (r.redundant_units - single):
            red += r.ctx.unit(uid).token_count
    return red / tot


def heldout_instability(items, runs) -> float:
    ho = [run for it, run in zip(items, runs) if it.split == HELDOUT]
    if not ho:
        return 0.0
    return metrics.aggregate(ho).extractor_instability_rate


def length_distribution(runs) -> dict:
    lens = [r.ctx.total_tokens for r in runs]
    return {"n": len(lens), "min": min(lens), "p25": _percentile(lens, 0.25),
            "median": _median(lens), "p75": _percentile(lens, 0.75), "max": max(lens),
            "mean": sum(lens) / len(lens) if lens else 0.0}


def bootstrap_ci(runs, field_name, *, iters=500, seed=0, alpha=0.05) -> tuple:
    rng = random.Random(seed)
    n = len(runs)
    if n == 0:
        return (0.0, 0.0)
    vals = []
    for _ in range(iters):
        sample = [runs[rng.randrange(n)] for _ in range(n)]
        vals.append(getattr(metrics.aggregate(sample), field_name))
    return (_percentile(vals, alpha / 2), _percentile(vals, 1 - alpha / 2))


@dataclass
class NaturalisticReport:
    agg: object
    by_partition: dict
    by_domain: dict
    by_action: dict
    by_split: dict
    redundancy_only_fraction: float
    heldout_instability: float
    length_dist: dict
    ci: dict                      # field -> (lo, hi)
    per_context: list = field(default_factory=list)


def compute(items, runs) -> NaturalisticReport:
    agg = metrics.aggregate(runs)
    ci_fields = ["f_critical_union", "oracle_ceiling", "deployable_ceiling",
                 "recall_p0", "precision_p0"]
    return NaturalisticReport(
        agg=agg,
        by_partition=stratify(items, runs, lambda it: it.partition),
        by_domain=stratify(items, runs, lambda it: it.domain),
        by_action=stratify(items, runs, lambda it: it.action_type),
        by_split=stratify(items, runs, lambda it: it.split),
        redundancy_only_fraction=redundancy_only_fraction(runs),
        heldout_instability=heldout_instability(items, runs),
        length_dist=length_distribution(runs),
        ci={f: bootstrap_ci(runs, f) for f in ci_fields},
        per_context=agg.per_context)
