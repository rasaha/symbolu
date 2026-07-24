"""Tests for the real-reviewer calibration activation gate.

Covers the two decisive paths: (a) the SUPPLIED placeholder roster is blocked and no session activates,
and (b) a hypothetical fully-eligible real roster passes the gate. The eligibility gate must never treat a
placeholder or mock identity as a real reviewer.
"""
import pytest

from reviewer_session_activation import activation, eligibility
from reviewer_session_activation.provided_roster import PROVIDED_ROSTER


# ---------- frozen state ----------

def test_frozen_state_verifies():
    fs = activation.verify_frozen_state()
    assert fs.ok, [c for c in fs.checks if not c["ok"]]
    names = {c["check"] for c in fs.checks}
    assert "native_actiongate_vocabulary" in names
    assert "no_threshold_drift" in names


# ---------- supplied placeholder roster ----------

def test_supplied_roster_is_blocked():
    res = activation.activate(PROVIDED_ROSTER)
    assert res.activated is False
    assert res.decision == activation.D_NOT_ENOUGH
    assert res.eligibility.real_reviewer_count == 0
    assert res.final_set_may_open is False


def test_placeholder_reviewer_not_real():
    r = eligibility.validate_reviewer("R1", PROVIDED_ROSTER["R1"], required=True)
    assert r.is_real is False
    assert r.passed is False
    assert any("placeholder" in f for f in r.failures)


def test_is_placeholder_detection():
    assert eligibility.is_placeholder("[R1_ID]")
    assert eligibility.is_placeholder("[YES/NO]")
    assert eligibility.is_placeholder("")
    assert eligibility.is_placeholder(None)
    assert not eligibility.is_placeholder("REV-A")


def test_mock_identity_rejected():
    r = eligibility.validate_reviewer("R1", {
        "pseudonymous_id": "TEST-REVIEWER-1", "role": "TECHNICAL REVIEWER", "real_reviewer": "YES",
        "confidentiality_ack": "YES", "coi_declaration": "YES", "access_scope": "internal calibration"},
        required=True)
    assert r.is_real is False
    assert any("mock/test" in f for f in r.failures)


def test_optional_adjudicator_absent_is_not_a_failure_of_the_round():
    res = activation.activate(PROVIDED_ROSTER)
    # A1 is a placeholder/NONE -> recorded absent; it does not, by itself, change the R1/R2 block
    assert res.eligibility.adjudicator is not None
    assert res.eligibility.adjudicator.passed is False


# ---------- hypothetical fully-eligible real roster ----------

def _real_roster():
    common = {"real_reviewer": True, "confidentiality_ack": "YES", "coi_declaration": "YES"}
    return {
        "R1": {"pseudonymous_id": "REV-A", "role": "TECHNICAL REVIEWER",
               "access_scope": "internal calibration set", **common},
        "R2": {"pseudonymous_id": "REV-B", "role": "POLICY-RISK REVIEWER",
               "access_scope": "internal calibration set", **common},
    }


def test_real_roster_passes_eligibility():
    elig = eligibility.evaluate_roster(_real_roster())
    assert elig.activatable is True
    assert elig.real_reviewer_count == 2
    for r in elig.reviewers:
        assert r.is_real and r.passed, r.failures


def test_real_roster_activates_but_final_set_stays_closed_without_reviews():
    res = activation.activate(_real_roster())
    assert res.activated is True
    # even activated, with zero completed real reviews the final set cannot open
    assert res.final_set_may_open is False
    assert res.decision == activation.D_NOT_ENOUGH
    assert res.human_validation == "NOT_EVALUATED"


def test_missing_coi_blocks():
    roster = _real_roster()
    roster["R1"]["coi_declaration"] = "[YES/NO]"
    elig = eligibility.evaluate_roster(roster)
    assert elig.activatable is False
    assert any("conflict-of-interest" in f for f in elig.reviewers[0].failures)


def test_prohibited_artifact_assignment_blocks():
    roster = _real_roster()
    roster["R1"]["assigned_artifacts"] = ["final-set-item-1"]
    elig = eligibility.evaluate_roster(roster, prohibited_artifacts={"final-set-item-1"})
    assert elig.activatable is False
    assert any("prohibited" in f for f in elig.reviewers[0].failures)


# ---------- honesty guarantees ----------

def test_activation_never_claims_human_validation():
    res = activation.activate(PROVIDED_ROSTER)
    assert res.human_validation == "NOT_EVALUATED"
    assert res.external_pilot == "BLOCKED"
    assert res.production_readiness == "NOT_READY"


def test_decision_is_one_of_the_allowed_set():
    allowed = {activation.D_OPEN_FINAL, activation.D_REPEAT_GUIDE, activation.D_REPEAT_RETRAIN,
               activation.D_FIX_METADATA, activation.D_FIX_INTERFACE, activation.D_POLICY_TRACK,
               activation.D_NOT_ENOUGH, activation.D_STOP_SAFETY, activation.D_DO_NOT_PROCEED}
    assert activation.activate(PROVIDED_ROSTER).decision in allowed
