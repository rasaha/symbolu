"""Phase 2 - Minimal evidence-obligation schema.

A small ORDERED obligation vocabulary and the decision record. The policy never declares a claim true,
never judges evidence sufficiency, never lowers a frozen threshold, and never authorizes delivery/action.

Ordering (strict): E0 < E1 < E2 < E3 < E4 < ER. No modifier may lower the result below the risk floor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

POLICY_VERSION = "minimal_evidence_policy_v1"

# the six ordered obligation levels
E0 = "E0_NO_FACTUAL_EVIDENCE_GATE"
E1 = "E1_CONTEXTUAL_SUPPORT"
E2 = "E2_AUTHORITATIVE_INTERNAL_OR_IMPLEMENTATION_EVIDENCE"
E3 = "E3_INDEPENDENT_OR_MEASURED_EVIDENCE"
E4 = "E4_EXTERNAL_AUTHORITATIVE_EVIDENCE_AND_REVIEW"
ER = "ER_HUMAN_REVIEW_OR_INDETERMINATE"

LEVELS = (E0, E1, E2, E3, E4, ER)
RANK = {lvl: i for i, lvl in enumerate(LEVELS)}   # E0=0 ... ER=5

RISK_TIERS = ("low", "medium", "high", "critical", "unknown")


def higher(a: str, b: str) -> str:
    """Return the stronger (higher-rank) obligation. Used to keep modifiers upward-only."""
    return a if RANK[a] >= RANK[b] else b


@dataclass
class Decision:
    """One minimal-policy decision, fully explainable in a single trace."""
    claim_id: str
    risk_floor: str                          # obligation from the risk floor alone
    modifiers_applied: List[str] = field(default_factory=list)
    invariants_triggered: List[str] = field(default_factory=list)
    final_obligation: str = ER
    rationale: str = ""
    unresolved_fields: List[str] = field(default_factory=list)
    review_required: bool = False
    reason_codes: List[str] = field(default_factory=list)
    policy_version: str = POLICY_VERSION

    def is_review(self) -> bool:
        return self.final_obligation == ER or self.review_required


def validate(d: Decision) -> List[str]:
    """Structural validation. Returns violation codes (empty = valid)."""
    v: List[str] = []
    if d.final_obligation not in LEVELS:
        v.append("MP.UNKNOWN_LEVEL")
    if d.risk_floor not in LEVELS:
        v.append("MP.UNKNOWN_FLOOR")
    # INV-9: final must never be below the risk floor
    if d.final_obligation in LEVELS and d.risk_floor in LEVELS and \
            RANK[d.final_obligation] < RANK[d.risk_floor]:
        v.append("MP.BELOW_RISK_FLOOR")
    return v
