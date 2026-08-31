#!/usr/bin/env python3
"""Frozen gate evaluation + mechanical verdict for the E1 capability probe (torch-free math over
already-computed metrics). Gate numbers come from config.GATES (frozen on dev)."""
from __future__ import annotations

import config as C

ALWAYS = ["ORIGINAL_BINDINGSLOTS_NEURAL_ROUTING_UNRESOLVED", "KDA_VALIDATION_BLOCKED"]


def nomatch_precision_recall(false_accept_g6, false_reject_valid):
    """Balanced-count no-match precision/recall from G6 false-accept and a valid split's false-reject.
    positive = 'abstain'. recall = correctly-abstained no-match; precision = abstentions that were
    truly no-match."""
    tp = 1.0 - false_accept_g6          # no-match correctly abstained
    fn = false_accept_g6               # no-match wrongly answered
    fp = false_reject_valid            # valid wrongly abstained
    recall = tp / (tp + fn) if (tp + fn) else 1.0
    precision = tp / (tp + fp) if (tp + fp) else 1.0
    return precision, recall


def seed_metrics(e1_splits, b0_g1_e2e):
    """Collapse one seed's per-split eval dicts into the gate-relevant scalars."""
    g = e1_splits
    fa = g["G6_no_match"]["false_accept_rate"]
    fr = g["G1_unseen_identity"]["false_reject_rate"]
    prec, rec = nomatch_precision_recall(fa, fr)
    return {
        "G1_addr": g["G1_unseen_identity"]["addressing_top1"],
        "G2_addr": g["G2_paraphrase"]["addressing_top1"],
        "G3_addr": g["G3_hard_names"]["addressing_top1"],
        "G4_addr": g["G4_same_entity_diff_attr"]["addressing_top1"],
        "G5_addr": g["G5_recombined"]["addressing_top1"],
        "G7_addr": g["G7_stable"]["addressing_top1"],
        "G1_e2e": g["G1_unseen_identity"]["e2e_retrieval_accuracy"],
        "G1_false_reject": fr,
        "answer_availability": g["G1_unseen_identity"]["answer_availability"],
        "oracle_key_value_accuracy": g["G1_unseen_identity"]["oracle_key_value_accuracy"],
        "nomatch_false_accept": fa,
        "nomatch_recall": rec,
        "nomatch_precision": prec,
        "nomatch_confident_false_accept": g["G6_no_match"]["nomatch_confident_falseaccept_rate"],
        "b0_G1_e2e": b0_g1_e2e,
        "improvement_over_b0": g["G1_unseen_identity"]["e2e_retrieval_accuracy"] - b0_g1_e2e,
        "oracle_to_predicted_gap": g["G1_unseen_identity"]["oracle_key_value_accuracy"] - g["G1_unseen_identity"]["e2e_retrieval_accuracy"],
    }


