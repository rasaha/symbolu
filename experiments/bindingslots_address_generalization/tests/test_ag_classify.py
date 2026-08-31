#!/usr/bin/env python3
"""Torch-free tests: query-template separation, seed allocation, futility, mechanism gates, AG gating,
verdict logic. Standalone or pytest."""
from __future__ import annotations

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
EXP = HERE.parent
sys.path.insert(0, str(EXP))
import ag_classify as AC  # noqa: E402


def test_held_out_template_separation():
    from ag_meta import QUERY_TEMPLATES
    train = set(map(tuple, QUERY_TEMPLATES["train"]))
    dev = set(map(tuple, QUERY_TEMPLATES["dev"]))
    test = set(map(tuple, QUERY_TEMPLATES["test"]))
    assert test.isdisjoint(train), "eval/test template leaked into train"
    assert test.isdisjoint(dev)
    assert train.isdisjoint(dev)
    # the held-out test template is the frozen needle-eval query framing
    assert ("the", "code", "for", "ENT", "is") in test


def test_seed_allocation():
    reg = json.loads((EXP / "seed_registry.json").read_text())
    assert reg["phase_seeds"] == [28, 29, 30, 31, 32]
    used = set(reg["previously_used_bindingslots_training_seeds"])
    assert not (set(reg["phase_seeds"]) & used)
    assert all(s > 27 for s in reg["phase_seeds"])


def _row(qq, cs, prob_d=0.2, top1_d=0.2, approach=True, wak=-0.01, b0wak=-0.2,
         needle_ni=True, prob_ni=True, other=None, gneg=3):
    return {"quality_qualified": qq, "clean_stable": cs, "prob_delta_vs_b0": prob_d,
            "top1_delta_vs_b0": top1_d, "approaches_oracle": approach,
            "wak_cos_teacher_window": wak, "b0_wak_cos_teacher_window": b0wak,
            "needle_noninf_vs_b0": needle_ni, "prob_noninf_vs_b0": prob_ni,
            "other_group_min_cos": other or {"backbone": 0.01, "embeddings": -0.01},
            "g1_negative_cosine_updates": gneg, "seed": 0, "arm": "X"}


def test_a1_gate_passes_when_all_conditions_met():
    rows = [_row(True, True) for _ in range(5)]
    ok, conds = AC.a1_gate(rows, leakage_ok=True)
    assert ok and all(conds.values())


def test_a1_gate_fails_on_leakage():
    rows = [_row(True, True) for _ in range(5)]
    ok, conds = AC.a1_gate(rows, leakage_ok=False)
    assert not ok and conds["no_template_leakage"] is False


def test_a1_gate_fails_without_eval_improvement():
    rows = [_row(True, True, prob_d=0.0, top1_d=0.0) for _ in range(5)]  # probe may move but eval flat
    ok, conds = AC.a1_gate(rows, leakage_ok=True)
    assert not ok and not conds["eval_routing_materially_improves_ge_4of5"]


def test_g1_gate_passes():
    rows = [_row(True, True, wak=-0.01, b0wak=-0.2) for _ in range(5)]
    ok, conds = AC.g1_gate(rows)
    assert ok and all(conds.values())


def test_g1_gate_fails_on_new_conflict_in_other_group():
    rows = [_row(True, True, other={"backbone": -0.3}) for _ in range(5)]
    ok, conds = AC.g1_gate(rows)
    assert not ok and not conds["no_new_conflict_other_group_ge_4of5"]


def test_g1_conflict_reduction_by_fraction():
    # cos still negative (-0.09) but |cos| reduced >50% vs b0 (-0.2) -> counts as reduced
    rows = [_row(True, True, wak=-0.09, b0wak=-0.2) for _ in range(5)]
    ok, conds = AC.g1_gate(rows)
    assert conds["conflict_reduced_ge_4of5"]


def test_futility_second_failure_stops_arm():
    rows2 = [_row(False, False), _row(False, False)]   # 2 failures -> max clean 3 < 4
    assert AC.arm_futile(rows2)
    rows1 = [_row(False, False), _row(True, True)]      # 1 failure -> still possible
    assert not AC.arm_futile(rows1)


def test_verdict_matrix():
    assert AC.verdict(True, True, True, True) == "JOINT_BINDINGSLOTS_INTERVENTION_CANDIDATE_SELECTED"
    assert AC.verdict(True, True, False, False) == "BOTH_COMPONENTS_PASS_JOINT_ARM_NOT_RUN"
    assert AC.verdict(True, True, True, False) == "BINDINGSLOTS_INTERVENTION_RESULTS_INCONCLUSIVE"
    assert AC.verdict(True, False, False, False) == "READ_ADDRESS_GENERALIZATION_CANDIDATE_SELECTED"
    assert AC.verdict(False, True, False, False) == "ROUTING_GRADIENT_ISOLATION_CANDIDATE_SELECTED"
    assert AC.verdict(False, False, False, False) == "NO_BINDINGSLOTS_INTERVENTION_SELECTED"


def test_ag_blocked_unless_both_pass():
    # AG must not run unless both a1 and g1 pass — enforced by driver; verdict never selects joint
    # without ag_ran. Here assert the guard semantics at the verdict layer.
    assert AC.verdict(True, False, False, False) != "JOINT_BINDINGSLOTS_INTERVENTION_CANDIDATE_SELECTED"
    assert AC.verdict(False, True, False, False) != "JOINT_BINDINGSLOTS_INTERVENTION_CANDIDATE_SELECTED"


def _run_standalone():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"ag-classify tests: {len(fns)} passed, 0 failed")
    return 0


if __name__ == "__main__":
    raise SystemExit(_run_standalone())
