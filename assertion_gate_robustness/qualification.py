"""Qualification transform + robustness checks (Phase 10). Rule-based scoped rewrite; no new facts,
no meaning reversal. Metrics: semantic preservation, unsupported-content removal, new-claim
introduction, usefulness. Deterministic; no live calls; never invents evidence.
"""
from __future__ import annotations

from typing import Dict

_HEDGES = {
    "strong": "The available evidence indicates that",
    "moderate": "Limited evidence suggests that",
    "weak": "There is only weak, preliminary evidence that",
}


def _band(support: float) -> str:
    return "strong" if support >= 0.5 else "moderate" if support >= 0.3 else "weak"


def qualify_text(claim: str, support: float) -> str:
    hedge = _HEDGES[_band(support)]
    low = claim[0].lower() + claim[1:] if claim else claim
    return f"{hedge} {low} (in the studied context)."


# --- robustness metrics (rule-based proxies) -------------------------------

def semantic_preservation(claim: str, qualified: str) -> float:
    """Does the qualified text still reference the original claim tokens? proxy in [0,1]."""
    if not qualified:
        return 0.0
    ctoks = set(claim.lower().replace("[", " ").replace("]", " ").split())
    qtoks = set(qualified.lower().split())
    if not ctoks:
        return 1.0
    return round(len(ctoks & qtoks) / len(ctoks), 3)


def new_claim_introduced(claim: str, qualified: str) -> bool:
    """Any content token in qualified beyond claim + allowed hedge vocabulary."""
    allowed = set()
    for h in _HEDGES.values():
        allowed |= set(h.lower().split())
    allowed |= {"(in", "the", "studied", "context).", "that", "context)"}
    ctoks = set(claim.lower().replace("[", " ").replace("]", " ").split())
    extra = set(qualified.lower().split()) - ctoks - allowed
    # extra tokens should be only punctuation/hedge remnants
    extra = {t for t in extra if any(ch.isalpha() for ch in t)}
    return len(extra) > 0


def removes_unsupported_certainty(claim: str, qualified: str) -> bool:
    """Qualified text must add a hedge (reduce certainty)."""
    return any(qualified.startswith(h.split()[0]) or h.split()[0].lower() in qualified.lower()
               for h in _HEDGES.values())


def qualification_report(claim: str, support: float) -> Dict[str, float]:
    q = qualify_text(claim, support)
    return {"semantic_preservation": semantic_preservation(claim, q),
            "new_claim_introduced": int(new_claim_introduced(claim, q)),
            "removes_certainty": int(removes_unsupported_certainty(claim, q)),
            "usefulness": 1.0 if len(q) > len(claim) else 0.5}
