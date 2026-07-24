"""Reference Assertion Governance Engine (Phase 8). Isolated; NOT integrated into the control
plane. Deterministic, stdlib-only, no live calls.

The engine works from CONTINUOUS inputs (grounding support scalar, claim-strength scalar, risk,
and coarse relation flags a real system gets from an NLI/grounding stage). It applies its OWN
continuous thresholds — deliberately NOT identical to the frozen rubric's exact cutoffs — so it
approximates rather than copies ground truth (anti-circularity) and is not tuned on eval.

Distinct outputs vs baselines: it emits a disposition AND a qualified rewrite (for QUALIFY) AND an
auditable reason/record — the transform + audit that pure signal-baselines do not produce.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from assertion_governance.taxonomy import Disposition, fail_closed

# engine thresholds (fixed a priori; NOT the rubric's exact 0.10/0.40 cutoffs)
_ALLOW_GAP = 0.12          # rubric uses 0.10  -> boundary disagreements expected
_ESCALATE_GAP = 0.38       # rubric uses 0.40  -> boundary disagreements expected
_SUPPORT_FLOOR = 0.15      # below this with no relation, treat as unsupported
_HIGH = ("high", "critical")


@dataclass
class AssertionInput:
    claim_text: str
    claim_strength: float
    evidence_support: float
    risk_class: str
    relation: str = "supports"          # coarse label from upstream NLI: supports/contradicts/neutral/missing/conflicting
    authority: str = "yes"
    policy: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssertionDecision:
    disposition: str
    delivered_text: str
    qualification: Optional[str]
    reason_codes: List[str]
    reason: str
    evidence_support: float
    risk_class: str
    audit: Dict[str, Any]


def _qualified_rewrite(claim: str, support: float) -> str:
    """Produce a scoped/hedged version of the claim (the QUALIFY transform)."""
    if support >= 0.5:
        hedge = "The available evidence suggests that"
    elif support >= 0.3:
        hedge = "Limited evidence indicates that"
    else:
        hedge = "There is weak, preliminary evidence that"
    low = claim[0].lower() + claim[1:] if claim else claim
    return f"{hedge} {low} (in the studied context)."


def govern(inp: AssertionInput) -> AssertionDecision:
    high = inp.risk_class in _HIGH
    gap = inp.claim_strength - inp.evidence_support
    codes: List[str] = []

    def decide():
        rel = inp.relation
        if rel == "contradicts":
            return Disposition.REJECT, "evidence contradicts the claim", ["ASSERT.CONTRADICTED"]
        if rel == "missing":
            if high:
                return Disposition.ESCALATE, "no evidence in a high-risk domain", ["ASSERT.MISSING_HIGH_RISK"]
            return Disposition.NOT_SUPPORTED, "no evidence addresses the claim", ["ASSERT.NO_EVIDENCE"]
        if rel == "conflicting":
            if high:
                return Disposition.ESCALATE, "conflicting evidence in a high-risk domain", ["ASSERT.CONFLICT_HIGH_RISK"]
            return Disposition.INDETERMINATE, "conflicting evidence", ["ASSERT.CONFLICT"]
        if rel == "neutral":
            return Disposition.INDETERMINATE, "evidence neither supports nor contradicts", ["ASSERT.NEUTRAL"]
        # supports (or unlabeled) — use continuous gap logic
        if inp.evidence_support < _SUPPORT_FLOOR:
            return Disposition.NOT_SUPPORTED, "support below floor", ["ASSERT.LOW_SUPPORT"]
        if gap <= _ALLOW_GAP:
            return Disposition.ALLOW, "evidence supports the claim at its stated strength", []
        if high and gap >= _ESCALATE_GAP:
            return Disposition.ESCALATE, "large overclaim in a high-risk domain", ["ASSERT.OVERCLAIM_HIGH_RISK"]
        return Disposition.QUALIFY, "claim overstates the evidence; delivering a scoped version", ["ASSERT.OVERCLAIM"]

    disp, reason, dcodes = decide()
    codes.extend(dcodes)

    delivered = inp.claim_text
    qualification = None
    if disp == Disposition.ALLOW:
        delivered = inp.claim_text
    elif disp == Disposition.QUALIFY:
        delivered = _qualified_rewrite(inp.claim_text, inp.evidence_support)
        qualification = "scoped to studied context; strength reduced to match evidence"
    else:
        delivered = ""  # withheld (REJECT/ESCALATE/INDETERMINATE/NOT_SUPPORTED)

    audit = {"claim_strength": inp.claim_strength, "evidence_support": inp.evidence_support,
             "gap": round(gap, 3), "risk_class": inp.risk_class, "relation": inp.relation,
             "disposition": disp.value, "reason_codes": codes, "engine": "age_reference_v1"}
    return AssertionDecision(disposition=disp.value, delivered_text=delivered,
                             qualification=qualification, reason_codes=codes, reason=reason,
                             evidence_support=inp.evidence_support, risk_class=inp.risk_class, audit=audit)


def govern_item(it) -> AssertionDecision:
    """Adapter from a dataset Item to the engine input (deployed-AGE input shape)."""
    return govern(AssertionInput(
        claim_text=it.claim_text, claim_strength=it.claim_strength,
        evidence_support=it.evidence_support, risk_class=it.risk_class,
        relation=it.evidence_relation, authority=it.authority_governed))
