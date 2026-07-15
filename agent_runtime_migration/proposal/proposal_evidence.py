"""Advisory proposal evidence — may RAISE scrutiny, never authorize.

The runtime may attach advisory signals (risk notes, uncertainty) to a proposal as
context for the governor. This module deliberately produces only NON-authoritative
evidence: it returns advisory records, never an allow/deny.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Tuple


@dataclass(frozen=True)
class AdvisoryEvidence:
    kind: str                 # e.g. "uncertainty", "risk_note"
    detail: str
    raises_scrutiny: bool = False   # may be True; may NEVER lower scrutiny / authorize

    def to_dict(self) -> Dict[str, Any]:
        return {"kind": self.kind, "detail": self.detail,
                "raises_scrutiny": bool(self.raises_scrutiny), "authoritative": False}


def collect(*evidence: AdvisoryEvidence) -> Tuple[Dict[str, Any], ...]:
    return tuple(e.to_dict() for e in evidence)
