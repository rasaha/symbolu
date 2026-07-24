"""Phase 10 tests: the obligation->EA contract never verifies a high-external-burden claim without
external evidence, marks obligation-relative VERIFIED for met low-burden standards, and drives the
frozen EA to the expected delivery.
"""
from evidence_obligation import schema as s, adapters, classifier
from governed_inference_pilot.adapters import evidence_assurance as ea


def _obl(otype, **kw):
    return s.new_obligation("c", "a", evidence_obligation_type=otype, **kw)


def test_high_external_burden_never_verified_without_evidence():
    for t in (s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, s.INDEPENDENT_CORROBORATION_REQUIRED,
              s.TELEMETRY_OR_MEASUREMENT_REQUIRED, s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED):
        steer = adapters.to_evidence_steer(_obl(t))
        assert steer["evidence_state"] != "VERIFIED"


def test_low_burden_met_is_obligation_relative_verified():
    o = _obl(s.IMPLEMENTATION_EVIDENCE_SUFFICIENT, implementation_inspectability=True)
    steer = adapters.to_evidence_steer(o)
    assert steer["evidence_state"] == "VERIFIED"
    assert steer["obligation_relative_verified"] is True       # not a truth claim


def test_implementation_absent_is_insufficient():
    o = _obl(s.IMPLEMENTATION_EVIDENCE_SUFFICIENT, implementation_inspectability=False)
    assert adapters.to_evidence_steer(o)["evidence_state"] == "INSUFFICIENT"


def test_external_with_injected_evidence_can_verify():
    o = _obl(s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED)
    av = adapters.available_evidence_for(o, override={"external": True})
    assert adapters.to_evidence_steer(o, av)["evidence_state"] == "VERIFIED"


def test_contract_drives_frozen_ea_to_allow_on_met_context():
    o = _obl(s.CONTEXTUAL_SUPPORT_SUFFICIENT)
    steer = adapters.to_evidence_steer(o)
    assert ea.run(steer, "low").local_disposition == "ALLOW"
