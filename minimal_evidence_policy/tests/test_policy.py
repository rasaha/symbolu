"""Phases 2-3 tests: ordered vocabulary, risk floor, upward-only modifiers, invariants, and the
never-below-floor guarantee."""
from minimal_evidence_policy import schema as s, policy


def _item(**kw):
    base = {"artifact_id": "c", "risk_tier": "low", "claim_family": "process_description"}
    base.update(kw); return base


def test_ordering():
    assert s.RANK[s.E0] < s.RANK[s.E1] < s.RANK[s.E2] < s.RANK[s.E3] < s.RANK[s.E4] < s.RANK[s.ER]


def test_risk_floor():
    assert policy.assign(_item(risk_tier="low")).risk_floor == s.E1
    assert policy.assign(_item(risk_tier="high")).risk_floor == s.E3
    assert policy.assign(_item(risk_tier="critical")).risk_floor == s.E4
    assert policy.assign(_item(risk_tier="unknown")).risk_floor == s.ER


def test_e0_only_for_non_factual_low_risk():
    assert policy.assign(_item(claim_family="subjective_opinion", risk_tier="low")).final_obligation == s.E0
    # never E0 at high risk (INV-12)
    assert policy.assign(_item(claim_family="subjective_opinion", risk_tier="high")).final_obligation != s.E0
    # never E0 with factual leak
    assert policy.assign(_item(claim_family="subjective_opinion", risk_tier="low",
                               factual_leak=True)).final_obligation != s.E0


def test_regulated_min_e4():
    for fam in ("medical", "financial", "legal_interpretation"):
        assert policy.assign(_item(claim_family=fam, risk_tier="low")).final_obligation == s.E4


def test_model_self_verification_raised():
    d = policy.assign(_item(claim_family="current_fact", source_role="model_generated_text"))
    assert "INV-1.NO_MODEL_SELF_VERIFICATION" in d.invariants_triggered
    assert s.RANK[d.final_obligation] >= s.RANK[s.E3]


def test_action_requires_authority():
    d = policy.assign(_item(claim_family="code_behavior", claim_actionability="action_directive"))
    assert s.RANK[d.final_obligation] >= s.RANK[s.E3]
    assert any(c.startswith("INV-11") for c in d.invariants_triggered)


def test_never_below_risk_floor():
    for risk in ("low", "medium", "high", "critical"):
        for fam in ("subjective_opinion", "code_behavior", "medical", "current_fact"):
            d = policy.assign(_item(risk_tier=risk, claim_family=fam))
            if d.final_obligation != s.E0:                # E0 non-factual exemption
                assert s.RANK[d.final_obligation] >= s.RANK[d.risk_floor], (risk, fam)


def test_unknown_to_review():
    assert policy.assign(_item(risk_tier="unknown")).review_required is True
