"""Executable demonstrations (18) of the study machinery. Run:

    python -m cyber_security.behavioral_biometrics.study.demos.demo

Every demonstration exercises SOFTWARE PATHS ONLY on MOCK_TEST_ONLY fixtures and emits
no scientific/biometric claim (verdicts are *_PATH_VERIFIED / *_NO_SCIENTIFIC_VERDICT).
"""

from __future__ import annotations

import json
import warnings
from typing import Any, Dict, List

warnings.filterwarnings("ignore")

from cyber_security.behavioral_biometrics import splits
from cyber_security.behavioral_biometrics.study import (
    bcvf, confidence, effects, evidence, fusion, identity, mockdata, origin,
    runner, temporal, use_eval,
)

CFG = effects.DEFAULT
IT = 300
NOTE = "software path only — MOCK_TEST_ONLY, no biometric claim"


def _auc(recs, arm):
    plan = splits.session_disjoint(recs, seed=1)
    r = identity.run_arm(recs, plan, arm, cfg=CFG)
    return round(r["metrics"]["auc"], 3) if r.get("usable") else None


def d01_no_signal():
    r = mockdata.make_cohort("NO_SIGNAL", seed=1)["records"]
    return {"demo": "01_no_signal_identity", "MM_auc": _auc(r, "MM"), "note": NOTE}


def d02_keyboard_only():
    r = mockdata.make_cohort("KEYBOARD_ONLY_SIGNAL", seed=1)["records"]
    return {"demo": "02_keyboard_only", "K_auc": _auc(r, "K"), "P_auc": _auc(r, "P"), "note": NOTE}


def d03_multimodal_fusion():
    r = mockdata.make_fusion("FUSION_HELPFUL", seed=1)
    res = fusion.evaluate_fusion(r["rows"], cfg=CFG, iters=IT)
    return {"demo": "03_multimodal_fusion_improvement", "best_single": round(res["best_single_auc"], 3),
            "best_fusion": round(res["best_fusion_auc"], 3), "path_branch": fusion.classify_fusion(res, CFG),
            "note": NOTE}


def d04_coupling_only():
    r = mockdata.make_cohort("COUPLING_ONLY_SIGNAL", seed=1)["records"]
    u = use_eval.run_use(r, cfg=CFG, iters=IT)
    return {"demo": "04_coupling_only", "MM_auc": round(u["arm_auc"]["MM"], 3),
            "MM_COUPLING_CONTEXT_auc": round(u["arm_auc"]["MM_COUPLING_CONTEXT"], 3),
            "path_branch": use_eval.classify_use(u, CFG), "note": NOTE}


def d05_shuffled_control():
    r = mockdata.make_cohort("SAMPLING_ARTIFACT", seed=1)["records"]
    u = use_eval.run_use(r, cfg=CFG, iters=IT)
    return {"demo": "05_shuffled_coupling_control",
            "ctx_vs_shuffled_lo": round(u["gain_context_vs_shuffled"]["lo"], 3),
            "path_branch": use_eval.classify_use(u, CFG), "note": NOTE}


def d06_device_confound():
    r = mockdata.make_cohort("DEVICE_CONFOUND", seed=1)["records"]
    same = _auc(r, "MM")
    dev = splits.device_instance(r)
    cross = identity.run_arm(r, dev, "MM", cfg=CFG) if dev.enroll else {"usable": False}
    return {"demo": "06_device_confound", "same_device_MM_auc": same,
            "cross_device_MM_auc": round(cross["metrics"]["auc"], 3) if cross.get("usable") else None,
            "note": NOTE}


def d07_task_confound():
    r = mockdata.make_cohort("TASK_CONFOUND", seed=1)["records"]
    same = _auc(r, "MM")
    tp = splits.task_disjoint(r)
    cross = identity.run_arm(r, tp, "MM", cfg=CFG) if tp.enroll else {"usable": False}
    return {"demo": "07_task_confound", "same_task_MM_auc": same,
            "task_disjoint_MM_auc": round(cross["metrics"]["auc"], 3) if cross.get("usable") else None,
            "note": NOTE}


def _bcvf_demo(regime, n):
    fx = mockdata.make_bcvf(regime, seed=1, n=500)
    r = bcvf.evaluate_bcvf(fx["rows"], cfg=CFG, iters=IT)
    return {"demo": n, "auc_no_disagreement": round(r["auc_no_disagreement"], 3),
            "auc_bcvf": round(r["auc_bcvf"], 3), "gain_lo": round(r["gain"]["lo"], 3),
            "path_branch": bcvf.classify_bcvf(r, CFG), "note": NOTE}


