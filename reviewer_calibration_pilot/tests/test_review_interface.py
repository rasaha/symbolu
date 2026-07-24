"""Phase 7 tests: blinded interface enforces blinding, immutability, override-reason, non-enforcement."""
import pytest
from reviewer_calibration_pilot import review_interface as ri

_ART = {"artifact_id": "a", "text": "x", "claim_family": "code_behavior", "risk_tier": "low",
        "source_role": "primary_implementation"}


def _sess():
    return ri.BlindedReviewSession("REV-A", _ART)


def test_blinded_view_has_no_system_result():
    bv = _sess().blinded_view()
    assert "gold_obligation" not in bv and "system" not in bv and "obligation" not in bv


def test_cannot_reveal_before_stage_a():
    with pytest.raises(ValueError):
        _sess().reveal({"obligation": "E2"})


def test_cannot_submit_blinded_twice():
    s = _sess(); s.submit_stage_a(ri.ReviewerJudgment(obligation="E2"))
    with pytest.raises(ValueError):
        s.submit_stage_a(ri.ReviewerJudgment(obligation="E1"))


def test_override_requires_reason():
    s = _sess(); s.submit_stage_a(ri.ReviewerJudgment(obligation="E1")); s.reveal({"obligation": "E2"})
    with pytest.raises(ValueError):
        s.submit_stage_b(ri.ReviewerJudgment(obligation="E3"), agreement=False, override=True)


def test_record_never_enforces_and_locks():
    s = _sess(); s.submit_stage_a(ri.ReviewerJudgment(obligation="E2")); s.reveal({"obligation": "E2"})
    rec = s.submit_stage_b(ri.ReviewerJudgment(obligation="E2"), agreement=True, override=False)
    assert rec.enforced is False
    assert rec._locked is True
    with pytest.raises(ValueError):
        s.submit_stage_b(ri.ReviewerJudgment(obligation="E2"), agreement=True, override=False)
