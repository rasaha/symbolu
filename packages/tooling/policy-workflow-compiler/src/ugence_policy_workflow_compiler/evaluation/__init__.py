"""Deterministic evaluation of declarative policy predicates.

One interpreter for the policy language, used by every consumer that needs to know
whether a predicate holds — the reference-equivalence harnesses today, and the
offline simulator (PWC-P3C) next.
"""

from __future__ import annotations

from .predicates import (
    UnsupportedComparator,
    evaluate_all,
    evaluate_any,
    evaluate_predicate,
)

__all__ = [
    "evaluate_predicate",
    "evaluate_all",
    "evaluate_any",
    "UnsupportedComparator",
]
