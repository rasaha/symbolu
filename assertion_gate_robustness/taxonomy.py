"""Disposition taxonomy (Phase 8), isolated for this track. Mirrors the AGE delivery vocabulary
but is defined independently here (no import from the frozen AGE package)."""
from __future__ import annotations

from enum import Enum


class Disposition(str, Enum):
    ALLOW = "ALLOW"
    QUALIFY = "QUALIFY"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"
    INDETERMINATE = "INDETERMINATE"
    NOT_SUPPORTED = "NOT_SUPPORTED"


# conservativeness order (higher = more conservative / safer withholding)
CONSERVATISM = {
    Disposition.ALLOW.value: 0, Disposition.QUALIFY.value: 1, Disposition.INDETERMINATE.value: 2,
    Disposition.NOT_SUPPORTED.value: 2, Disposition.ESCALATE.value: 3, Disposition.REJECT.value: 3,
}

# "not deliverable as written" — delivering these as ALLOW is an unsupported-escape
NOT_DELIVERABLE = {Disposition.QUALIFY.value, Disposition.REJECT.value, Disposition.ESCALATE.value,
                   Disposition.INDETERMINATE.value, Disposition.NOT_SUPPORTED.value}

PRIMARY = (Disposition.ALLOW.value, Disposition.QUALIFY.value, Disposition.REJECT.value,
           Disposition.ESCALATE.value, Disposition.INDETERMINATE.value)


def to_primary(d: str) -> str:
    return Disposition.INDETERMINATE.value if d == Disposition.NOT_SUPPORTED.value else d


def more_conservative(a: str, b: str) -> str:
    return a if CONSERVATISM[a] >= CONSERVATISM[b] else b
