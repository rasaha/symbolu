"""Sign-test + Wilson-CI primitives for the §6.2 paired comparison.

Pure NumPy + stdlib — no scipy dependency. The pilot's headline
result is a one-sided sign test on per-scene deltas
``delta_i = err_A0_i - err_A3_i`` (positive ⇒ A3 wins on scene i).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass
class PairedComparisonResult:
    """Output of :func:`one_sided_sign_test`."""

    n_paired: int
    n_a3_wins: int
    n_a0_wins: int
    n_ties: int
    win_rate: float
    win_rate_ci_low: float
    win_rate_ci_high: float
    p_value_one_sided: float
    significant_at_alpha: float


def _wilson_ci(
    successes: int, total: int, z: float = 1.96,
) -> tuple:
    """Wilson score interval for a binomial proportion.

    ``z = 1.96`` corresponds to a 95% two-sided confidence interval.
    Returns (low, high). Returns (0.0, 1.0) when total == 0.
    """
    if total <= 0:
        return 0.0, 1.0
    p = successes / total
    denom = 1.0 + (z * z) / total
    centre = (p + (z * z) / (2.0 * total)) / denom
    half = (
        z
        * math.sqrt(
            (p * (1.0 - p) / total) + (z * z) / (4.0 * total * total)
        )
    ) / denom
    return max(0.0, centre - half), min(1.0, centre + half)


def _binomial_tail_geq(k: int, n: int, p: float = 0.5) -> float:
    """P(X >= k) for X ~ Binomial(n, p). Stable for small n."""
    if n <= 0:
        return 1.0 if k <= 0 else 0.0
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    # Iterative computation of P(X = i) recurrence:
    #   P(X = i+1) = P(X = i) * (n - i) / (i + 1) * p / (1 - p)
    log_p = math.log(p)
    log_q = math.log(1.0 - p) if p < 1.0 else float("-inf")
    log_pmf = n * log_q
    cdf = math.exp(log_pmf)   # P(X = 0)
    if k == 0:
        return 1.0
    for i in range(1, n + 1):
        log_pmf = log_pmf + math.log((n - i + 1) / i) + log_p - log_q
        cdf += math.exp(log_pmf)
        if i == k - 1:
            break
    cdf = min(1.0, max(0.0, cdf))
    return max(0.0, 1.0 - cdf)


def one_sided_sign_test(
    deltas: Sequence[float],
    alpha: float = 0.05,
    tie_eps: float = 0.0,
) -> PairedComparisonResult:
    """One-sided sign test: H0: median(delta) <= 0; H1: median(delta) > 0.

    A scene's delta is the per-scene metric improvement A3 vs A0
    (positive ⇒ A3 wins). Ties (``|delta| <= tie_eps``) are excluded
    from the test, following the standard sign-test convention.

    Returns a :class:`PairedComparisonResult` with win rate, Wilson CI,
    one-sided p-value, and a significance flag at ``alpha``.
    """
    a3_wins = 0
    a0_wins = 0
    ties = 0
    for d in deltas:
        if abs(d) <= tie_eps:
            ties += 1
        elif d > 0:
            a3_wins += 1
        else:
            a0_wins += 1
    n_decisive = a3_wins + a0_wins
    if n_decisive == 0:
        return PairedComparisonResult(
            n_paired=len(deltas),
            n_a3_wins=0,
            n_a0_wins=0,
            n_ties=ties,
            win_rate=0.5,
            win_rate_ci_low=0.0,
            win_rate_ci_high=1.0,
            p_value_one_sided=1.0,
            significant_at_alpha=alpha,
        )
    win_rate = a3_wins / n_decisive
    ci_low, ci_high = _wilson_ci(a3_wins, n_decisive)
    p = _binomial_tail_geq(a3_wins, n_decisive, 0.5)
    return PairedComparisonResult(
        n_paired=len(deltas),
        n_a3_wins=a3_wins,
        n_a0_wins=a0_wins,
        n_ties=ties,
        win_rate=win_rate,
        win_rate_ci_low=ci_low,
        win_rate_ci_high=ci_high,
        p_value_one_sided=p,
        significant_at_alpha=alpha,
    )
