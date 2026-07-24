"""Uncertainty preservation (Phase 14). Distinguishes an UNCERTAIN claim from a claim ABOUT
uncertainty, attributed uncertainty, lack of evidence, and evidence of absence. Deterministic.
"""
from __future__ import annotations

import re
from typing import Dict

_HEDGE = re.compile(r"\b(may|might|likely|possibly|probably|generally|typically|often|approximately|uncertain)\b", re.I)
_ABSENCE = re.compile(r"\b(no evidence|not established|not proven|unknown whether)\b", re.I)
_OF_ABSENCE = re.compile(r"\b(is false|does not exist|has been ruled out|is disproven)\b", re.I)


def uncertainty_state(text: str) -> str:
    t = text.lower()
    if _ABSENCE.search(t):
        return "lack_of_evidence"       # "no evidence that P" - epistemic absence
    if _OF_ABSENCE.search(t):
        return "evidence_of_absence"    # "P is false" - a positive negative claim
    if _HEDGE.search(t):
        return "hedged"
    return "none"


def preserved(gold_text: str, produced_text: str) -> bool:
    """Preserved iff the uncertainty STATE matches. Crucially, lack_of_evidence must NOT collapse to
    evidence_of_absence (the 'no evidence'->'false' inversion)."""
    return uncertainty_state(gold_text) == uncertainty_state(produced_text)
