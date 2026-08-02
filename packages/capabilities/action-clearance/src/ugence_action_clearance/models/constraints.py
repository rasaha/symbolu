"""Effective constraints, obligations, and the narrowing (intersection) algebra.

Monotonicity (design §7, §20): clearance may only **narrow**. The intersection of
an authorization constraint and a clearance constraint on the same dimension can
only produce an equal-or-narrower constraint. If a clearance constraint would
broaden, the pair conflicts; if a constraint kind cannot be interpreted, the
evaluator fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Tuple


class ConstraintKind(str, Enum):
    """Neutral, interpretable constraint kinds."""

    MAX = "MAX"                  # numeric upper bound; narrower = smaller
    MIN = "MIN"                  # numeric lower bound; narrower = larger
    ALLOWED_SET = "ALLOWED_SET"  # membership; narrower = subset (intersection)
    TIME_WINDOW_END = "TIME_WINDOW_END"  # window end; narrower = earlier
    REQUIRED = "REQUIRED"        # a required control/obligation flag; narrower = superset


@dataclass(frozen=True)
class EffectiveConstraint:
    """A single neutral constraint on one dimension."""

    dimension: str
    kind: ConstraintKind
    value: Any

    def canonical(self) -> str:
        return f"{self.dimension}:{self.kind.value}={self.value}"


class ConstraintOutcome(str, Enum):
    OK = "OK"
    CONFLICT = "CONFLICT"          # would relax / cannot both hold
    UNSUPPORTED = "UNSUPPORTED"    # no deterministic interpretation rule


@dataclass(frozen=True)
class IntersectionResult:
    outcome: ConstraintOutcome
    constraint: Optional[EffectiveConstraint] = None


def intersect(auth: EffectiveConstraint, clearance: EffectiveConstraint) -> IntersectionResult:
    """Intersect two same-dimension constraints; never broaden.

    Returns the narrowed constraint, or CONFLICT if the clearance constraint would
    broaden/contradict, or UNSUPPORTED if the kinds cannot be combined.
    """
    if auth.dimension != clearance.dimension:
        return IntersectionResult(ConstraintOutcome.UNSUPPORTED)
    if auth.kind is not clearance.kind:
        return IntersectionResult(ConstraintOutcome.UNSUPPORTED)
    k = auth.kind
    a, c = auth.value, clearance.value
    try:
        if k is ConstraintKind.MAX:
            # narrower = smaller; clearance may only lower the ceiling
            if c > a:
                return IntersectionResult(ConstraintOutcome.CONFLICT)
            return IntersectionResult(ConstraintOutcome.OK,
                                      EffectiveConstraint(auth.dimension, k, min(a, c)))
        if k is ConstraintKind.MIN:
            if c < a:
                return IntersectionResult(ConstraintOutcome.CONFLICT)
            return IntersectionResult(ConstraintOutcome.OK,
                                      EffectiveConstraint(auth.dimension, k, max(a, c)))
        if k is ConstraintKind.TIME_WINDOW_END:
            if c > a:
                return IntersectionResult(ConstraintOutcome.CONFLICT)
            return IntersectionResult(ConstraintOutcome.OK,
                                      EffectiveConstraint(auth.dimension, k, min(a, c)))
        if k is ConstraintKind.ALLOWED_SET:
            aset, cset = set(a), set(c)
            if not cset.issubset(aset):
                # clearance introduces members not authorized -> would broaden
                return IntersectionResult(ConstraintOutcome.CONFLICT)
            inter = aset & cset
            if not inter:
                return IntersectionResult(ConstraintOutcome.CONFLICT)
            return IntersectionResult(ConstraintOutcome.OK,
                                      EffectiveConstraint(auth.dimension, k, tuple(sorted(inter))))
        if k is ConstraintKind.REQUIRED:
            union = tuple(sorted(set(a) | set(c)))
            return IntersectionResult(ConstraintOutcome.OK,
                                      EffectiveConstraint(auth.dimension, k, union))
    except TypeError:
        return IntersectionResult(ConstraintOutcome.UNSUPPORTED)
    return IntersectionResult(ConstraintOutcome.UNSUPPORTED)


@dataclass(frozen=True)
class ClearanceObligation:
    """A neutral obligation that must be honored downstream."""

    obligation: str

    def canonical(self) -> str:
        return self.obligation


__all__ = [
    "ConstraintKind",
    "EffectiveConstraint",
    "ConstraintOutcome",
    "IntersectionResult",
    "intersect",
    "ClearanceObligation",
]
