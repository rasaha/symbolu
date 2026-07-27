"""annealing.py — supervision-annealing schedules (§ Supervision-annealing schedules)."""
from __future__ import annotations
import math


def anneal_coeff(schedule: str, frac: float) -> float:
    """Supervision coefficient in [0,1] as a function of training progress frac ∈ [0,1].
    Reaches 0 at frac=1 for every schedule; training continues past that (post-anneal)."""
    frac = min(max(frac, 0.0), 1.0)
    if schedule == "linear":
        return 1.0 - frac
    if schedule == "cosine":
        return 0.5 * (1.0 + math.cos(math.pi * frac))
    if schedule == "staged":
        # 100% → 50% → 10% → 0%
        if frac < 0.25:
            return 1.0
        if frac < 0.5:
            return 0.5
        if frac < 0.75:
            return 0.1
        return 0.0
    raise ValueError(schedule)
