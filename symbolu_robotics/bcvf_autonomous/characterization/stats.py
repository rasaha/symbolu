"""Statistical helpers for the characterization sweep.

The sweep's per-(family, magnitude) cells are evaluated at multiple
seeds and rolled up into a per-config pass tally. Tying the
regression suite to a *stated* statistical bound — "with 95%
confidence the true pass rate at this config is at least 0.90" —
requires a confidence-interval primitive that:

* Has known small-sample behaviour (Wilson score interval is the
  standard textbook choice; closed-form, no scipy dependency,
  honest at the boundary cases the sweep actually hits, e.g.
  60-of-60 pass).
* Returns both bounds so a caller can also display the upper bound
  in summary tables.

The certification floor and Wilson-z constant live here so a
caller can override either without editing the sweep itself.
"""

from __future__ import annotations

import math
from typing import Tuple


# Wilson z-score for a 95% two-sided confidence interval.
WILSON_Z_95: float = 1.959963984540054

# Certification floor for the per-config pass-rate Wilson CI lower
# bound. Calibrated so that 60-of-60 pass produces a lower bound of
# ~0.940 (clear of the floor); a single statistical failure
# (59/60) produces ~0.911 (still clear); two failures (58/60)
# produces ~0.886 (under the floor) — i.e. the floor binds at
# exactly the regime the audit flagged ("kernel flips pass→fail
# with a small kernel change") rather than tolerating arbitrary
# regressions.
CERTIFICATION_FLOOR: float = 0.90


def wilson_ci(
    successes: int,
    total: int,
    z: float = WILSON_Z_95,
) -> Tuple[float, float]:
    """Two-sided Wilson score confidence interval for a binomial proportion.

    Args:
        successes: number of successful trials (0 <= successes <= total).
        total: total trial count.
        z: Wilson z-score; default ``WILSON_Z_95`` for a 95%
            two-sided interval. ``z = 2.5758`` gives the 99% interval.

    Returns:
        ``(low, high)`` clamped to ``[0, 1]``. Returns ``(0.0, 1.0)``
        if ``total == 0``: with no observations the entire interval
        is feasible.

    Raises:
        ValueError: if ``total`` is negative (nonsensical) or if
            ``successes`` falls outside ``[0, total]``.
    """
    if total < 0:
        raise ValueError(f"total must be >= 0; got {total}")
    if total == 0:
        return 0.0, 1.0
    if successes < 0 or successes > total:
        raise ValueError(
            f"successes must lie in [0, {total}]; got {successes}"
        )
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


def wilson_lower_bound(
    successes: int,
    total: int,
    z: float = WILSON_Z_95,
) -> float:
    """Convenience wrapper returning only the lower bound of :func:`wilson_ci`."""
    low, _ = wilson_ci(successes, total, z=z)
    return low
