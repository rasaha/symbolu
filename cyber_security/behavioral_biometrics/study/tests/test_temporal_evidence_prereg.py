"""Temporal machinery, evidence export, preregistration."""

from __future__ import annotations

from cyber_security.behavioral_biometrics.study import (
    confidence, evidence, mockdata, preregistration, temporal,
)


# ---- temporal ----

def test_abrupt_takeover_detected():
    fx = mockdata.make_temporal("ABRUPT_TAKEOVER", seed=1)
    r = temporal.evaluate_stream(fx)
    assert r["arms"]["cusum"]["detected"]
    assert r["arms"]["cusum"]["time_to_detection_steps"] is not None


def test_legitimate_drift_low_false_challenges():
    fx = mockdata.make_temporal("LEGITIMATE_DRIFT", seed=1)
    r = temporal.evaluate_stream(fx)
    assert r["true_change"] is None


def test_temporal_makes_no_security_claim():
    fx = mockdata.make_temporal("ABRUPT_TAKEOVER", seed=1)
    v = temporal.temporal_verdict(fx, fx)
    assert v["verdict"] == temporal.TEMPORAL_PATH_VERIFIED
    assert not v["scientific"]


def test_temporal_arms_present():
    fx = mockdata.make_temporal("SLOW_TAKEOVER", seed=1)
    r = temporal.evaluate_stream(fx)
    for arm in temporal.ARMS:
        assert arm in r["arms"]


# ---- evidence export ----

def _conf():
    return confidence.build_confidence(identity_probability=0.8,
                                       calibration_status=confidence.CONFIDENCE_CALIBRATED,
                                       uncertainty=0.3, quality=0.9, evidence_sufficiency=0.7)


def test_evidence_build_and_validate():
    exp = evidence.build(session_id="s", timestamp="2026-01-01T00:00:00",
                         confidence_output=_conf(), data_origin="MOCK_TEST_ONLY").to_dict()
    assert evidence.validate(exp) == []


def test_evidence_no_authorization_decision():
    exp = evidence.build(session_id="s", timestamp="t", confidence_output=_conf(),
                         data_origin="MOCK_TEST_ONLY").to_dict()
    assert "recommended_evidence_action" in exp
    assert exp["recommended_evidence_action"] not in ("ALLOW", "DENY")
    # injecting an authorization token must fail validation
    exp["anomaly_state"] = {"decision": "ALLOW"}
    assert any("forbidden_authorization_token" in p for p in evidence.validate(exp))


def test_evidence_out_of_range_caught():
    exp = evidence.build(session_id="s", timestamp="t", confidence_output=_conf(),
                         data_origin="MOCK_TEST_ONLY").to_dict()
    exp["confidence"] = 1.5
    assert any("out_of_range" in p for p in evidence.validate(exp))


def test_evidence_missing_fields_caught():
    assert any("missing" in p for p in evidence.validate({"session_id": "s"}))


# ---- preregistration ----

def test_prereg_template_valid():
    assert preregistration.validate(preregistration.default_template()) == []


def test_prereg_missing_keys_caught():
    bad = preregistration.default_template()
    del bad["primary_contrast"]
    assert "missing:primary_contrast" in preregistration.validate(bad)


def test_prereg_roundtrip(tmp_path):
    p = preregistration.write_template(str(tmp_path / "prereg.json"))
    loaded = preregistration.load(p)
    assert preregistration.validate(loaded) == []