def d08_bcvf_helpful(): return _bcvf_demo("BCVF_HELPFUL", "08_bcvf_helpful")
def d09_bcvf_redundant(): return _bcvf_demo("BCVF_REDUNDANT", "09_bcvf_redundant")
def d10_bcvf_harmful(): return _bcvf_demo("BCVF_HARMFUL", "10_bcvf_harmful")


def _conf_demo(regime, n):
    fx = mockdata.make_confidence(regime, seed=1)
    r = confidence.calibrate_and_evaluate(fx["rows"]["scores"], fx["rows"]["labels"], cfg=CFG)
    return {"demo": n, "held_out_ece": round(r["ece"], 3), "raw_ece": round(r["raw_ece"], 3),
            "path_branch": confidence.classify_confidence(r, CFG), "note": NOTE}


def d11_conf_calibrated(): return _conf_demo("CONFIDENCE_WELL_CALIBRATED", "11_confidence_well_calibrated")
def d12_conf_miscalibrated(): return _conf_demo("CONFIDENCE_MISCALIBRATED", "12_confidence_miscalibrated")


def _temporal_demo(regime, n):
    fx = mockdata.make_temporal(regime, seed=1)
    r = temporal.evaluate_stream(fx)
    c = r["arms"]["cusum"]
    return {"demo": n, "detected": c["detected"], "time_to_detection_steps": c["time_to_detection_steps"],
            "false_challenges": c["false_challenges"], "note": NOTE}


def d13_abrupt(): return _temporal_demo("ABRUPT_TAKEOVER", "13_abrupt_takeover")
def d14_slow(): return _temporal_demo("SLOW_TAKEOVER", "14_slow_takeover")


def d15_missing_modality():
    ch = {"identity": {"value": 0.8, "quality": 0.9, "present": True},
          "pointer": {"present": False}, "device_trust": {"value": 0.9, "present": True}}
    fused = fusion.fuse_channels(ch, hard_gates={})
    return {"demo": "15_missing_modality_fallback", "n_present": fused["n_present"],
            "sufficiency": round(fused["sufficiency"], 3), "conservative": fused["conservative"],
            "note": NOTE}


def d16_end_to_end():
    r = mockdata.make_cohort("COUPLING_PLUS_MARGINAL_SIGNAL", seed=1)["records"]
    rep = runner.run_study(r, cfg=CFG, iters=IT,
                           temporal_fixture=mockdata.make_temporal("ABRUPT_TAKEOVER", seed=1))
    return {"demo": "16_end_to_end_mock_study", "origin_banner": rep["origin_banner"],
            "mechanical_verdicts": rep["mechanical_verdicts"], "note": NOTE}


def d17_evidence_export():
    conf = confidence.build_confidence(identity_probability=0.82,
                                       calibration_status=confidence.CONFIDENCE_CALIBRATED,
                                       uncertainty=0.25, quality=0.9, evidence_sufficiency=0.7)
    exp = evidence.build(session_id="mock_s", timestamp="2026-01-01T00:00:00",
                         confidence_output=conf, modality_quality={"kbd": 0.9, "ptr": 0.85},
                         data_origin="MOCK_TEST_ONLY").to_dict()
    return {"demo": "17_evidence_export", "validation_problems": evidence.validate(exp),
            "recommended_evidence_action": exp["recommended_evidence_action"],
            "contains_authorization_decision": False, "note": NOTE}


def d18_no_claim_lock():
    r = mockdata.make_cohort("MULTIMODAL_MARGINAL_SIGNAL", seed=1)["records"]
    lock = origin.claim_lock(r)
    # prove a positive scientific verdict is impossible on this data
    guarded = origin.guarded(r, scientific=lambda: "MARGINAL_SIGNAL_SUPPORTED",
                             path_verified="PATH_VERIFIED")
    return {"demo": "18_no_claim_lock_on_mock", "locked": lock["locked"], "banner": lock["banner"],
            "guarded_verdict": guarded["verdict"], "scientific": guarded["scientific"], "note": NOTE}


DEMOS = [d01_no_signal, d02_keyboard_only, d03_multimodal_fusion, d04_coupling_only,
         d05_shuffled_control, d06_device_confound, d07_task_confound, d08_bcvf_helpful,
         d09_bcvf_redundant, d10_bcvf_harmful, d11_conf_calibrated, d12_conf_miscalibrated,
         d13_abrupt, d14_slow, d15_missing_modality, d16_end_to_end, d17_evidence_export,
         d18_no_claim_lock]


def main() -> int:
    print(json.dumps([fn() for fn in DEMOS], indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
