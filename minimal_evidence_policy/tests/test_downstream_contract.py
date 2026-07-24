"""Phase 9 tests: E3/E4 never VERIFIED without independent evidence; E0/E1/E2-met -> ALLOW; obligation
is represented separately from truth."""
from minimal_evidence_policy import schema as s, adapters, classifier
from governed_inference_pilot.adapters import evidence_assurance as ea


def _dec(level):
    return s.Decision(claim_id="c", risk_floor=level, final_obligation=level)


def test_high_burden_never_verified_without_evidence():
    for lvl in (s.E3, s.E4, s.ER):
        assert adapters.to_evidence_steer(_dec(lvl), {})["evidence_state"] != "VERIFIED"


def test_e2_met_is_obligation_relative_allow():
    it = {"source_role": "primary_implementation"}
    steer = adapters.to_evidence_steer(_dec(s.E2), it)
    assert steer["evidence_state"] == "VERIFIED"
    assert steer["obligation_relative_verified"] is True
    assert steer["factual_truth_status"] == "not_independently_established"
    assert ea.run(steer, "low").local_disposition == "ALLOW"


def test_e2_absent_evidence_insufficient():
    steer = adapters.to_evidence_steer(_dec(s.E2), {"source_role": "generated_documentation"})
    assert steer["evidence_state"] == "INSUFFICIENT"


def test_e3_with_injected_telemetry_can_verify():
    av = adapters.available_evidence_for({}, override={"telemetry": True})
    assert adapters.to_evidence_steer(_dec(s.E3), {}, av)["evidence_state"] == "VERIFIED"
