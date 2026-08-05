#!/usr/bin/env python3
"""Frozen gate evaluation, 2^3 factorial analysis, mechanical selection rule, and verdict. Torch-free:
operates purely on metric dictionaries so it runs in CI and is unit-tested. Nothing here is tuned on data.
"""
from __future__ import annotations

import factor_config as C

SPLIT = {"T1": "T1_unseen_entity", "T2": "T2_unseen_combo", "T3": "T3_temporal_order",
         "T4": "T4_latest", "T6": "T6_paraphrase", "T7": "T7_confusable", "T9": "T9_stable",
         "T8": "T8_no_match"}


def per_seed_gates(cm, G=C.GATES):
    """cm: {split_name: metrics}. Returns per-primary-gate booleans + all_primary_pass.
    T4 gates on null-inclusive correct_latest; inherited splits gate on null-excluded addressing_top1."""
    g = {
        "T4": cm[SPLIT["T4"]]["correct_latest"] >= G["T4_min"],
        "T1": cm[SPLIT["T1"]]["addressing_top1"] >= G["T1_min"],
        "T2": cm[SPLIT["T2"]]["addressing_top1"] >= G["T2_min"],
        "T3": cm[SPLIT["T3"]]["addressing_top1"] >= G["T3_min"],
        "T6": cm[SPLIT["T6"]]["addressing_top1"] >= G["T6_min"],
        "T7": cm[SPLIT["T7"]]["addressing_top1"] >= G["T7_min"],
        "T9": cm[SPLIT["T9"]]["addressing_top1"] >= G["T9_min_no_material_regression"],
        "nomatch_false_accept": cm[SPLIT["T8"]]["false_accept"] <= G["nomatch_max_false_accept"],
        "nomatch_false_reject": cm[SPLIT["T3"]]["false_reject"] <= G["nomatch_max_false_reject"],
    }
    g["all_primary_pass"] = all(g.values())
    return g


def cell_seed_T4(cm):
    return cm[SPLIT["T4"]]["correct_latest"]


def cell_qualification(cell, seed_metrics, ref_mean_T4, added_params, G=C.GATES):
    """seed_metrics: list of {split: metrics} for this cell across final seeds. ref_mean_T4: cell-000 mean.
    A cell qualifies if >= required seeds pass ALL primary gates AND mean T4 improvement over cell 000
    >= the given absolute margin. (Cell 000 never improves over itself, so it cannot be an intervention.)
    'No material regression in ordinary semantic retrieval' is enforced by the inherited T1/T2/T3 (and
    T6/T7/T9) gates being part of all_primary_pass on >= required seeds."""
    gates = [per_seed_gates(cm, G) for cm in seed_metrics]
    n_pass = sum(1 for x in gates if x["all_primary_pass"])
    t4s = [cell_seed_T4(cm) for cm in seed_metrics]
    mean_T4 = sum(t4s) / len(t4s)
    worst_T4 = min(t4s)
    improvement = mean_T4 - ref_mean_T4
    n_factors = sum(1 for ch in cell if ch == "1")
    is_reference = (cell == C.REFERENCE_CELL)
    qualifies = (not is_reference) and (n_pass >= G["required_seeds_pass"]) and \
                (improvement >= G["T4_improvement_over_000_min"])
    return {"cell": cell, "n_factors": n_factors, "added_params": added_params,
            "seeds_passing_all_primary": n_pass, "required": G["required_seeds_pass"],
            "mean_T4": mean_T4, "worst_seed_T4": worst_T4, "improvement_over_000": improvement,
            "per_seed_gates": gates, "qualifies": bool(qualifies), "is_reference": is_reference}


# ---- 2^3 factorial effects (Yates ±1 contrasts; effect = Σ contrast·y / 4) --------------
def _bits(cell):
    return [1 if ch == "1" else -1 for ch in cell]   # [F1,F2,F3] in {-1,+1}


def factorial_effects(cell_mean_T4):
    """cell_mean_T4: {code: mean_T4} for all 8 cells. Returns main effects + all interactions on T4."""
    codes = list(cell_mean_T4.keys())
    terms = {"F1": (0,), "F2": (1,), "F3": (2,), "F1xF2": (0, 1), "F1xF3": (0, 2),
             "F2xF3": (1, 2), "F1xF2xF3": (0, 1, 2)}
    eff = {}
    for name, idxs in terms.items():
        s = 0.0
        for code in codes:
            b = _bits(code)
            contrast = 1
            for i in idxs:
                contrast *= b[i]
            s += contrast * cell_mean_T4[code]
        eff[name] = s / 4.0
    return eff


def select_cell(qualifications):
    """Mechanical selection among qualifying cells:
       1) fewest enabled factors  2) lowest added params  3) highest worst-seed T4  4) highest mean T4."""
    q = [x for x in qualifications if x["qualifies"]]
    if not q:
        return None
    q.sort(key=lambda x: (x["n_factors"], x["added_params"], -x["worst_seed_T4"], -x["mean_T4"]))
    return q[0]


def verdict(selected, determinism_ok, leakage_ok, protocol_ok, resource_ok=True):
    """One primary verdict. Always co-emits the three preserved invariants; never a transfer-validation or
    KDA-unblocking verdict."""
    preserve = list(C.PRESERVE)
    if not resource_ok:
        return "T4_FACTORIAL_RESOURCE_BLOCKED", None, preserve
    if not (determinism_ok and leakage_ok and protocol_ok):
        return "T4_FACTORIAL_PROTOCOL_VIOLATED", None, preserve
    if selected is None:
        return "T4_FACTORIAL_NO_INTERVENTION_SELECTED", None, preserve
    nf = selected["n_factors"]
    v = {1: "T4_FACTORIAL_SINGLE_FACTOR_SELECTED",
         2: "T4_FACTORIAL_COMBINATION_SELECTED",
         3: "T4_FACTORIAL_ALL_FACTORS_REQUIRED"}[nf]
    return v, selected["cell"], preserve
