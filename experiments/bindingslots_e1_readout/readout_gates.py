#!/usr/bin/env python3
"""Frozen gate evaluation, conclusion logic, and learned-arm selection for the readout diagnostic.
Torch-free: operates on metric dictionaries; unit-tested; nothing tuned on data."""
from __future__ import annotations

import readout_config as C

SPLIT = {"T1": "T1_unseen_entity", "T2": "T2_unseen_combo", "T3": "T3_temporal_order",
         "T4": "T4_latest", "T6": "T6_paraphrase", "T7": "T7_confusable", "T9": "T9_stable",
         "T8": "T8_no_match"}


def _inherited_pass(cm, G):
    return (cm[SPLIT["T1"]]["addressing_top1"] >= G["T1_min"]
            and cm[SPLIT["T2"]]["addressing_top1"] >= G["T2_min"]
            and cm[SPLIT["T3"]]["addressing_top1"] >= G["T3_min"]
            and cm[SPLIT["T6"]]["addressing_top1"] >= G["T6_min"]
            and cm[SPLIT["T7"]]["addressing_top1"] >= G["T7_min"]
            and cm[SPLIT["T9"]]["addressing_top1"] >= G["T9_min_no_material_regression"])


def _nomatch_pass(cm, G):
    return (cm[SPLIT["T8"]]["false_accept"] <= G["nomatch_max_false_accept"]
            and cm[SPLIT["T3"]]["false_reject"] <= G["nomatch_max_false_reject"])


def _seed_pass(cm, G, t4_min):
    return (cm[SPLIT["T4"]]["correct_latest"] >= t4_min) and _inherited_pass(cm, G) and _nomatch_pass(cm, G)


def eval_arm(arm, seed_metrics, r0_seed_T4, G=C.GATES):
    """seed_metrics: list of {split: metrics} across final seeds. r0_seed_T4: R0's T4 per matching seed.
    Returns the arm's present/partial flags on null-inclusive T4 with the frozen gate numbers."""
    t4s = [cm[SPLIT["T4"]]["correct_latest"] for cm in seed_metrics]
    n = len(t4s)
    mean_T4 = sum(t4s) / n
    worst = min(t4s)
    impr = [t4s[i] - r0_seed_T4[i] for i in range(n)]
    mean_impr = sum(impr) / n
    present_seed_pass = sum(1 for cm in seed_metrics if _seed_pass(cm, G, G["present_mean_T4_min"]))
    partial_seed_pass = sum(1 for cm in seed_metrics if _seed_pass(cm, G, G["partial_mean_T4_min"]))
    present = (present_seed_pass >= G["present_min_seeds"] and mean_T4 >= G["present_mean_T4_min"]
               and mean_impr >= G["present_mean_improvement_over_R0_min"])
    partial = (partial_seed_pass >= G["partial_min_seeds"] and mean_T4 >= G["partial_mean_T4_min"]
               and mean_impr >= G["partial_mean_improvement_over_R0_min"])
    return {"arm": arm, "mean_T4": mean_T4, "worst_seed_T4": worst, "mean_improvement_over_R0": mean_impr,
            "present_seed_pass": present_seed_pass, "partial_seed_pass": partial_seed_pass,
            "present": bool(present), "partial": bool(partial)}


def _select(arm_results, cands, added_params):
    """Mechanical selection among tied learned arms: fewer params -> higher worst-seed T4 -> higher mean."""
    return sorted(cands, key=lambda a: (added_params[a], -arm_results[a]["worst_seed_T4"],
                                        -arm_results[a]["mean_T4"]))[0]


def conclude(arm_results, added_params, integrity_ok, resource_ok=True):
    """Exactly one primary conclusion + selected learned arm + structural-prior-only flag.
    arm_results: {arm: eval_arm(...)} for R0..R3. R3 is never selectable as the primary learned readout;
    R3 alone can only yield SIGNAL_PARTIAL with STRUCTURAL_PRIOR_ONLY_SIGNAL."""
    preserve = list(C.PRESERVE)
    if not resource_ok:
        return {"conclusion": "FROZEN_REPRESENTATION_READOUT_RESOURCE_BLOCKED", "selected_arm": None,
                "structural_prior_only": False, "preserved": preserve}
    if not integrity_ok:
        return {"conclusion": "FROZEN_REPRESENTATION_READOUT_PROTOCOL_VIOLATED", "selected_arm": None,
                "structural_prior_only": False, "preserved": preserve}

    present_learned = [a for a in C.LEARNED_ARMS if arm_results[a]["present"]]
    if present_learned:
        sel = _select(arm_results, present_learned, added_params)
        return {"conclusion": "FROZEN_REPRESENTATION_READOUT_SIGNAL_PRESENT", "selected_arm": sel,
                "structural_prior_only": False, "preserved": preserve}

    partial_learned = [a for a in C.LEARNED_ARMS if arm_results[a]["partial"]]
    if partial_learned:
        sel = _select(arm_results, partial_learned, added_params)
        return {"conclusion": "FROZEN_REPRESENTATION_READOUT_SIGNAL_PARTIAL", "selected_arm": sel,
                "structural_prior_only": False, "preserved": preserve}

    # structural-prior-only: R3 reaches the PRESENT numerical bars while no learned arm reaches partial
    if arm_results[C.STRUCTURAL_ARM]["present"]:
        return {"conclusion": "FROZEN_REPRESENTATION_READOUT_SIGNAL_PARTIAL", "selected_arm": None,
                "structural_prior_only": True, "preserved": preserve}

    return {"conclusion": "FROZEN_REPRESENTATION_READOUT_SIGNAL_NOT_FOUND", "selected_arm": None,
            "structural_prior_only": False, "preserved": preserve}
