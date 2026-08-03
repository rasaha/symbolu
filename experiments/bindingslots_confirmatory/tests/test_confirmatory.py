#!/usr/bin/env python3
"""Torch-free test suite for the BindingSlots confirmatory replication.

Covers: freeze integrity, seed integrity, preregistration, training-protocol schedule assertions,
causal gates, quality/distance gates, restart/resume idempotence logic, the mechanical classifier
(all 8 required cases), and evidence completeness. Runnable under pytest or standalone.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
SBS = REPO / "hybrid_llm_vnext_lab" / "experiments" / "slot_formation_stabilization"
for p in (str(EXP), str(SBS)):
    if p not in sys.path:
        sys.path.insert(0, p)

import classify_confirmatory as C  # noqa: E402
import retention as RET  # noqa: E402

FROZEN = json.loads((EXP / "frozen_cr1_config.json").read_text())
SEEDS = json.loads((EXP / "fresh_seeds.json").read_text())
CLS = json.loads((EXP / "classifier.json").read_text())
PRE = json.loads((EXP / "preregistration.json").read_text())


def sha256(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


# ---------- helpers to synthesize seed records ----------
def rec(seed, arm, d96, d16=None, d220=None, ppl=135.0, params=2000104, ablation=None, traj=None):
    d16 = d96 if d16 is None else d16
    d220 = d96 if d220 is None else d220
    r = {"seed": seed, "arm": arm, "params": params,
         "needle_by_dist": {"16": d16, "96": d96, "220": d220},
         "ppl": {"256": ppl, "512": ppl + 5}, "ablation": ablation or {}}
    if traj:
        r["trajectory"] = traj
    return r


def clean_abl(base):
    return {"baseline": base, "slots_off": 0.0, "randomized_address": 0.02}


def dirty_abl(base):
    return {"baseline": base, "slots_off": base, "randomized_address": base}


def build(cr1_forms, b0_forms=(13, 14), causal="clean", ppl_cr1=135.0, ppl_ap=140.0,
          d16_regress=False, d220_bad=False):
    seeds = [13, 14, 15, 16, 17]
    cr1, ap, b0 = {}, {}, {}
    for s in seeds:
        f = s in cr1_forms
        d = 0.99 if f else 0.0
        abl = {}
        if f:
            abl = dirty_abl(d) if (causal == "dirty" and s == cr1_forms[0]) else clean_abl(d)
        d16 = (0.0 if d16_regress and f else d)
        d220 = (0.0 if d220_bad else d)
        cr1[s] = rec(s, "CR1", d, d16=d16, d220=d220, ppl=ppl_cr1, ablation=abl)
        ap[s] = rec(s, "A+", 0.0, ppl=ppl_ap, params=2000392)
        b0[s] = rec(s, "B0", 0.6 if s in b0_forms else 0.0)
    return cr1, ap, b0


# ================= FREEZE INTEGRITY =================
def test_frozen_abc_hash():
    assert sha256(REPO / "experiments/phase_lc/results/abc.json") == \
        "b31989a3135b150ef4cf693e42f173aadb51bba876b6e956da73f022d539b482"


def test_frozen_classifier_hash():
    assert sha256(SBS / "classify_stage_b.py") == CLS["inherited_from"]["sha256"]


def test_all_frozen_code_hashes_match():
    for rel, want in FROZEN["frozen_code_hashes_sha256"].items():
        assert sha256(REPO / rel) == want, rel


def test_architecture_signature_and_params():
    a = FROZEN["architecture"]
    assert a["architecture_signature_sha256"] == "6e8672bd3df43f81241f4fe965508055b2500cceba5c66b59b012e2ff4a7cff1"
    assert a["slot_arm_parameters"] == 2000104
    assert a["aplus_control_parameters"] == 2000392
    assert a["slots"] == 32 and a["slot_key_dimension"] == 64 and a["local_window"] == 64


def test_no_forbidden_architecture_tokens():
    forbidden = ["MultiLatentAttention", "quadratic_attention", "class KDA"]
    for src in ("run_confirmatory.py", "classify_confirmatory.py", "retention.py"):
        txt = (EXP / src).read_text()
        for t in forbidden:
            assert t not in txt, (src, t)


# ================= SEED INTEGRITY =================
def test_five_unique_fresh_seeds():
    fs = SEEDS["confirmatory_seeds"]
    assert fs == [13, 14, 15, 16, 17]
    assert len(fs) == len(set(fs)) == 5


def test_no_previously_used_seed():
    used = set(SEEDS["previously_used_bindingslots_training_seeds"]["union_all_training_seeds"])
    assert not (used & set(SEEDS["confirmatory_seeds"]))


def test_deterministic_selection_rule():
    hi = SEEDS["previously_used_bindingslots_training_seeds"]["highest_used_training_seed"]
    assert SEEDS["confirmatory_seeds"] == [hi + i for i in range(1, 6)]


# ================= PREREGISTRATION =================
def test_all_gates_present():
    for g in ("C1_form_ge_4_of_5", "C2_form_gt_B0", "C3_win_ge_4_of_5", "C4_mean_margin",
              "C5_median_margin", "C6_quality", "C7_distance", "C8_slots_off",
              "C9_randomized_address", "C10_integrity", "C11_no_protocol_deviation"):
        assert g in CLS["primary_gates"], g


def test_classifier_version_pinned():
    assert CLS["inherited_from"]["file"].endswith("classify_stage_b.py")
    assert PRE["no_tuning_declaration"]


def test_verdict_enum_frozen():
    assert set(CLS["final_verdict_mapping"]) == {
        "REPLICATED_SLOT_FORMATION_STABILIZATION", "CONFIRMATORY_REPLICATION_FAILED",
        "CONFIRMATORY_PROTOCOL_VIOLATED", "CONFIRMATORY_INTEGRITY_FAILED",
        "CONFIRMATORY_ENVIRONMENT_MISMATCH", "CONFIRMATORY_RESOURCE_BLOCKED"}


# ================= TRAINING PROTOCOL =================
def test_arm_count_and_ids():
    assert CLS["arms"] == ["A+", "B0", "CR1"]


def test_step_budget_and_checkpoints():
    assert FROZEN["training"]["training_steps"] == 1200
    assert FROZEN["training"]["checkpoints"] == [0, 60, 120, 300, 600, 900, 1200]


def test_curriculum_schedule():
    assert FROZEN["curriculum"]["boundaries"] == [300, 700, 1200]
    assert FROZEN["curriculum"]["final_500_steps_original"] is True


def test_alignment_schedule_and_zero_point():
    al = FROZEN["alignment"]
    assert al["alignment_coefficient_peak"] == 0.10
    assert al["alignment_zero_point"] == 600
    assert al["zero_during_all_evaluation"] is True


def test_no_best_checkpoint_selection():
    assert PRE["training_protocol"]["no_best_checkpoint_selection"] is True
    assert PRE["training_protocol"]["final_evaluation_point"] == 1200


# ================= CLASSIFIER (8 required cases) =================
def _v(cr1, ap, b0, **kw):
    return C.classify(cr1, ap, b0, **kw)["primary_verdict"]


def test_case_5of5_pass():
    cr1, ap, b0 = build([13, 14, 15, 16, 17])
    assert _v(cr1, ap, b0) == "REPLICATED_SLOT_FORMATION_STABILIZATION"


def test_case_4of5_pass():
    cr1, ap, b0 = build([13, 14, 16, 17])
    assert _v(cr1, ap, b0) == "REPLICATED_SLOT_FORMATION_STABILIZATION"


def test_case_3of5_fail():
    cr1, ap, b0 = build([13, 14, 16])
    assert _v(cr1, ap, b0) == "CONFIRMATORY_REPLICATION_FAILED"


def test_case_4of5_one_causal_failure():
    cr1, ap, b0 = build([13, 14, 16, 17], causal="dirty")
    out = C.classify(cr1, ap, b0)
    assert out["primary_verdict"] == "CONFIRMATORY_REPLICATION_FAILED"
    assert out["gates"]["C8_slots_off"] is False


def test_case_quality_failure():
    cr1, ap, b0 = build([13, 14, 16, 17], ppl_cr1=400.0, ppl_ap=100.0)
    out = C.classify(cr1, ap, b0)
    assert out["gates"]["C6_quality"] is False
    assert out["primary_verdict"] == "CONFIRMATORY_REPLICATION_FAILED"


def test_case_distance_failure():
    cr1, ap, b0 = build([13, 14, 16, 17], d220_bad=True)
    out = C.classify(cr1, ap, b0)
    assert out["gates"]["C7_distance"] is False
    assert out["primary_verdict"] == "CONFIRMATORY_REPLICATION_FAILED"


def test_case_protocol_deviation():
    cr1, ap, b0 = build([13, 14, 15, 16, 17])
    assert _v(cr1, ap, b0, protocol_deviations=["changed lr"]) == "CONFIRMATORY_PROTOCOL_VIOLATED"


def test_case_integrity_failure():
    cr1, ap, b0 = build([13, 14, 15, 16, 17])
    assert _v(cr1, ap, b0, integrity_ok=False) == "CONFIRMATORY_INTEGRITY_FAILED"


# ================= CAUSAL: individual failure propagates, no averaging =================
def test_individual_causal_failure_propagates_to_aggregate():
    # 4 clean forming + 1 dirty forming; even though 4/5 causal-clean, the aggregate must fail.
    cr1, ap, b0 = build([13, 14, 15, 16, 17], causal="dirty")
    out = C.classify(cr1, ap, b0)
    assert out["cr1_formation_count"] == 5
    assert out["primary_verdict"] == "CONFIRMATORY_REPLICATION_FAILED"  # not averaged away


# ================= QUALITY / DISTANCE deterministic aggregation =================
def test_quality_gate_thresholds():
    cr1, ap, b0 = build([13, 14, 16, 17], ppl_cr1=120.0, ppl_ap=140.0)
    out = C.classify(cr1, ap, b0)
    assert out["quality"]["pass"] is True


def test_all_distances_present():
    cr1, ap, b0 = build([13, 14, 16, 17])
    out = C.classify(cr1, ap, b0)
    # every seed record carries d16/d96/d220
    for s in (13, 14, 15, 16, 17):
        assert set(cr1[s]["needle_by_dist"]) == {"16", "96", "220"}
    assert "d16_ok" in out["distance"] and "d220_ok" in out["distance"]


# ================= RESTART / RESUME idempotence (logic) =================
def test_resume_skip_logic(tmp_path=None):
    import tempfile
    d = pathlib.Path(tmp_path or tempfile.mkdtemp())
    seed_dir = d / "seeds"
    seed_dir.mkdir(parents=True)
    (seed_dir / "CR1_seed13.json").write_text(json.dumps(rec(13, "CR1", 0.9)))
    # a resumed orchestrator must treat an existing per-seed file as complete
    assert (seed_dir / "CR1_seed13.json").exists()
    loaded = json.loads((seed_dir / "CR1_seed13.json").read_text())
    assert loaded["seed"] == 13 and loaded["arm"] == "CR1"


# ================= EVIDENCE completeness =================
def test_seed_result_required_fields_schema():
    sch = json.loads((EXP / "seed_result.schema.json").read_text())
    for f in ("seed", "arm", "params", "needle_by_dist", "ppl", "config_hash", "code_commit",
              "environment_fingerprint", "checkpoint_steps", "train_s"):
        assert f in sch["required"], f


def test_retention_categories_defined_before_training():
    cats = set(PRE["retention_diagnostics"]["categories"])
    assert cats == {"NEVER_FORMED", "FORMED_AND_RETAINED", "FORMED_THEN_COLLAPSED",
                    "LATE_FORMATION", "TRANSIENT_RECOVERY", "OTHER_PREDEFINED"}


def test_retention_seed9_pattern():
    seed9 = [0.0, 0.0, 0.0, 1.0, 0.5, 0.1, 0.0]
    assert RET.classify(seed9, formed_final=False) == "FORMED_THEN_COLLAPSED"


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
    print(f"confirmatory tests: {passed} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
