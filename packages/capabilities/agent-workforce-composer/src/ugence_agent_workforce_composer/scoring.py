"""Deterministic fixed-point scoring primitives.

All P2 scores are **integer basis points** (0..10000, where 10000 = 1.0000). The
only place a raw metric (a Python float from an ``AgentProfile``) is converted to
basis points is :func:`normalize_higher_better` / :func:`normalize_lower_better`,
which use :class:`decimal.Decimal` with a **fixed local context** and
``ROUND_FLOOR`` — exact and identical across processes and platforms, and
monotonic (a larger input never yields a smaller floored result). All subsequent
arithmetic (weighting, summation) is pure Python ``int`` math, so a total score is
exactly reconstructable from its integer components. No binary float ever enters a
stored score or a fingerprint.

Representation recorded for audit: integer basis points; precision 1 bp (1e-4);
rounding ROUND_FLOOR on normalization; weighting by integer floor division.
"""
from __future__ import annotations

from decimal import ROUND_FLOOR, Context, Decimal
from typing import Optional

#: 1.0000 in basis points.
BP_SCALE = 10000

#: Fixed decimal context for normalization — never reads the global context, so it
#: is deterministic regardless of ambient ``decimal.getcontext()`` state.
_CTX = Context(prec=40, rounding=ROUND_FLOOR)

SCORE_REPRESENTATION = "integer_basis_points"
SCORE_PRECISION = "1_basis_point"
SCORE_ROUNDING = "ROUND_FLOOR"


def _dec(value) -> Decimal:
    # Decimal(str(x)) makes float→Decimal deterministic (no binary artefacts).
    return Decimal(str(value))


def clamp_bp(value: int) -> int:
    if value < 0:
        return 0
    if value > BP_SCALE:
        return BP_SCALE
    return int(value)


def normalize_higher_better(value: Optional[float], lo: float, hi: float) -> int:
    """Map ``value`` in [lo, hi] to basis points; higher raw value → higher bp.

    ``None`` → 0 (missing metric contributes nothing). Degenerate ``hi <= lo`` → 0.
    """
    if value is None:
        return 0
    v, dlo, dhi = _dec(value), _dec(lo), _dec(hi)
    if dhi <= dlo:
        return 0
    if v <= dlo:
        return 0
    if v >= dhi:
        return BP_SCALE
    frac = _CTX.divide((v - dlo) * BP_SCALE, (dhi - dlo))
    return clamp_bp(int(frac.to_integral_value(rounding=ROUND_FLOOR)))


def normalize_lower_better(value: Optional[float], lo: float, hi: float) -> int:
    """Map ``value`` in [lo, hi] to basis points; lower raw value → higher bp.

    ``None`` → 0. Degenerate ``hi <= lo`` → 0.
    """
    if value is None:
        return 0
    v, dlo, dhi = _dec(value), _dec(lo), _dec(hi)
    if dhi <= dlo:
        return 0
    if v <= dlo:
        return BP_SCALE
    if v >= dhi:
        return 0
    frac = _CTX.divide((dhi - v) * BP_SCALE, (dhi - dlo))
    return clamp_bp(int(frac.to_integral_value(rounding=ROUND_FLOOR)))


def weighted_contribution(normalized_bp: int, weight_bp: int) -> int:
    """Weighted contribution = normalized * weight / 10000, floored (integer)."""
    return (clamp_bp(normalized_bp) * int(weight_bp)) // BP_SCALE


__all__ = [
    "BP_SCALE",
    "SCORE_REPRESENTATION",
    "SCORE_PRECISION",
    "SCORE_ROUNDING",
    "clamp_bp",
    "normalize_higher_better",
    "normalize_lower_better",
    "weighted_contribution",
]
