"""Thin AssertionGate V1 (Phase 8). Combines signals, PROPAGATES uncertainty, applies domain-risk
policy, detects disagreement, requires qualification, escalates unresolved high-risk cases, emits
reason codes + provenance. Intentionally thin (a bounded rule set). Deterministic; no live calls;
no evidence retrieval; no action; never silently replaces the assertion; never hides missing or
conflicting inputs.

Central mechanism (tested, not assumed): ALLOW requires a CONJUNCTION — effective_support high AND
entailment supports AND adequacy ok AND uncertainty low. No single (possibly noisy) signal is
authoritative for ALLOW. Uncertainty (confidence/calibration/freshness/conflict/provenance/adequacy)
is discounted into effective_support and gates delivery — which helps on DETECTABLE noise and,
by construction, cannot help on silent/correlated noise (the confidence it propagates is itself
wrong there).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from assertion_gate_robustness.policy import GatePolicy, POLICY_VERSION
from assertion_gate_robustness.qualification import qualify_text
from assertion_gate_robustness.signals import SignalBundle
from assertion_gate_robustness.taxonomy import Disposition as D

GATE_VERSION = "assertion_gate_v1"


@dataclass
class GateDecision:
    disposition: str
    delivered_text: str
    qualification: Optional[str]
    reason_codes: List[str]
    uncertainty: float
    effective_support: float
    audit: Dict[str, Any]


def govern(bundle: SignalBundle, claim_strength: float, claim_text: str = "claim",
           policy: Optional[GatePolicy] = None, policy_version: str = POLICY_VERSION) -> GateDecision:
    pol = policy or GatePolicy()
    codes: List[str] = []

    # policy-version mismatch -> fail-closed (detectable perturbation #21)
    if not pol.compatible(policy_version):
        return _mk(D.ESCALATE.value, "", None, ["ASSERT.POLICY_VERSION_MISMATCH"], 1.0, 0.0, bundle, claim_strength)

    high = bundle.high_risk()
    unc = bundle.uncertainty()
    eff = bundle.effective_support()
    gap = claim_strength - bundle.grounding.support

    def decide():
        # 1. contradiction may independently REJECT (only high-confidence)
        if bundle.entailment.label == "contradicts" and bundle.entailment.confidence >= 0.5:
            return D.REJECT.value, ["ASSERT.CONTRADICTED"]
        # 2. explicit disagreement between grounding and entailment -> surface, never average away
        if bundle.grounding.support >= 0.6 and bundle.entailment.label == "contradicts":
            return (D.ESCALATE.value if high else D.INDETERMINATE.value), ["ASSERT.SIGNAL_DISAGREEMENT"]
        # 3. major evidence conflict
        if bundle.evidence.conflict == "major":
            return (D.ESCALATE.value if high else D.INDETERMINATE.value), ["ASSERT.EVIDENCE_CONFLICT"]
        # 4. uncertainty propagation: unreliable signals -> withhold (this is the robustness lever)
        if unc >= pol.uncertainty_ceiling:
            return (D.ESCALATE.value if high else D.INDETERMINATE.value), ["ASSERT.HIGH_UNCERTAINTY"]
        # 5. missing / no support
        if eff < pol.support_floor and bundle.entailment.label != "supports":
            return (D.ESCALATE.value if high else D.NOT_SUPPORTED.value), ["ASSERT.NO_SUPPORT"]
        # 6. inadequate evidence -> cannot ALLOW
        if bundle.evidence.adequacy < pol.adequacy_floor:
            return (D.ESCALATE.value if high else D.QUALIFY.value), ["ASSERT.INADEQUATE_EVIDENCE"]
        # 7. stale in high-risk -> escalate; else qualify
        if bundle.evidence.is_stale():
            return (D.ESCALATE.value if high else D.QUALIFY.value), ["ASSERT.STALE_EVIDENCE"]
        # 8. neutral entailment -> indeterminate
        if bundle.entailment.label == "neutral":
            return D.INDETERMINATE.value, ["ASSERT.NEUTRAL"]
        # 9. supported: gap logic on CONJUNCTION (effective support high AND supports AND adequate)
        if gap <= pol.allow_gap and eff >= 0.55:
            return D.ALLOW.value, []
        if high and gap >= pol.escalate_gap:
            return D.ESCALATE.value, ["ASSERT.OVERCLAIM_HIGH_RISK"]
        return D.QUALIFY.value, ["ASSERT.OVERCLAIM"]

    disp, dcodes = decide()
    codes.extend(dcodes)
    delivered = claim_text if disp == D.ALLOW.value else (
        qualify_text(claim_text, bundle.grounding.support) if disp == D.QUALIFY.value else "")
    qual = None if disp != D.QUALIFY.value else "scoped to studied context; strength reduced to evidence"
    return _mk(disp, delivered, qual, codes, unc, eff, bundle, claim_strength)


def _mk(disp, delivered, qual, codes, unc, eff, bundle, claim):
    audit = {"disposition": disp, "reason_codes": codes, "uncertainty": round(unc, 3),
             "effective_support": round(eff, 3), "raw_support": round(bundle.grounding.support, 3),
             "entailment": bundle.entailment.label, "adequacy": round(bundle.evidence.adequacy, 3),
             "conflict": bundle.evidence.conflict, "stale": bundle.evidence.is_stale(),
             "risk": bundle.risk_class, "gate": GATE_VERSION}
    return GateDecision(disp, delivered, qual, codes, round(unc, 3), round(eff, 3), audit)


def govern_disposition(bundle: SignalBundle, claim_strength: float) -> str:
    return govern(bundle, claim_strength).disposition
