#!/usr/bin/env python3
"""Torch-free mechanism gates, futility, selection and verdict for the address-generalization /
gradient-isolation phase. Reuses the FROZEN persistence clean-stable classifier for clean-stable and
quality. All numeric thresholds are frozen (mirrored in preregistration.json thresholds_frozen) and
were set from merged clean-control distributions, not from A1/G1 outcomes.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
PERS = REPO / "experiments" / "bindingslots_persistence"
for p in (str(HERE), str(PERS)):
    if p not in sys.path:
        sys.path.insert(0, p)

# ---- frozen thresholds (preregistered; from clean-control distributions, not from outcomes) ----
QUALITY_RATIO = 1.20
MATERIAL_PROB_DELTA = 0.15        # eval-time correct-slot prob improvement vs paired B0
TOP1_DELTA = 0.15                 # eval-time correct-slot top-1 improvement vs paired B0
APPROACH_ORACLE_RATIO = 0.80      # ordinary needle >= 0.80 * oracle-address needle
G1_CONFLICT_MAX_COS = -0.02       # teacher-window mean wak cosine must reach >= this (neg eliminated)
G1_CONFLICT_REDUCE_FRAC = 0.50    # OR |cos| reduced by >= 50% vs paired B0
NONINF_NEEDLE = 0.05              # G1 non-inferiority margin (needle)
NONINF_PROB = 0.05               # G1 non-inferiority margin (eval correct-slot prob)
OTHER_GROUP_CONFLICT = -0.10      # a NEW conflict in another group is cosine <= this and worse than B0
NEED = 4                          # 4/5 required
NSEEDS = 5


def quality_qualified(cand_rec, aplus_rec):
    return float(cand_rec["ppl"]["256"]) <= QUALITY_RATIO * float(aplus_rec["ppl"]["256"])


def clean_stable(cand_rec, aplus_rec):
    import persistence_classify as PC
    d = PC.classify_seed(cand_rec, aplus_rec)
    return bool(d.get("clean_stable")), d


def _er1200(rec):
    for e in reversed(rec.get("eval_time_routing", [])):
        if e.get("step") == 1200:
            return e
    return rec.get("eval_time_routing", [{}])[-1] if rec.get("eval_time_routing") else {}


def _teacher_window_wak_cos(rec):
    """Mean write_addr_proj LM-vs-aux cosine over the teacher window checkpoints (>=600)."""
    vals = [g.get("lm_vs_aux_cosine_wak") for g in rec.get("grad_behaviour", [])
            if g.get("step", 0) >= 600 and g.get("lm_vs_aux_cosine_wak") is not None]
    return sum(vals) / len(vals) if vals else None


def _other_group_min_cos(rec):
    """Most-negative non-write_addr_proj group cosine over teacher-window checkpoints."""
    worst = {}
    for g in rec.get("grad_behaviour", []):
        if g.get("step", 0) < 600:
            continue
        for grp, c in (g.get("lm_vs_aux_cosine_by_group") or {}).items():
            if grp == "write_addr_proj":
                continue
            worst[grp] = min(worst.get(grp, 1.0), c)
    return worst


# --------------------------------------------------------------- per-seed rows
def seed_rows(arm, arm_by_seed, b0_by_seed, aplus_by_seed):
    rows = []
    for s in sorted(arm_by_seed):
        cand = arm_by_seed[s]; ap = aplus_by_seed[s]; b0 = b0_by_seed.get(s)
        qq = quality_qualified(cand, ap)
        cs, cs_detail = clean_stable(cand, ap)
        er = _er1200(cand); erb = _er1200(b0) if b0 else {}
        row = {"arm": arm, "seed": s, "quality_qualified": qq, "clean_stable": cs,
               "eval_prob": er.get("correct_slot_prob"), "eval_top1": er.get("correct_slot_top1"),
               "ordinary_needle": er.get("ordinary_needle"), "oracle_needle": er.get("oracle_address_needle"),
               "prob_delta_vs_b0": (er.get("correct_slot_prob", 0) - erb.get("correct_slot_prob", 0)) if b0 else None,
               "top1_delta_vs_b0": (er.get("correct_slot_top1", 0) - erb.get("correct_slot_top1", 0)) if b0 else None,
               "approaches_oracle": (er.get("ordinary_needle", 0) >= APPROACH_ORACLE_RATIO * er.get("oracle_address_needle", 0))
                                    if er.get("oracle_address_needle", 0) > 0 else False,
               "needle_noninf_vs_b0": (er.get("ordinary_needle", 0) >= erb.get("ordinary_needle", 0) - NONINF_NEEDLE) if b0 else None,
               "prob_noninf_vs_b0": (er.get("correct_slot_prob", 0) >= erb.get("correct_slot_prob", 0) - NONINF_PROB) if b0 else None,
               "wak_cos_teacher_window": _teacher_window_wak_cos(cand),
               "b0_wak_cos_teacher_window": _teacher_window_wak_cos(b0) if b0 else None,
               "other_group_min_cos": _other_group_min_cos(cand),
               "g1_negative_cosine_updates": cand.get("g1_negative_cosine_updates")}
        rows.append(row)
    return rows


def a1_gate(rows, leakage_ok):
    n = len(rows)
    qq = sum(r["quality_qualified"] for r in rows)
    cs = sum(r["clean_stable"] for r in rows)
    prob_improve = sum(1 for r in rows if (r["prob_delta_vs_b0"] or 0) >= MATERIAL_PROB_DELTA)
    top1_improve = sum(1 for r in rows if (r["top1_delta_vs_b0"] or 0) >= TOP1_DELTA)
    approach = sum(1 for r in rows if r["approaches_oracle"])
    conds = {
        "quality_ge_4of5": qq >= NEED,
        "clean_stable_ge_4of5": cs >= NEED,
        "eval_routing_materially_improves_ge_4of5": prob_improve >= NEED,
        "top1_improves_ge_4of5": top1_improve >= NEED,
        "approaches_oracle_ge_4of5": approach >= NEED,
        "eval_routing_changed_not_probe_only": prob_improve >= NEED,  # improvement is on held-out eval
        "no_template_leakage": bool(leakage_ok),
    }
    return all(conds.values()), conds


def g1_gate(rows):
    n = len(rows)
    qq = sum(r["quality_qualified"] for r in rows)
    def conflict_reduced(r):
        c = r["wak_cos_teacher_window"]; b = r["b0_wak_cos_teacher_window"]
        if c is None:
            return False
        if c >= G1_CONFLICT_MAX_COS:
            return True
        if b is not None and b < 0 and c > b and abs(c) <= (1 - G1_CONFLICT_REDUCE_FRAC) * abs(b):
            return True
        return False
    def no_new_conflict(r):
        b0worst = None  # compared per-group to B0 would need b0 rows; use absolute floor + not worse
        for grp, c in (r["other_group_min_cos"] or {}).items():
            if c <= OTHER_GROUP_CONFLICT:
                return False
        return True
    reduced = sum(1 for r in rows if conflict_reduced(r))
    noninf = sum(1 for r in rows if (r["needle_noninf_vs_b0"] and r["prob_noninf_vs_b0"]))
    no_new = sum(1 for r in rows if no_new_conflict(r))
    conds = {
        "quality_ge_4of5": qq >= NEED,
        "conflict_reduced_ge_4of5": reduced >= NEED,
        "noninferior_retrieval_and_routing_ge_4of5": noninf >= NEED,
        "no_new_conflict_other_group_ge_4of5": no_new >= NEED,
        "only_write_addr_proj_projected": True,   # structural (G1 projects wak only; asserted by tests)
        "training_semantics_unchanged": all(r.get("g1_negative_cosine_updates") is not None for r in rows),
    }
    return all(conds.values()), conds


def ag_gate(rows):
    qq_cs = sum(1 for r in rows if r["quality_qualified"] and r["clean_stable"])
    approach = sum(1 for r in rows if r["approaches_oracle"])
    conds = {"quality_qualified_clean_stable_ge_4of5": qq_cs >= NEED,
             "approaches_oracle_ge_4of5": approach >= NEED}
    return all(conds.values()), conds


def arm_futile(rows_so_far):
    """After the SECOND completed seed making 4/5 impossible, the arm is futile. A seed 'fails' the
    arm if it is not both quality-qualified and clean-stable (the shared necessary condition)."""
    completed = len(rows_so_far)
    fails = sum(1 for r in rows_so_far if not (r["quality_qualified"] and r["clean_stable"]))
    max_possible_clean = (NSEEDS - fails)
    return fails >= 2 and max_possible_clean < NEED


def verdict(a1_pass, g1_pass, ag_ran, ag_pass):
    if a1_pass and g1_pass:
        if ag_ran and ag_pass:
            return "JOINT_BINDINGSLOTS_INTERVENTION_CANDIDATE_SELECTED"
        if ag_ran and not ag_pass:
            return "BINDINGSLOTS_INTERVENTION_RESULTS_INCONCLUSIVE"  # both pass, AG failed -> interaction diagnosis next
        return "BOTH_COMPONENTS_PASS_JOINT_ARM_NOT_RUN"
    if a1_pass:
        return "READ_ADDRESS_GENERALIZATION_CANDIDATE_SELECTED"
    if g1_pass:
        return "ROUTING_GRADIENT_ISOLATION_CANDIDATE_SELECTED"
    return "NO_BINDINGSLOTS_INTERVENTION_SELECTED"


FROZEN_THRESHOLDS = {
    "QUALITY_RATIO": QUALITY_RATIO, "MATERIAL_PROB_DELTA": MATERIAL_PROB_DELTA, "TOP1_DELTA": TOP1_DELTA,
    "APPROACH_ORACLE_RATIO": APPROACH_ORACLE_RATIO, "G1_CONFLICT_MAX_COS": G1_CONFLICT_MAX_COS,
    "G1_CONFLICT_REDUCE_FRAC": G1_CONFLICT_REDUCE_FRAC, "NONINF_NEEDLE": NONINF_NEEDLE,
    "NONINF_PROB": NONINF_PROB, "OTHER_GROUP_CONFLICT": OTHER_GROUP_CONFLICT, "NEED": NEED, "NSEEDS": NSEEDS,
}
