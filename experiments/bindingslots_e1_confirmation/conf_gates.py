#!/usr/bin/env python3
"""Independent gate evaluation + confirmation verdict (torch-free). Uses the SAME frozen gate numbers as
PR #1351 (conf_config.GATES); re-implemented mapping so the confirmation is not a replay."""
from __future__ import annotations

import conf_config as C

ALWAYS = ["ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED", "KDA_VALIDATION_BLOCKED"]


def nomatch_pr(false_accept, false_reject):
    tp = 1.0 - false_accept
    recall = tp / (tp + false_accept) if (tp + false_accept) else 1.0
    precision = tp / (tp + false_reject) if (tp + false_reject) else 1.0
    return precision, recall


def collapse(e1_splits, b0_g1_e2e):
    g = e1_splits
    fa = g["G6_no_match"]["false_accept"]
    fr = g["G1_unseen_identity"]["false_reject"]
    prec, rec = nomatch_pr(fa, fr)
    return {
        "G1_addr": g["G1_unseen_identity"]["addressing_top1"],
        "G2_addr": g["G2_paraphrase"]["addressing_top1"],
        "G3_addr": g["G3_hard_names"]["addressing_top1"],
        "G4_addr": g["G4_same_entity_diff_attr"]["addressing_top1"],
        "G5_addr": g["G5_recombined"]["addressing_top1"],
        "G7_addr": g["G7_stable"]["addressing_top1"],
        "G1_e2e": g["G1_unseen_identity"]["e2e"],
        "G1_false_reject": fr, "answer_availability": g["G1_unseen_identity"]["answer_availability"],
        "oracle_key_value_accuracy": g["G1_unseen_identity"]["oracle_key_value_accuracy"],
        "nomatch_false_accept": fa, "nomatch_recall": rec, "nomatch_precision": prec,
        "nomatch_confident_false_accept": g["G6_no_match"]["confident_false_accept"],
        "b0_G1_e2e": b0_g1_e2e, "improvement_over_b0": g["G1_unseen_identity"]["e2e"] - b0_g1_e2e,
        "oracle_to_predicted_gap": g["G1_unseen_identity"]["oracle_key_value_accuracy"] - g["G1_unseen_identity"]["e2e"],
    }


def eval_gates(m, G=C.GATES):
    gen = {"G1": m["G1_addr"] >= G["G1_unseen_identity_min_addr"],
           "G2": m["G2_addr"] >= G["G2_paraphrase_min_addr"],
           "G3": m["G3_addr"] >= G["G3_hard_names_min_addr"],
           "G4": m["G4_addr"] >= G["G4_same_entity_diff_attr_min_addr"],
           "G5": m["G5_addr"] >= G["G5_recombined_min_addr"]}
    nomatch = {"false_accept": m["nomatch_false_accept"] <= G["nomatch_max_false_accept"],
               "recall": m["nomatch_recall"] >= G["nomatch_min_recall"],
               "precision": m["nomatch_precision"] >= G["nomatch_min_precision"],
               "confident_fa": m["nomatch_confident_false_accept"] <= G["nomatch_max_confident_false_accept"],
               "false_reject": m["G1_false_reject"] <= G["valid_max_false_reject"],
               "availability": m["answer_availability"] >= G["min_answer_availability"]}
    e2e = {"ordinary": m["G1_e2e"] >= G["min_ordinary_retrieval_accuracy"],
           "improvement": m["improvement_over_b0"] >= G["min_improvement_over_b0"],
           "oracle": m["oracle_key_value_accuracy"] >= G["min_oracle_key_value_accuracy"],
           "oracle_gap": m["oracle_to_predicted_gap"] <= G["max_oracle_to_predicted_gap"]}
    stable = {"G7": m["G7_addr"] >= G["min_G7_stable_addr"]}
    groups = {"generalization": all(gen.values()), "nomatch": all(nomatch.values()),
              "e2e": all(e2e.values()), "stable": all(stable.values())}
    return {"generalization": gen, "nomatch": nomatch, "e2e": e2e, "stable": stable,
            "groups": groups, "all_primary_pass": all(groups.values())}


def verdict(per_seed, determinism_ok, leakage_ok, protocol_ok, resource_ok=True):
    if not (determinism_ok and leakage_ok and protocol_ok):
        return "E1_CONFIRMATION_PROTOCOL_VIOLATED", list(ALWAYS)
    if not resource_ok:
        return "E1_CONFIRMATION_RESOURCE_BLOCKED", list(ALWAYS)
    required = C.RESERVED_SEEDS_REQUIRED_TO_PASS
    floor = C.GATES["worst_seed_min_G1_addr"]
    n_pass = sum(1 for s in per_seed if s["gates"]["all_primary_pass"])
    worst = min(s["metrics"]["G1_addr"] for s in per_seed)
    if n_pass >= required and worst >= floor:
        return "E1_INDEPENDENTLY_CONFIRMED", list(ALWAYS) + ["E1_FOLLOW_ON_RESEARCH_ELIGIBLE"]
    if n_pass >= 1:
        return "E1_CONFIRMATION_PARTIAL", list(ALWAYS)
    return "E1_CONFIRMATION_FAILED", list(ALWAYS)
