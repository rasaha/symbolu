"""
test_trust_observables.py — Phase-1 trust-observable layer (product, torch-free).

Covers the required decision invariants:
  * a hard veto beats a high (confident) trust signal
  * high raw entropy + high verbalized safety on a write tool → CONFIRM (the gap)
  * low entropy + high verbalized safety with no other risk → ALLOW
  * a provisional observable can advise (CONFIRM) but never BLOCK
  * a CG/RESEARCH observable never affects the decision
  * the audit trail records which observable drove the decision
"""

from __future__ import annotations

from agentic.agentic_framework.trust import (
    EvidenceStatus,
    Observation,
    ObservableType,
    TrustDecision,
    Verdict,
    decide,
    observe_tool_call,
)
from agentic.agentic_framework.trust.observables import TRUST_CLAIM_SAFE


# ---- decision model (pure) ---------------------------------------------------

def _veto(verdict):
    return Observation("tool_validity", ObservableType.HARD_VETO,
                       EvidenceStatus.PROVEN, verdict, severity=1.0,
                       reason="hallucinated tool")


def _confident_claim():
    return Observation("verbalized_safety", ObservableType.TRUST_SIGNAL,
                       EvidenceStatus.PROVEN, Verdict.SAFE, severity=0.0,
                       reason="model claims safe", direction=TRUST_CLAIM_SAFE)


def test_hard_veto_beats_high_trust_signal():
    out = decide([_confident_claim(), _veto(Verdict.UNSAFE)])
    assert out.decision == TrustDecision.BLOCK
    assert "tool_validity" in [o.name for o in out.drivers]


def test_confident_claim_cannot_raise_trust_or_block():
    # A confident claim alongside a proven validator UNSURE must not suppress the CONFIRM.
    validator_unsure = Observation("raw_entropy", ObservableType.VALIDATOR,
                                   EvidenceStatus.PROVEN, Verdict.UNSURE, severity=0.9)
    out = decide([_confident_claim(), validator_unsure])
    assert out.decision == TrustDecision.CONFIRM


def test_provisional_observable_cannot_block():
    prov = Observation("input_risk", ObservableType.VALIDATOR,
                       EvidenceStatus.PROVISIONAL, Verdict.UNSAFE, severity=0.9)
    out = decide([prov])
    assert out.decision == TrustDecision.CONFIRM      # advises, never blocks
    assert out.decision != TrustDecision.BLOCK


def test_research_observable_never_affects_decision():
    research = Observation("vritti_risk", ObservableType.VALIDATOR,
                           EvidenceStatus.RESEARCH, Verdict.UNSAFE, severity=1.0)
    out = decide([research])
    assert out.decision == TrustDecision.ALLOW


def test_audit_records_driver():
    out = decide([_veto(Verdict.UNSAFE)])
    audit = out.to_audit()
    assert audit["trust_decision"] == "block"
    assert "tool_validity" in audit["trust_drivers"]
    assert any(o["name"] == "tool_validity" for o in audit["trust_observations"])


# ---- registry builder (formalizes the proven gateway signals) ----------------

def test_high_entropy_plus_high_verbalized_safety_confirms_on_write():
    obs = observe_tool_call(
        tool_risk_level="write", raw_entropy=0.9, verbalized_safety_confidence=0.95)
    out = decide(obs)
    assert out.decision == TrustDecision.CONFIRM
    names = [o.name for o in out.drivers]
    assert "confidence_risk_gap" in names or "raw_entropy" in names


def test_low_entropy_plus_high_verbalized_safety_allows_when_no_other_risk():
    obs = observe_tool_call(
        tool_risk_level="write", raw_entropy=0.1, verbalized_safety_confidence=0.95)
    out = decide(obs)
    assert out.decision == TrustDecision.ALLOW


def test_unregistered_tool_blocks_even_when_confident():
    obs = observe_tool_call(
        tool_risk_level="write", raw_entropy=0.1,
        verbalized_safety_confidence=0.99, tool_registered=False)
    out = decide(obs)
    assert out.decision == TrustDecision.BLOCK
    assert "tool_validity" in [o.name for o in out.drivers]


def test_budget_exceeded_blocks():
    obs = observe_tool_call(tool_risk_level="read_only", budget_exceeded=True)
    out = decide(obs)
    assert out.decision == TrustDecision.BLOCK
    assert "budget_gate" in [o.name for o in out.drivers]


def test_approval_required_confirms_not_blocks():
    obs = observe_tool_call(tool_risk_level="write", raw_entropy=0.1,
                            requires_confirmation=True)
    out = decide(obs)
    assert out.decision == TrustDecision.CONFIRM


def test_registry_declares_cg_as_research_only():
    from agentic.agentic_framework.trust import CG_RESEARCH_OBSERVABLES, PRODUCT_OBSERVABLES
    # No CG-state signal is a product observable.
    for cg in ("vritti_risk", "guna", "kosha", "jepa_regime", "bhava_write", "csr"):
        assert cg not in PRODUCT_OBSERVABLES
        assert cg in CG_RESEARCH_OBSERVABLES
    # The product observables that exist are the proven ones.
    assert "raw_entropy" in PRODUCT_OBSERVABLES
    assert "confidence_risk_gap" in PRODUCT_OBSERVABLES
