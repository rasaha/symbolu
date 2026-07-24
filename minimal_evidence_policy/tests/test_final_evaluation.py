"""Phase 21 test: final evaluation passes all frozen criteria, is conservative on high-risk, and leaves
human validation NOT EVALUATED."""
from minimal_evidence_policy import final_evaluation as fe


def test_guards_and_all_criteria_pass():
    m = fe.run()
    assert m["guards"]["prior_artifacts_intact"] is True
    assert m["success_criteria_passed"] == m["success_criteria_total"]


def test_safety_instrumentation_clean():
    m = fe.run()
    assert m["self_verification_escape"] == 0
    assert m["monotonicity_violations"] == 0
    assert m["native_actiongate_preserved"] is True


def test_conservative_on_high_risk():
    m = fe.run()
    by = m["subgroups"]["by_risk_tier"]
    assert by["high"]["clean_allow_rate"] <= by["low"]["clean_allow_rate"]


def test_human_validation_not_evaluated():
    assert fe.run()["human_validation"] == "NOT_EVALUATED"
