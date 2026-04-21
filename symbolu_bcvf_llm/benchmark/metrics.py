"""§6.5 metrics — accuracy, paired McNemar, latency, §1.10 evaluation.

All pure-NumPy / stdlib; no SciPy dependency. The McNemar test uses
the exact binomial form, which is what autonomy used (N=26 paired)
so the discipline transfers.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np


def accuracy(correct: np.ndarray) -> float:
    """Fraction correct across questions."""
    c = np.asarray(correct, dtype=bool)
    if c.size == 0:
        return 0.0
    return float(c.mean())


@dataclass
class McNemarResult:
    """Paired McNemar test — exact binomial form."""

    n: int                # total paired comparisons
    b: int                # count where A correct and B incorrect
    c: int                # count where A incorrect and B correct
    statistic: float      # (b - c)**2 / (b + c); 0 if b+c=0
    p_value_exact: float  # exact two-sided binomial


def mcnemar_paired(
    a_correct: np.ndarray, b_correct: np.ndarray
) -> McNemarResult:
    """Compute the paired McNemar test between two decoders.

    `a_correct` and `b_correct` are boolean arrays of equal length
    indicating per-question correctness. Returns `McNemarResult`
    with discordant-pair counts, the chi-square-style statistic,
    and an exact two-sided binomial p-value.
    """
    a = np.asarray(a_correct, dtype=bool)
    b = np.asarray(b_correct, dtype=bool)
    if a.shape != b.shape:
        raise ValueError(
            f"a_correct {a.shape} must match b_correct {b.shape}"
        )
    b_count = int(np.sum(a & ~b))   # A correct, B wrong
    c_count = int(np.sum(~a & b))   # A wrong, B correct
    n = b_count + c_count
    if n == 0:
        return McNemarResult(
            n=int(a.size), b=0, c=0, statistic=0.0, p_value_exact=1.0
        )
    statistic = float((b_count - c_count) ** 2) / float(n)
    # Exact two-sided binomial: P(X ≤ min(b, c)) × 2, capped at 1.
    k = min(b_count, c_count)
    # Sum P(X = i) for i = 0..k under Binom(n, 0.5).
    total = 0.0
    for i in range(k + 1):
        total += math.comb(n, i) * (0.5 ** n)
    p_value = min(1.0, 2.0 * total)
    return McNemarResult(
        n=int(a.size),
        b=b_count,
        c=c_count,
        statistic=statistic,
        p_value_exact=p_value,
    )


@dataclass
class LatencyStats:
    mean_s: float
    median_s: float
    p95_s: float
    min_s: float
    max_s: float
    n: int


def latency_stats(latencies_s: np.ndarray) -> LatencyStats:
    x = np.asarray(latencies_s, dtype=np.float64)
    if x.size == 0:
        return LatencyStats(
            mean_s=0.0, median_s=0.0, p95_s=0.0, min_s=0.0, max_s=0.0, n=0
        )
    return LatencyStats(
        mean_s=float(np.mean(x)),
        median_s=float(np.median(x)),
        p95_s=float(np.percentile(x, 95)),
        min_s=float(np.min(x)),
        max_s=float(np.max(x)),
        n=int(x.size),
    )


# --------------------------------------------------------------------------- #
# §1.10 pre-committed threshold evaluation
# --------------------------------------------------------------------------- #


@dataclass
class PhaseSixVerdict:
    """§1.10 classification of the three-decoder comparison.

    Fields:
        classification: one of PASS | NULL | REGRESSION | UNVIABLE_COST
        accuracy_trust: BCVF-trust accuracy
        accuracy_blend: conventional-blend accuracy
        delta_pp: (trust - blend) in percentage points
        latency_ratio: mean-latency trust / mean-latency blend
        mcnemar: McNemarResult for the paired trust-vs-blend test
        notes: human-readable classification rationale
    """

    classification: str
    accuracy_trust: float
    accuracy_blend: float
    delta_pp: float
    latency_ratio: float
    mcnemar: McNemarResult
    notes: str


def classify_phase_six_result(
    trust_correct: np.ndarray,
    blend_correct: np.ndarray,
    trust_latencies: np.ndarray,
    blend_latencies: np.ndarray,
) -> PhaseSixVerdict:
    """Apply §1.10's pre-committed thresholds to a single-seed run.

    §1.10 thresholds:
      PASS            : trust ≥ blend + 2 pp  AND  latency ≤ 2× blend
      NULL            : |trust − blend| < 0.5 pp
      REGRESSION      : trust ≤ blend − 1 pp
      UNVIABLE_COST   : latency > 5× blend  (regardless of accuracy)
      AMBIGUOUS       : none of the above (between -1 pp and +2 pp)

    The two-seed replication check is a separate step (§6.6) and is
    not evaluated here — this function classifies a single seed.
    """
    acc_t = accuracy(trust_correct)
    acc_b = accuracy(blend_correct)
    delta_pp = (acc_t - acc_b) * 100.0
    mcn = mcnemar_paired(trust_correct, blend_correct)

    lat_t = latency_stats(trust_latencies)
    lat_b = latency_stats(blend_latencies)
    ratio = (
        lat_t.mean_s / lat_b.mean_s
        if lat_b.mean_s > 0 else float("inf")
    )

    # Cost check takes precedence — unviable is a hard stop.
    if ratio > 5.0:
        return PhaseSixVerdict(
            classification="UNVIABLE_COST",
            accuracy_trust=acc_t, accuracy_blend=acc_b,
            delta_pp=delta_pp, latency_ratio=ratio, mcnemar=mcn,
            notes=(
                f"Latency {ratio:.1f}× conventional-blend exceeds §1.10's "
                "5× unviable-cost ceiling regardless of accuracy delta."
            ),
        )
    if delta_pp <= -1.0:
        return PhaseSixVerdict(
            classification="REGRESSION",
            accuracy_trust=acc_t, accuracy_blend=acc_b,
            delta_pp=delta_pp, latency_ratio=ratio, mcnemar=mcn,
            notes=(
                f"trust − blend = {delta_pp:+.2f} pp ≤ −1 pp. "
                "§1.10 regression. Post-mortem required."
            ),
        )
    if abs(delta_pp) < 0.5:
        return PhaseSixVerdict(
            classification="NULL",
            accuracy_trust=acc_t, accuracy_blend=acc_b,
            delta_pp=delta_pp, latency_ratio=ratio, mcnemar=mcn,
            notes=(
                f"|trust − blend| = {abs(delta_pp):.2f} pp < 0.5 pp. "
                "§1.10 null — structural claim does not transfer."
            ),
        )
    if delta_pp >= 2.0 and ratio <= 2.0:
        return PhaseSixVerdict(
            classification="PASS",
            accuracy_trust=acc_t, accuracy_blend=acc_b,
            delta_pp=delta_pp, latency_ratio=ratio, mcnemar=mcn,
            notes=(
                f"trust − blend = {delta_pp:+.2f} pp ≥ 2 pp AND latency "
                f"{ratio:.2f}× blend ≤ 2×. §1.10 success (single seed — "
                "§6.6 replication still required for final sign-off)."
            ),
        )
    return PhaseSixVerdict(
        classification="AMBIGUOUS",
        accuracy_trust=acc_t, accuracy_blend=acc_b,
        delta_pp=delta_pp, latency_ratio=ratio, mcnemar=mcn,
        notes=(
            f"delta {delta_pp:+.2f} pp, latency ratio {ratio:.2f}× — "
            "between §1.10 thresholds; requires larger N or second-seed "
            "replication for classification."
        ),
    )
