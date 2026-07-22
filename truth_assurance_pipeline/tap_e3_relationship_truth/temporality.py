"""
Deterministic temporality + date-interval extraction.

Represents the temporal relationship STATED in the evidence (current / historical /
future / superseded / conditional-time / unresolved) and preserves explicit
valid_from / valid_until when present. It does NOT decide legal applicability.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from truth_assurance_pipeline.tap_e3_relationship_truth.schema import Temporality

_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august",
           "september", "october", "november", "december")
_DATE = (r"(?:\d{4}-\d{2}-\d{2}"
         r"|(?:%s)\s+\d{1,2}(?:,?\s+\d{4})?"
         r"|\d{1,2}\s+(?:%s)(?:\s+\d{4})?)" % ("|".join(_MONTHS), "|".join(_MONTHS)))

_HIST = (r"\bpreviously\b", r"\bused to\b", r"\bformerly\b", r"\bhistorically\b",
         r"\bin the past\b", r"\bno longer\b")
_FUTURE = (r"\bwill\b", r"\bwill be\b", r"\bin the future\b", r"\bplanned to\b")


@dataclass(frozen=True)
class TemporalResult:
    temporality: Temporality
    valid_from: Optional[str]
    valid_until: Optional[str]


def _find_date(clause: str, after: str) -> Optional[str]:
    m = re.search(after + r"\s+(?:the\s+)?(" + _DATE + r")", clause, re.I)
    return m.group(1).strip() if m else None


def detect_temporality(clause: str, is_superseded: bool = False,
                       is_conditional: bool = False) -> TemporalResult:
    low = clause.lower()
    valid_from = _find_date(low, r"(?:from|effective|as of|starting)")
    valid_until = _find_date(low, r"(?:until|through|expires on|ends on|terminating on)")

    if is_superseded:
        return TemporalResult(Temporality.SUPERSEDED, valid_from, valid_until)
    if any(re.search(p, low) for p in _HIST):
        return TemporalResult(Temporality.HISTORICAL, valid_from, valid_until)
    if any(re.search(p, low) for p in _FUTURE):
        return TemporalResult(Temporality.FUTURE, valid_from, valid_until)
    if is_conditional:
        return TemporalResult(Temporality.CONDITIONAL_TIME, valid_from, valid_until)
    return TemporalResult(Temporality.CURRENT, valid_from, valid_until)
