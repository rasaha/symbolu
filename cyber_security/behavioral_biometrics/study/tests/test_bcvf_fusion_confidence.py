"""BCVF, fusion, and confidence machinery (branches + eligibility + calibration)."""

from __future__ import annotations

import numpy as np

from cyber_security.behavioral_biometrics.study import bcvf, confidence, fusion, mockdata
from cyber_security.behavioral_biometrics.study.effects import DEFAULT

CFG = DEFAULT


# ---- BCVF ----

def test_normalized_disagreement_math():
    q = bcvf.normalized_disagreement([1.0], [0.0], [1.0], [1.0])
    assert abs(q[0] - (1.0 / (2.0 + 1e-3))) < 1e-6


def test_robust_accumulation_monotone_nondecreasing():
    q = np.array([2.0, 2.0, 2.0])
    M = bcvf.robust_accumulate(q, eta=1.0, kappa=0.5)
    assert M[2] >= M[1] >= M[0] > 0


def test_bcvf_requires_two_qualifying_estimators():
    d = mockdata.make_bcvf("BCVF_HELPFUL", seed=1, n=400)
    rows = dict(d["rows"])
    rows["z2"] = np.zeros(len(rows["z2"])).tolist()  # second estimator is pure chance
    r = bcvf.evaluate_bcvf(rows, cfg=CFG, iters=150)
    assert not r["eligible"]
    assert bcvf.classify_bcvf(r, CFG) == bcvf.BCVF_NOT_ELIGIBLE


def test_bcvf_fast_slow_pair_forbidden():
    ok, why = bcvf.estimator_pair_eligible("ewma_fast", "ewma_slow")
    assert not ok
    ok2, _ = bcvf.estimator_pair_eligible("keyboard", "keyboard")
    assert not ok2
    ok3, _ = bcvf.estimator_pair_eligible("keyboard", "pointer")
    assert ok3


def test_bcvf_helpful_branch():
    d = mockdata.make_bcvf("BCVF_HELPFUL", seed=1, n=500)
    r = bcvf.evaluate_bcvf(d["rows"], cfg=CFG, iters=300)
    assert r["eligible"]
    assert bcvf.classify_bcvf(r, CFG) in (bcvf.BCVF_INCREMENTAL_VALUE_SUPPORTED,
                                          bcvf.BCVF_INCREMENTAL_VALUE_SMALL_EFFECT)


def test_bcvf_redundant_branch():
    d = mockdata.make_bcvf("BCVF_REDUNDANT", seed=1, n=500)
    r = bcvf.evaluate_bcvf(d["rows"], cfg=CFG, iters=300)
    assert bcvf.classify_bcvf(r, CFG) in (bcvf.BCVF_NO_INCREMENTAL_VALUE,
                                          bcvf.BCVF_INCREMENTAL_VALUE_SMALL_EFFECT)


def test_bcvf_classify_all_branches_pure():
    def r(lo, pt, fc=0.0, cal=0.0):
        return {"usable": True, "eligible": True,
                "gain": {"lo": lo, "point": pt, "hi": pt + 0.03},
                "false_challenge_increase": fc, "calibration_regression": cal}
    assert bcvf.classify_bcvf(r(0.05, 0.08), CFG) == bcvf.BCVF_INCREMENTAL_VALUE_SUPPORTED
    assert bcvf.classify_bcvf(r(0.01, 0.03), CFG) == bcvf.BCVF_INCREMENTAL_VALUE_SMALL_EFFECT
    assert bcvf.classify_bcvf(r(-0.01, 0.01), CFG) == bcvf.BCVF_NO_INCREMENTAL_VALUE
    assert bcvf.classify_bcvf(r(-0.05, -0.03), CFG) == bcvf.BCVF_REGRESSES
    assert bcvf.classify_bcvf({"usable": True, "eligible": False}, CFG) == bcvf.BCVF_NOT_ELIGIBLE


# ---- fusion ----

def test_fusion_helpful_positive_gain():
    d = mockdata.make_fusion("FUSION_HELPFUL", seed=1)
    r = fusion.evaluate_fusion(d["rows"], cfg=CFG, iters=300)
    assert r["gain_over_best_single"]["point"] > 0
    assert fusion.classify_fusion(r, CFG) in (fusion.FUSION_SUPPORTED, fusion.FUSION_SMALL_EFFECT)


def test_fusion_redundant_no_value():
    d = mockdata.make_fusion("FUSION_REDUNDANT", seed=1)
    r = fusion.evaluate_fusion(d["rows"], cfg=CFG, iters=300)
    assert fusion.classify_fusion(r, CFG) in (fusion.FUSION_NO_VALUE, fusion.FUSION_SMALL_EFFECT)


