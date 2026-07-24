"""M6 tests - label schema (Phase 10) + blinded review interface (Phase 11)."""
import pytest

from reviewer_ready_pilot import schema
from reviewer_ready_pilot.review_interface import BlindedReviewSession


def _artifact():
    return {"artifact_id": "rrp-test", "text": "A factual claim about current performance.",
            "source_path": "x/y.py", "source_kind": "docstring", "claim_family": "measured_performance",
            "risk_tier": "high", "source_role": "source_code", "claim_actionability": "none",
            "temporal_sensitivity": "current_status",
            # these must never appear in the blinded view:
            "gold_obligation": "E3_INDEPENDENT_OR_MEASURED_EVIDENCE", "trap_type": "fixture_as_telemetry"}


def _valid_a():
    return schema.StageALabel(obligation="E3", risk_tier="high", source_authority="non_authoritative",
                              obligation_satisfied=False, action_present=False, confidence=0.8, reason="perf")


def _valid_b(override=False):
    return schema.StageBLabel(obligation="E3", agreement=not override, override=override,
                              override_direction="stricter" if override else "none",
                              override_reason="needs telemetry" if override else "",
                              acceptable_actiongate_outcome="REQUEST_MORE_EVIDENCE",
                              explanation_useful=4, trace_comprehensible=True, confidence=0.7)


# ---- schema ----

def test_schema_rejects_bad_obligation():
    assert "obligation" in " ".join(schema.validate_stage_a(schema.StageALabel(obligation="E9", risk_tier="low", source_authority="unknown")))


def test_schema_rejects_e0_at_high_risk():
    errs = schema.validate_stage_a(schema.StageALabel(obligation="E0", risk_tier="high", source_authority="unknown"))
    assert any("E0 is invalid" in x for x in errs)


def test_schema_override_requires_reason_and_direction():
    bad = schema.StageBLabel(obligation="E3", override=True, override_direction="none", override_reason="")
    errs = schema.validate_stage_b(bad)
    assert any("reason" in x for x in errs) and any("direction" in x for x in errs)


def test_schema_actiongate_not_collapsed():
    bad = schema.StageBLabel(obligation="E3", acceptable_actiongate_outcome="allow")
    assert any("ActionGate" in x for x in schema.validate_stage_b(bad))
    assert "ALLOW_WITH_CONSTRAINTS" in schema.ACTIONGATE_OUTCOMES
    assert "ESCALATE_TO_HUMAN" in schema.ACTIONGATE_OUTCOMES


# ---- interface ----

def test_blinded_view_hides_system_result():
    s = BlindedReviewSession("REV-A", _artifact())
    v = s.blinded_view()
    for k in ("gold_obligation", "trap_type", "final_obligation", "rationale"):
        assert k not in v


def test_cannot_reveal_before_stage_a():
    s = BlindedReviewSession("REV-A", _artifact())
    with pytest.raises(ValueError):
        s.reveal({"final_obligation": "E3"})


def test_full_flow_agreement():
    s = BlindedReviewSession("REV-A", _artifact())
    s.submit_stage_a(_valid_a())
    res = s.reveal({"final_obligation": "E3", "actiongate_outcome": "REQUEST_MORE_EVIDENCE"})
    assert res["final_obligation"] == "E3"
    rec = s.submit_stage_b(_valid_b())
    assert rec.enforced is False and rec._locked is True
    assert rec.stage_b.agreement is True


def test_stage_a_immutable():
    s = BlindedReviewSession("REV-A", _artifact())
    s.submit_stage_a(_valid_a())
    with pytest.raises(ValueError):
        s.submit_stage_a(_valid_a())


def test_stage_b_requires_reveal():
    s = BlindedReviewSession("REV-A", _artifact())
    s.submit_stage_a(_valid_a())
    with pytest.raises(ValueError):
        s.submit_stage_b(_valid_b())


def test_override_flow_records_reason():
    s = BlindedReviewSession("REV-A", _artifact(), is_mock=True)
    s.submit_stage_a(_valid_a())
    s.reveal({"final_obligation": "E2"})
    rec = s.submit_stage_b(_valid_b(override=True))
    assert rec.stage_b.override is True and rec.stage_b.override_reason
    assert rec.enforced is False and rec.is_mock is True


def test_invalid_label_rejected_not_repaired():
    s = BlindedReviewSession("REV-A", _artifact())
    with pytest.raises(ValueError):
        s.submit_stage_a(schema.StageALabel(obligation="E0", risk_tier="high", source_authority="unknown"))
    assert s.record.stage_a is None


def test_record_serializable():
    s = BlindedReviewSession("REV-A", _artifact())
    s.submit_stage_a(_valid_a())
    s.reveal({"final_obligation": "E3"})
    s.submit_stage_b(_valid_b())
    d = s.record.as_dict()
    assert d["enforced"] is False and d["system_revealed"] is True
