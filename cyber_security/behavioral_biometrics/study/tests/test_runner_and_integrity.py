"""End-to-end runner determinism + the EXPLICIT integrity proofs."""

from __future__ import annotations

import copy

import numpy as np

from cyber_security.behavioral_biometrics.study import (
    bcvf, confidence, effects, mockdata, origin, report, runner, use_eval,
)
from cyber_security.behavioral_biometrics.version import (
    ORIGIN_MOCK, ORIGIN_REAL, ORIGIN_SYNTHETIC, REAL_MARKER,
)

CFG = effects.DEFAULT


def _mock(regime="COUPLING_PLUS_MARGINAL_SIGNAL"):
    return mockdata.make_cohort(regime, seed=1)["records"]


def _as_real(records):
    out = copy.deepcopy(records)
    for r in out:
        r["meta"]["data_origin"] = ORIGIN_REAL
        r["meta"]["data_provenance"] = REAL_MARKER
    return out


# ---- runner ----

def test_end_to_end_runs_and_locks():
    rep = runner.run_study(_mock(), cfg=CFG, iters=200,
                           temporal_fixture=mockdata.make_temporal("ABRUPT_TAKEOVER", seed=1))
    assert rep["origin_banner"] == origin.BANNER
    for k, v in rep["mechanical_verdicts"].items():
        assert v not in origin.POSITIVE_SCIENTIFIC


def test_report_has_all_sections():
    rep = runner.run_study(_mock(), cfg=CFG, iters=150)
    for sec in ("dataset_eligibility", "marginal_identity", "multimodal_fusion",
                "coupling_use", "bcvf", "confidence_calibration", "confound_artifact_gates",
                "mechanical_verdicts", "limitations", "origin_banner"):
        assert sec in rep


def test_report_deterministic():
    r1 = runner.run_study(_mock(), cfg=CFG, iters=200)
    r2 = runner.run_study(_mock(), cfg=CFG, iters=200)
    assert r1["mechanical_verdicts"] == r2["mechanical_verdicts"]
    assert r1["coupling_use"]["analysis"]["gain_context_vs_marginal"] == \
           r2["coupling_use"]["analysis"]["gain_context_vs_marginal"]


def test_leakage_free_split_in_runner():
    rep = runner.run_study(_mock(), cfg=CFG, iters=100)
    assert rep["leakage_check"] == []


# ---- INTEGRITY PROOFS (explicitly required) ----

def test_mock_data_cannot_emit_positive_scientific_verdict():
    recs = _mock()
    v = use_eval.use_verdict(recs, cfg=CFG, iters=200)
    assert v["verdict"] not in origin.POSITIVE_SCIENTIFIC
    assert v["scientific"] is False
    assert v["verdict"] == use_eval.USE_PATH_VERIFIED


def test_synthetic_data_cannot_emit_positive_scientific_verdict():
    recs = _mock()
    for r in recs:
        r["meta"]["data_origin"] = ORIGIN_SYNTHETIC
    v = use_eval.use_verdict(recs, cfg=CFG, iters=200)
    assert v["scientific"] is False
    assert v["verdict"] not in origin.POSITIVE_SCIENTIFIC


def test_only_eligible_real_data_reaches_positive_verdict_path():
    real = _as_real(mockdata.make_cohort("COUPLING_ONLY_SIGNAL", seed=1)["records"])
    v = use_eval.use_verdict(real, cfg=CFG, iters=300)
    # real origin -> the scientific classifier runs (may be SUPPORTED here)
    assert v["scientific"] is True
    assert v["verdict"] in (use_eval.USER_SPECIFIC_COUPLING_SUPPORTED,
                            use_eval.USER_SPECIFIC_COUPLING_SMALL_EFFECT,
                            use_eval.HUMANNESS_SIGNAL_ONLY,
                            use_eval.SAMPLING_OR_CONTEXT_ARTIFACT,
                            use_eval.DEVICE_BOUND_COUPLING_ONLY,
                            use_eval.COUPLING_NOT_SUPPORTED)


def test_same_data_mock_vs_real_diverge_only_by_origin():
    mock = mockdata.make_cohort("COUPLING_ONLY_SIGNAL", seed=1)["records"]
    real = _as_real(mock)
    vm = use_eval.use_verdict(mock, cfg=CFG, iters=300)
    vr = use_eval.use_verdict(real, cfg=CFG, iters=300)
    assert vm["verdict"] == use_eval.USE_PATH_VERIFIED and not vm["scientific"]
    assert vr["scientific"] is True


def test_bcvf_cannot_run_without_two_qualifying_estimators():
    d = mockdata.make_bcvf("BCVF_HELPFUL", seed=1, n=400)
    rows = dict(d["rows"]); rows["z2"] = np.zeros(len(rows["z2"])).tolist()
    r = bcvf.evaluate_bcvf(rows, cfg=CFG, iters=150)
    assert not r["eligible"] and bcvf.classify_bcvf(r, CFG) == bcvf.BCVF_NOT_ELIGIBLE


def test_use_cannot_be_credited_for_extra_modalities():
    recs = mockdata.make_cohort("MULTIMODAL_MARGINAL_SIGNAL", seed=1)["records"]  # no coupling
    u = use_eval.run_use(recs, cfg=CFG, iters=300)
    assert use_eval.classify_use(u, CFG) != use_eval.USER_SPECIFIC_COUPLING_SUPPORTED


def test_confidence_not_calibrated_without_held_out_eval():
    d = mockdata.make_confidence("CONFIDENCE_MISCALIBRATED", seed=1)
    r = confidence.calibrate_and_evaluate(d["rows"]["scores"], d["rows"]["labels"], cfg=CFG)
    assert r["n_test"] > 0                       # held-out test set was used
    assert confidence.classify_confidence(r, CFG) != confidence.CONFIDENCE_CALIBRATED


def test_positive_verdict_tripwire():
    recs = _mock()
    try:
        origin.assert_not_positive_on_nonreal(recs, "MARGINAL_SIGNAL_SUPPORTED")
        assert False, "tripwire did not fire"
    except AssertionError as e:
        assert "illegal positive" in str(e)


def test_no_participant_or_device_ids_in_any_arm_feature():
    from cyber_security.behavioral_biometrics.study import arms
    recs = mockdata.make_cohort("MULTIMODAL_MARGINAL_SIGNAL", seed=1)["records"]
    for arm in ("K", "P", "MM", "MM_COUPLING", "MM_COUPLING_CONTEXT"):
        feats = arms.builder_for(arm)(recs[0])
        for k in feats:
            assert "participant" not in k and "device" not in k and "session" not in k
