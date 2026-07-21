"""Deterministic polarity (negation) detection. Negation is never discarded."""

from __future__ import annotations

import re

from truth_assurance_pipeline.tap_e3_relationship_truth.schema import Polarity

# negation cues; "prohibited from" is a POSITIVE assertion of a prohibition, so it is
# NOT a negation cue here (it maps to PROHIBITED_FROM/PROHIBITS with POSITIVE polarity).
_NEG = (r"\bnot\b", r"\bnever\b", r"\bno longer\b", r"\bcannot\b", r"\bcan not\b",
        r"\bshall not\b", r"\bmust not\b", r"\bmay not\b", r"\bare not\b", r"\bis not\b",
        r"\bwithout\b")


def detect_polarity(clause: str) -> Polarity:
    low = clause.lower()
    if any(re.search(p, low) for p in _NEG):
        return Polarity.NEGATED
    return Polarity.POSITIVE
