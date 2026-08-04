#!/usr/bin/env python3
"""Torch-free tests for the persistence preregistration. Runnable standalone or via pytest."""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parents[1]
sys.path.insert(0, str(EXP))
import objectives_persistence as OP  # noqa: E402

ARMS = json.loads((EXP / "arm_definitions.json").read_text())
SEEDS = json.loads((EXP / "seed_manifest.json").read_text())
O1R = json.loads((EXP / "o1r_definition.json").read_text())
H1 = json.loads((EXP / "h1_parameter_group_manifest.json").read_text())
H2 = json.loads((EXP / "h2_teacher_definition.json").read_text())
CLS = json.loads((EXP / "classifier.json").read_text())
FROZEN = json.loads((EXP / "frozen_reference_config.json").read_text())


# ---- scope: no training / no results ----
def _exec_mode():
    auth = EXP / "execution_authorization.json"
    if not auth.exists():
        return False
    try:
        return json.loads(auth.read_text()).get("pr_1332_merge_commit") == "101951cb8bbccca32b6e3faa371bc675371dca89"
    except Exception:
        return False


def test_no_training_result_files():
    # preregistration-mode invariant only; execution-authorized mode permits committed evidence
    if _exec_mode():
        return
    sd = EXP / "results" / "seeds"
    assert not (sd.exists() and any(sd.iterdir()))
    for banned in ("aggregate_classification.json", "selection_decision.json"):
        assert not (EXP / "results" / banned).exists()


def test_runner_stub_refuses():
    import runner_stub
    assert runner_stub.main() == 3  # non-zero; nothing runs


def test_no_forbidden_arch_imports():
    for src in ("objectives_persistence.py", "runner_stub.py", "verify_persistence_prereg.py"):
        code = "\n".join(l for l in (EXP / src).read_text().splitlines()
                         if not l.strip().startswith("#") and '"' not in l and "'" not in l)
        for bad in ("import kda", "import mla", "PhaseAttentionLayer", "MultiLatentAttention"):
            assert bad not in code, (src, bad)


# ---- matrix ----
def test_exactly_six_arms_five_seeds_thirty_runs():
    assert ARMS["matrix"]["arms"] == ["A+", "R0", "O1", "O1R", "H1", "H2"]
    assert ARMS["matrix"]["seeds"] == [23, 24, 25, 26, 27]
    assert ARMS["matrix"]["planned_runs"] == 30


def test_aplus_present_and_no_o2_o3_h3_c1():
    assert "A+" in ARMS["arms"]
    assert not ({"O2", "O3", "H3", "C1"} & set(ARMS["arms"].keys()))


# ---- seeds ----
def test_seeds_exact_fresh_no_replacement():
    assert SEEDS["stage_seeds"] == [23, 24, 25, 26, 27]
    used = set(SEEDS["previously_used_bindingslots_training_seeds"])
    assert not (used & set(SEEDS["stage_seeds"]))
    assert "FORBIDDEN" in SEEDS["replacement_policy"]


# ---- O1R ----
def test_o1r_coefficient_and_schedule():
    assert O1R["residual_coefficient"] == 0.01
    assert O1R["residual_start_step"] == 601 and O1R["residual_stop_step"] == 1200
    assert O1R["evaluation_coefficient"] == 0.0
    assert OP.o1r_lambda(0) == 0.10 and OP.o1r_lambda(700) == 0.01 and OP.o1r_lambda(1199) == 0.01
    assert abs(OP.o1r_lambda(450) - 0.05) < 1e-9
    assert "no coefficient sweep on seeds 23-27" in O1R["prohibitions"]


# ---- H1 ----
def test_h1_group_frozen_hash_and_membership():
    assert H1["name_list_sha256"] == hashlib.sha256("\n".join(H1["ordered_names"]).encode()).hexdigest()
    assert H1["lr_multiplier"] == 0.1 and H1["active_step_range"] == [600, 900]
    assert H1["param_count"] == 12 and H1["element_count"] == 73728
    for n in H1["ordered_names"]:
        assert n.endswith(("slot_keys", "W_wk.weight", "W_rq.weight"))
        assert not any(x in n for x in ("W_wv", "gate", "W_o", "norm"))
    assert OP.h1_lr_multiplier(599) == 1.0 and OP.h1_lr_multiplier(600) == 0.1 and OP.h1_lr_multiplier(900) == 1.0


# ---- H2 ----
def test_h2_teacher_frozen_no_labels():
    assert H2["teacher_source_checkpoint"] == 600
    assert H2["evaluation_coefficient"] == 0.0
    assert len(H2["no_answer_label_proof"]) >= 3
    assert OP.h2_coefficient(600) == 0.0 and OP.h2_coefficient(700) == 0.02 and OP.h2_coefficient(1100) == 0.0


# ---- checkpoints ----
def test_checkpoint_cadence_includes_700():
    assert FROZEN["checkpoints"]["full_cadence"] == [0, 60, 120, 300, 600, 700, 900, 1200]
    assert FROZEN["checkpoints"]["added_diagnostic"] == 700


def test_step700_noninterference_report_if_present():
    p = EXP / "results" / "diagnostic_noninterference.json"
    if p.exists():
        r = json.loads(p.read_text())
        assert r["step_700_noninterference_proven"] is True
        assert r["test1_state_invariance"]["pass"] and r["test2_ab_trajectory"]["pass"]


# ---- classifier ----
def test_classifier_frozen_thresholds_same_seed_aplus():
    fc = CLS["frozen_constants"]
    assert fc["FORM_MIN"] == 0.075 and fc["FORM_MARGIN"] == 0.050 and fc["CHANCE"] == 0.02
    rt = CLS["routing_metric_thresholds"]
    assert rt["correct_slot_probability_min"] == 0.50 and rt["correct_slot_median_rank_max"] == 5
    assert rt["correct_slot_address_margin_min"] == 3.0
    assert "SAME-SEED" in CLS["same_seed_aplus_threshold"].upper()
    g = CLS["arm_advancement_gate"]
    assert g["clean_stable_count_ge"] == "4/5" and g["and_clean_stable_gt_R0"] is True


def test_classifier_requires_both_ablations_no_averaging():
    reqs = CLS["CLEAN_STABLE_requires_all_at_step_1200"]
    assert any("slots_off" in r for r in reqs) and any("randomized_address" in r for r in reqs)
    assert "never averaged" in CLS["discipline"]


# ---- schemas ----
def test_all_schemas_present_and_valid():
    for s in ("run_manifest", "seed_manifest", "arm_definition", "checkpoint_metrics",
              "causal_ablation_result", "routing_trajectory", "h1_parameter_group_manifest",
              "h2_teacher_definition", "integrity_report", "aggregate_classification", "selection_decision"):
        p = EXP / "schemas" / f"{s}.schema.json"
        assert p.exists()
        json.loads(p.read_text())


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"persistence tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