def test_fusion_classify_all_branches_pure():
    def r(lo, hi):
        return {"usable": True, "gain_over_best_single": {"lo": lo, "point": (lo + hi) / 2, "hi": hi}}
    assert fusion.classify_fusion(r(0.05, 0.1), CFG) == fusion.FUSION_SUPPORTED
    assert fusion.classify_fusion(r(0.005, 0.05), CFG) == fusion.FUSION_SMALL_EFFECT
    assert fusion.classify_fusion(r(-0.01, 0.02), CFG) == fusion.FUSION_NO_VALUE
    assert fusion.classify_fusion(r(-0.1, -0.02), CFG) == fusion.FUSION_REGRESSES
    assert fusion.classify_fusion({"usable": False}, CFG) == fusion.FUSION_NOT_ELIGIBLE


def test_channel_fusion_hard_gate_and_missing():
    ch = {"identity": {"value": 0.9, "quality": 1.0, "present": True},
          "liveness": {"value": 0.1, "present": True},
          "device": {"value": 0.8, "present": False}}
    out = fusion.fuse_channels(ch, hard_gates={"liveness": 0.5})
    assert out["hard_gate_failed"] == ["liveness"]
    assert out["conservative"] and out["fused"] <= 0.5
    assert out["n_present"] == 2  # missing device dropped


def test_inverse_variance_fusion():
    r = fusion.inverse_variance_fuse([1.0, 3.0], [1.0, 1.0])
    assert abs(r["estimate"] - 2.0) < 1e-9
    r2 = fusion.inverse_variance_fuse([1.0, 3.0], [0.01, 100.0])  # first dominates
    assert r2["estimate"] < 1.5


# ---- confidence ----

def test_confidence_calibrated_branch():
    d = mockdata.make_confidence("CONFIDENCE_WELL_CALIBRATED", seed=1)
    r = confidence.calibrate_and_evaluate(d["rows"]["scores"], d["rows"]["labels"], cfg=CFG)
    assert confidence.classify_confidence(r, CFG) == confidence.CONFIDENCE_CALIBRATED


def test_confidence_miscalibrated_branch():
    d = mockdata.make_confidence("CONFIDENCE_MISCALIBRATED", seed=1)
    r = confidence.calibrate_and_evaluate(d["rows"]["scores"], d["rows"]["labels"], cfg=CFG)
    assert confidence.classify_confidence(r, CFG) == confidence.CONFIDENCE_MISCALIBRATED


def test_confidence_small_sample_branch():
    r = confidence.calibrate_and_evaluate([0.5, 0.6, 0.7], [1, 0, 1], cfg=CFG)
    assert confidence.classify_confidence(r, CFG) == confidence.CONFIDENCE_SMALL_SAMPLE


def test_confidence_requires_held_out_evaluation():
    # a calibrator perfect on TRAIN but drifted on TEST must be caught as miscalibrated
    d = mockdata.make_confidence("CONFIDENCE_MISCALIBRATED", seed=2)
    for method in ("platt", "isotonic", "histogram"):
        r = confidence.calibrate_and_evaluate(d["rows"]["scores"], d["rows"]["labels"], method=method, cfg=CFG)
        assert r["ece"] > CFG.effects.max_confidence_ece


def test_calibrators_reduce_ece_on_fixable_fixture():
    rng = np.random.default_rng(0)
    n = 400
    p = rng.uniform(0, 1, n)
    y = (rng.random(n) < p).astype(int)
    over = np.clip(p ** 0.3, 1e-3, 1 - 1e-3)  # monotone overconfidence -> isotonic fixes it
    r = confidence.calibrate_and_evaluate(over, y, method="isotonic", cfg=CFG)
    assert r["calibrated_ece"] <= r["raw_ece"] + 1e-9


def test_structured_confidence_and_actions():
    hi = confidence.build_confidence(identity_probability=0.95,
                                     calibration_status=confidence.CONFIDENCE_CALIBRATED,
                                     uncertainty=0.1, quality=0.95, evidence_sufficiency=0.9)
    assert hi["recommended_evidence_action"] == confidence.CONTINUE_PASSIVE
    lo = confidence.build_confidence(identity_probability=0.55, calibration_status="x",
                                     uncertainty=0.2, quality=0.5, evidence_sufficiency=0.1)
    assert lo["recommended_evidence_action"] == confidence.INSUFFICIENT_EVIDENCE
    assert hi["recommended_evidence_action"] not in ("ALLOW", "DENY")
