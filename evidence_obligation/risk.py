"""Phase 14 - Risk escalation (component under test).

Determines the risk tier of a claim and how risk elevates the evidence obligation. Risk can only RAISE
an obligation, never lower it. Low-risk source classification must never override high-impact use: an
inspectable implementation detail with a high-impact deployment consequence is high risk.

Deterministic, fail-closed: ambiguous risk resolves upward (to the safer, higher tier).
"""
from __future__ import annotations

import re
from typing import List, Tuple

_HIGH_IMPACT = re.compile(
    r"\b(security|vulnerab|exploit|credential|secret|delete|irreversible|production|payment|"
    r"access\s+control|authenticat|authoriz|privileg|patient|clinical|financial|medical|legal|"
    r"regulat|compliance|breach|leak)\w*", re.I)
_ABSOLUTE = re.compile(r"\b(always|never|guarantee|100\s*%|fully\s+secure|completely\s+safe|zero\s+risk|"
                       r"impossible|cannot\s+fail)\b", re.I)
# claim families that are intrinsically high-risk regardless of surface
_HIGH_RISK_FAMILIES = {"medical", "financial", "legal_interpretation", "action_proposal", "permission"}
_ELEVATED_FAMILIES = {"external_regulation", "causal", "unsupported_marketing", "current_fact"}


def assess_risk(text: str, claim_family: str, intended_use: str = "review",
                actionability: str = "none") -> Tuple[str, List[str]]:
    """Return (risk_tier, reason_codes). Ambiguity resolves upward."""
    codes: List[str] = []
    t = text or ""
    tier = "low"

    if claim_family in _HIGH_RISK_FAMILIES:
        tier = "high"; codes.append("RISK.HIGH_FAMILY")
    elif claim_family in _ELEVATED_FAMILIES:
        tier = "medium"; codes.append("RISK.ELEVATED_FAMILY")

    if _HIGH_IMPACT.search(t):
        tier = _max(tier, "high"); codes.append("RISK.HIGH_IMPACT_CONTENT")
    if _ABSOLUTE.search(t):
        tier = _max(tier, "medium"); codes.append("RISK.ABSOLUTE_CLAIM")

    # actionability / intended use elevate risk (low-risk source cannot override high-impact use)
    if actionability in ("action_proposal", "action_directive"):
        tier = _max(tier, "high"); codes.append("RISK.ACTIONABLE")
    if intended_use in ("enforcement", "customer_delivery", "high_impact_decision"):
        tier = _max(tier, "high"); codes.append("RISK.HIGH_IMPACT_USE")

    return tier, codes


_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _max(a: str, b: str) -> str:
    return a if _ORDER[a] >= _ORDER[b] else b


def escalate_obligation(base_obligation: str, risk_tier: str, claim_family: str) -> Tuple[str, List[str]]:
    """Apply risk escalation to a base obligation via the taxonomy's high_risk field. Never lowers."""
    from evidence_obligation import taxonomy
    if risk_tier in ("high", "critical"):
        escalated = taxonomy.rule_for(claim_family).get("high_risk", base_obligation)
        from evidence_obligation import ground_truth as _gt  # burden ranking (independent order)
        if _gt._RANK.get(escalated, 0) > _gt._RANK.get(base_obligation, 0):
            return escalated, ["RISK.OBLIGATION_ESCALATED"]
    return base_obligation, []
