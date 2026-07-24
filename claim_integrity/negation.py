"""Negation preservation (Phase 14). Full/partial/nested/double negation. The critical failures are
polarity inversion (drop 'not') and negation-scope error. Deterministic.
"""
from __future__ import annotations

import re
from typing import Dict

_NEG = re.compile(r"\b(not|no|never|cannot|does not|doesn't|didn't|won't|isn't|aren't)\b", re.I)
_DOUBLE = re.compile(r"\bnot\b[^.]*\b(un\w+|in\w+|no)\b", re.I)


def polarity(text: str) -> str:
    negs = len(_NEG.findall(text))
    if negs == 0:
        return "affirmative"
    if negs % 2 == 0 or _DOUBLE.search(text):
        return "double_or_partial"
    return "negated"


def preserved(gold_text: str, produced_text: str) -> bool:
    """Preserved iff both carry the same negation state. Losing/inverting negation is never OK."""
    g = polarity(gold_text)
    p = polarity(produced_text)
    # collapse double/partial to 'has-negation' for the safety comparison
    gh = g != "affirmative"
    ph = p != "affirmative"
    return gh == ph
