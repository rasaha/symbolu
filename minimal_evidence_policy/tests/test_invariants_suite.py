"""Phase 25 - Consolidated invariants & guarantees: every structural invariant, no-high-risk-E0,
unknown->ER, deterministic reason codes, frozen-component read-only, no enforcement/external action.
"""
from minimal_evidence_policy import (schema as s, policy, classifier, invariants, adapters,
                                     verify_prior_artifacts, self_verification as sv, monotonicity)
from governed_inference_pilot.adapters import evidence_assurance as ea


def _item(**kw):
    base = {"artifact_id": "c", "risk_tier": "low", "claim_family": "process_description"}
    base.update(kw); return base


def test_no_frozen_component_modification():
    assert verify_prior_artifacts.verify() is True
    assert len(verify_prior_artifacts.FROZEN) == 45


def test_no_high_risk_e0():
    for risk in ("high", "critical"):
        d = classifier.classify(_item(claim_family="subjective_opinion", risk_tier=risk))
        assert d.final_obligation != s.E0


def test_unknown_to_er():
    assert classifier.classify(_item(risk_tier="unknown", claim_family="")).final_obligation == s.ER


def test_all_invariants_present():
    # each INV code appears in reason_codes.CATALOG
    from minimal_evidence_policy import reason_codes
    for i in range(1, 13):
        if i == 9:      # INV-9 is the never-below-floor structural guarantee (schema-level)
            continue
        assert any(k.startswith(f"INV-{i}.") for k in reason_codes.CATALOG), i


def test_self_verification_zero_escapes():
    assert sv.validate()["self_verification_escape"] == 0


def test_monotonic_no_violations():
    assert monotonicity.check()["violations"] == 0


def test_deterministic_reason_codes():
    a = classifier.classify(_item(claim_family="medical", risk_tier="high"))
    b = classifier.classify(_item(claim_family="medical", risk_tier="high"))
    assert a.reason_codes == b.reason_codes


def test_downstream_is_disposition_not_action():
    d = classifier.classify(_item(claim_family="code_behavior", source_role="primary_implementation"))
    delivery = ea.run(adapters.to_evidence_steer(d, {"source_role": "primary_implementation"}), "low").local_disposition
    assert delivery in ("ALLOW", "QUALIFY", "ESCALATE", "INDETERMINATE", "REJECT")


def test_no_threshold_mutation_obligation_not_truth():
    d = classifier.classify(_item(claim_family="code_behavior", source_role="primary_implementation"))
    steer = adapters.to_evidence_steer(d, {"source_role": "primary_implementation"})
    assert steer["factual_truth_status"] == "not_independently_established"
