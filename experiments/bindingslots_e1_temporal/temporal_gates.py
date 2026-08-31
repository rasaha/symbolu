#!/usr/bin/env python3
"""Frozen gate evaluation + mechanical verdict for the temporal transfer test (torch-free)."""
from __future__ import annotations

import temporal_config as C

ALWAYS = ["ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED", "KDA_VALIDATION_BLOCKED"]


def collapse(e1_splits, b0_splits):
    a = lambda s: e1_splits[s]["addressing_top1"]
    fa = e1_splits["T8_no_match"]["false_accept"]
    fr = e1_splits["T3_temporal_order"].get("false_reject", 0.0)
    tp = 1.0 - fa
    recall = tp / (tp + fa) if (tp + fa) else 1.0
    precision = tp / (tp + fr) if (tp + fr) else 1.0
    primary = (a("T3_temporal_order") + a("T4_latest")) / 2.0
    b0_primary = (b0_splits["T3_temporal_order"]["e2e"] + b0_splits["T4_latest"]["e2e"]) / 2.0
    return {
        "T1": a("T1_unseen_entity"), "T2": a("T2_unseen_combo"), "T3": a("T3_temporal_order"),
        "T4": a("T4_latest"), "T5_diagnostic": a("T5_pred_succ"), "T6": a("T6_paraphrase"),
        "T7": a("T7_confusable"), "T9": a("T9_stable"),
        "T3_e2e": e1_splits["T3_temporal_order"]["e2e"], "T4_e2e": e1_splits["T4_latest"]["e2e"],
        "primary_structural": primary, "b0_primary": b0_primary,
        "improvement_over_b0": primary - b0_primary,
        "min_T3T4": min(a("T3_temporal_order"), a("T4_latest")),
        "nomatch_false_accept": fa, "nomatch_false_reject": fr,
        "nomatch_recall": recall, "nomatch_precision": precision,
        "b0_T3": b0_splits["T3_temporal_order"]["e2e"], "b0_T4": b0_splits["T4_latest"]["e2e"],
    }


def eval_gates(m, G=C.GATES):
    gen = {
        "T1": m["T1"] >= G["T1_min"], "T2": m["T2"] >= G["T2_min"], "T3": m["T3"] >= G["T3_min"],
        "T4": m["T4"] >= G["T4_min"], "T6": m["T6"] >= G["T6_min"], "T7": m["T7"] >= G["T7_min"],
        "T9": m["T9"] >= G["T9_min_no_material_regression"],
    }
    e2e = {"improvement_over_b0": m["improvement_over_b0"] >= G["improvement_over_b0_min"]}
    nomatch = {
        "false_accept": m["nomatch_false_accept"] <= G["nomatch_max_false_accept"],
        "false_reject": m["nomatch_false_reject"] <= G["nomatch_max_false_reject"],
        "recall": m["nomatch_recall"] >= G["nomatch_min_recall"],
        "precision": m["nomatch_precision"] >= G["nomatch_min_precision"],
    }
    groups = {"generalization": all(gen.values()), "improvement": all(e2e.values()),
              "nomatch": all(nomatch.values())}
    return {"generalization": gen, "improvement": e2e, "nomatch": nomatch, "groups": groups,
            "all_primary_pass": all(groups.values())}


def verdict(per_seed, determinism_ok, leakage_ok, protocol_ok, resource_ok=True):
    if not (determinism_ok and leakage_ok and protocol_ok):
        return "E1_TEMPORAL_TRANSFER_PROTOCOL_VIOLATED", list(ALWAYS)
    if not resource_ok:
        return "E1_TEMPORAL_TRANSFER_RESOURCE_BLOCKED", list(ALWAYS)
    n = len(per_seed)
    req = C.GATES["required_seeds_pass"]
    floor = C.GATES["worst_seed_min_T3T4_floor"]
    nomatch_pass = sum(1 for s in per_seed if s["gates"]["groups"]["nomatch"])
    full = sum(1 for s in per_seed if s["gates"]["all_primary_pass"])
    worst_min_t3t4 = min(s["metrics"]["min_T3T4"] for s in per_seed)
    # core transfer = generalization-except-T4 + improvement hold
    def core_ok(s):
        g = s["gates"]["generalization"]
        return g["T1"] and g["T2"] and g["T3"] and g["T6"] and g["T7"] and g["T9"] \
            and s["gates"]["groups"]["improvement"]
    core = sum(1 for s in per_seed if core_ok(s))

    if nomatch_pass < req:
        return "E1_TEMPORAL_TRANSFER_NO_MATCH_FAILED", list(ALWAYS)
    if full >= req and worst_min_t3t4 >= floor:
        return "E1_TEMPORAL_TRANSFER_VALIDATED", list(ALWAYS) + ["E1_STRUCTURAL_TRANSFER_CONFIRMED", "E1_FOLLOW_ON_RESEARCH_ELIGIBLE"]
    if core >= req:
        return "E1_TEMPORAL_TRANSFER_PARTIAL", list(ALWAYS)
    return "E1_TEMPORAL_TRANSFER_FAILED", list(ALWAYS)