def eval_seed_gates(m, G=C.GATES):
    """Return per-gate booleans + group flags for one seed's collapsed metrics."""
    gen = {
        "G1_unseen_identity": m["G1_addr"] >= G["G1_unseen_identity_min_addr"],
        "G2_paraphrase": m["G2_addr"] >= G["G2_paraphrase_min_addr"],
        "G3_hard_names": m["G3_addr"] >= G["G3_hard_names_min_addr"],
        "G4_same_entity_diff_attr": m["G4_addr"] >= G["G4_same_entity_diff_attr_min_addr"],
        "G5_recombined": m["G5_addr"] >= G["G5_recombined_min_addr"],
    }
    nomatch = {
        "false_accept": m["nomatch_false_accept"] <= G["nomatch_max_false_accept"],
        "recall": m["nomatch_recall"] >= G["nomatch_min_recall"],
        "precision": m["nomatch_precision"] >= G["nomatch_min_precision"],
        "confident_false_accept": m["nomatch_confident_false_accept"] <= G["nomatch_max_confident_false_accept"],
        "false_reject": m["G1_false_reject"] <= G["valid_max_false_reject"],
        "answer_availability": m["answer_availability"] >= G["min_answer_availability"],
    }
    e2e = {
        "ordinary_retrieval": m["G1_e2e"] >= G["min_ordinary_retrieval_accuracy"],
        "improvement_over_b0": m["improvement_over_b0"] >= G["min_improvement_over_b0"],
        "oracle_value": m["oracle_key_value_accuracy"] >= G["min_oracle_key_value_accuracy"],
        "oracle_gap": m["oracle_to_predicted_gap"] <= G["max_oracle_to_predicted_gap"],
    }
    stable = {"G7_stable": m["G7_addr"] >= G["min_G7_stable_addr"]}
    groups = {"generalization": all(gen.values()), "nomatch": all(nomatch.values()),
              "e2e": all(e2e.values()), "stable": all(stable.values())}
    return {"generalization": gen, "nomatch": nomatch, "e2e": e2e, "stable": stable,
            "groups": groups, "all_primary_pass": all(groups.values())}


def verdict(per_seed, determinism_ok, leakage_ok, protocol_ok, resource_ok=True,
            required=C.RESERVED_SEEDS_REQUIRED_TO_PASS, worst_floor=None):
    """Mechanical verdict over per-seed gate results (list of eval_seed_gates outputs) + collapsed
    metrics list `per_seed['metrics']`. Precedence per the merged gate/compute plan."""
    worst_floor = C.GATES["worst_seed_min_G1_addr"] if worst_floor is None else worst_floor
    if not leakage_ok:
        return "EXPLICIT_KEY_SHORTCUT_OR_LEAKAGE_DETECTED", list(ALWAYS)
    if not determinism_ok:
        return "EXPLICIT_KEY_DETERMINISM_NOT_ESTABLISHED", list(ALWAYS)
    if not protocol_ok:
        return "EXPLICIT_KEY_PROTOCOL_VIOLATED", list(ALWAYS)
    if not resource_ok:
        return "EXPLICIT_KEY_RESOURCE_BLOCKED", list(ALWAYS)

    gates = [s["gates"] for s in per_seed]
    metrics = [s["metrics"] for s in per_seed]
    n = len(gates)
    n_pass = sum(1 for g in gates if g["all_primary_pass"])
    worst_g1 = min(mm["G1_addr"] for mm in metrics)

    if n_pass >= required and worst_g1 >= worst_floor:
        return "EXPLICIT_KEY_SEMANTIC_MATCHING_VALIDATED", list(ALWAYS) + ["INDEPENDENT_NEURAL_MEMORY_CONFIRMATION_REQUIRED"]

    # count group failures across seeds
    nomatch_fail = sum(1 for g in gates if not g["groups"]["nomatch"])
    gen_fail = sum(1 for g in gates if not g["groups"]["generalization"] or not g["groups"]["e2e"])
    stable_fail = sum(1 for g in gates if not g["groups"]["stable"])

    if n_pass >= 1:
        return "EXPLICIT_KEY_SEMANTIC_MATCHING_PARTIAL", list(ALWAYS)
    # n_pass == 0: pick dominant failure by precedence (nomatch > generalization > stable)
    if nomatch_fail >= gen_fail and nomatch_fail >= stable_fail and nomatch_fail > 0:
        return "EXPLICIT_KEY_NO_MATCH_GATE_FAILED", list(ALWAYS)
    if gen_fail >= stable_fail and gen_fail > 0:
        return "EXPLICIT_KEY_GENERALIZATION_GATE_FAILED", list(ALWAYS)
    if stable_fail > 0:
        return "EXPLICIT_KEY_STABLE_CASE_REGRESSION", list(ALWAYS)
    return "EXPLICIT_KEY_SEMANTIC_MATCHING_NOT_SELECTED", list(ALWAYS)
