"""Phases 20-21 test: with no reviewers the calibration decision is Option 8 and the pilot decision is
Option I, both NOT ENOUGH HUMAN EVIDENCE."""
from reviewer_calibration_pilot import decision


def test_calibration_not_enough_human_evidence():
    m = decision.decide()
    assert m["calibration_decision"].startswith("8 NOT ENOUGH HUMAN EVIDENCE")


def test_pilot_not_enough_human_evidence():
    m = decision.decide()
    assert m["pilot_decision"].startswith("I NOT ENOUGH HUMAN EVIDENCE")


def test_external_readiness_blocked():
    m = decision.decide()
    assert "BLOCKED" in m["separated_dimensions"]["external_pilot_readiness"]
    assert m["reviewer_count"] == 0
