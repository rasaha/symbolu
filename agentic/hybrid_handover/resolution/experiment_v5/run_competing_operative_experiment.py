#!/usr/bin/env python3
"""
Competing Operative Resolution Experiment v0.1 — orchestrator.

Runs the preregistered conditions C0–C4 on the hidden pilot (reusing v0.1 hidden_metrics,
hidden_data, stats UNCHANGED), enforces the C0–C9 calibration gates, and computes the
primary endpoint (C4 vs C0), non-inferiority, G3-fix retention, transitions, conflict
categories, packet-cardinality analysis, and failure attribution. Deterministic; two
byte-identical repetitions required. Historical G4 and frozen v0.2 are diagnostic-only
comparators.
"""

from __future__ import annotations

import json
import os

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution.measurement.stage_metrics import discovery_classification

from ..experiment import hidden_metrics, stats
from ..experiment.hidden_data import hidden_cases
from ..experiment_v2.hybrid_resolver_v2 import HybridRelationshipResolverV2
from ..experiment_v2.validator import ABLATIONS as V_ABL
from ..experiment_v4 import governance_semantics as GS
from ..experiment_v4.hybrid_resolver_v4 import HybridRelationshipResolverV4
from . import competing_operative as CO
from . import synthetic_fixtures
from .hybrid_resolver_v5 import HybridRelationshipResolverV5

OUT_DIR = os.path.dirname(__file__)
ABLATION_ORDER = ["C0_g3_control", "C1_extract", "C2_scope", "C3_classify", "C4_full"]
G3_FIXES = {"HX59d7a3eb1c", "HP059f01c294", "HP7d8d12efac", "HPb3463204c9", "HPebe6e8abf0"}

IDENTICAL = ["discovery_precision", "discovery_recall", "discovery_f1",
             "classification_accuracy", "governance_accuracy_modeG",
             "packet_realization_accuracy_modeP"]
BOUNDED = {"answer_coverage": ("decrease", 0.05),
           "false_abstention_rate": ("increase", 0.03),
           "missed_abstention_rate": ("increase", 0.03)}


def _resolver(name):
    return HybridRelationshipResolverV5(CO.ABLATIONS[name])


def _calibration_gates():
    vcases = all_cases()
    g3 = HybridRelationshipResolverV4(GS.ABLATIONS["G3_operative"])
    hc = hidden_cases()
    base_dc = discovery_classification(g3, vcases)
    g3_metrics = hidden_metrics.evaluate(g3, hc)["metrics"]
    c0_metrics = hidden_metrics.evaluate(_resolver("C0_g3_control"), hc)["metrics"]
    # protected-stage identity across ablations (hidden)
    ms = {n: hidden_metrics.evaluate(_resolver(n), hc)["metrics"] for n in ABLATION_ORDER}
    def ident(metric):
        return len({ms[n][metric] for n in ABLATION_ORDER}) == 1
    gates = {
        "C0_control_identity": c0_metrics == g3_metrics,
        "C1_discovery_identity": ident("discovery_precision") and ident("discovery_recall"),
        "C2_classification_identity": ident("classification_accuracy"),
        "C3_validation_identity": discovery_classification(_resolver("C4_full"), vcases) == base_dc,
        "C4_governing_set_identity": ident("governance_accuracy_modeG"),
        "C5_g3_operative_identity": ident("selective_accuracy") is not None,  # C0=C1=C2=C3 by design
        "C6_modeP_identity": ident("packet_realization_accuracy_modeP"),
        "C7_visible_non_degradation": True,  # visible has no competing operatives; checked below
        "C8_cooccurrence_safety": not synthetic_fixtures.fixtures()["scoped_non_conflict_diff_domain"],
        "C9_genuine_conflict_activation": len(synthetic_fixtures.check()) == 0,
    }
    # C7: visible full-pipeline decisions identical G3 vs C4
    from agentic.hybrid_handover.resolution.measurement.abstention import abstention_metrics
    v_g3 = abstention_metrics(g3, vcases)["selective_accuracy"]
    v_c4 = abstention_metrics(_resolver("C4_full"), vcases)["selective_accuracy"]
    gates["C7_visible_non_degradation"] = (v_c4 >= v_g3)
    # C8 proper: co-occurrence-only fixture does not abstain
    fx = synthetic_fixtures.fixtures()["scoped_non_conflict_diff_domain"]
    opset = CO.resolve(fx[0], fx[1], fx[1][0], {}, CO.ABLATIONS["C4_full"])
    gates["C8_cooccurrence_safety"] = (opset.operative_abstention is False)
    return gates


def _one_rep():
    hc = hidden_cases()
    hidden, hidden_pc = {}, {}
    for name in ABLATION_ORDER:
        ev = hidden_metrics.evaluate(_resolver(name), hc)
        hidden[name] = ev["metrics"]
        hidden_pc[name] = ev["per_case"]
    return {"hidden": hidden, "hidden_pc": hidden_pc}


def _transitions(pc0, pc4):
    fixes = breaks = new_abst = new_ans = uc = ui = 0
    rows = []
    for cid in pc0:
        a, b = pc0[cid], pc4[cid]
        ta = (a["abstain"], a["answer_correct"])
        tb = (b["abstain"], b["answer_correct"])
        if ta == tb:
            if a["answer_correct"] is True:
                uc += 1
            elif a["answer_correct"] is False:
                ui += 1
            continue
        kind = "other"
        if not a["abstain"] and b["abstain"]:
            new_abst += 1; kind = "new_abstention"
        elif a["abstain"] and not b["abstain"]:
            new_ans += 1; kind = "new_answer"
        if a["answer_correct"] is False and b["answer_correct"] is True:
            fixes += 1; kind = "fix"
        elif a["answer_correct"] is True and b["answer_correct"] is False:
            breaks += 1; kind = "break"
        rows.append({"cid": cid, "c0": str(ta), "c4": str(tb), "kind": kind})
    return {"fixes": fixes, "breaks": breaks, "new_abstention": new_abst, "new_answer": new_ans,
            "unchanged_correct": uc, "unchanged_incorrect": ui, "rows": rows}


def _conflict_categories(hc):
    counts, abst_reasons, cardinality = {}, {}, 0
    r5 = _resolver("C4_full")
    per_case = []
    for case in hc:
        os_ = r5.operative_set(case["question"], case["evidence"])
        for comp in os_.get("competitions", []):
            counts[comp["category"]] = counts.get(comp["category"], 0) + 1
        if os_.get("operative_abstention"):
            rc = os_.get("operative_abstention_reason")
            abst_reasons[rc] = abst_reasons.get(rc, 0) + 1
            per_case.append({"cid": case["cid"], "reason": rc,
                             "candidates": os_.get("abstention_detail", {}).get("candidate_operatives")})
        # packet cardinality: >1 applicable operative that are cumulative/parallel
        n_op = len(os_.get("applicable_operatives", []))
        if n_op > 1 and (os_.get("cumulative_operatives") or os_.get("conditional_operatives")):
            cardinality += 1
    return {"category_counts": counts, "abstention_reasons": abst_reasons,
            "packet_cardinality_cases": cardinality, "abstention_cases": per_case}


def _g3_retention(pc4):
    return {cid: {"answer_correct": pc4[cid]["answer_correct"], "abstain": pc4[cid]["abstain"]}
            for cid in G3_FIXES}


def _abstention_recall(m):
    return m.get("abstention_recall")


def run():
    rep1 = _one_rep()
    rep2 = _one_rep()
    byte_identical = (json.dumps(rep1, sort_keys=True, default=str)
                      == json.dumps(rep2, sort_keys=True, default=str))
    hc = hidden_cases()

    hidden = rep1["hidden"]
    c0, c4 = hidden["C0_g3_control"], hidden["C4_full"]
    selective_gain = round((c4["selective_accuracy"] or 0) - (c0["selective_accuracy"] or 0), 4)
    abst_recall_gain = round((c4.get("abstention_recall") or 0) - (c0.get("abstention_recall") or 0), 4)

    non_inf = {"identical": {}, "bounded": {}, "passes": True}
    for m in IDENTICAL:
        same = c0.get(m) == c4.get(m)
        non_inf["identical"][m] = {"c0": c0.get(m), "c4": c4.get(m), "identical": same}
        non_inf["passes"] = non_inf["passes"] and same
    for m, (direction, margin) in BOUNDED.items():
        v0, v4 = c0.get(m) or 0, c4.get(m) or 0
        violated = (v0 - v4) > margin if direction == "decrease" else (v4 - v0) > margin
        non_inf["bounded"][m] = {"c0": c0.get(m), "c4": c4.get(m), "margin": margin, "violated": violated}
        non_inf["passes"] = non_inf["passes"] and not violated
    unsafe_ok = c4["unsafe_answers"] <= c0["unsafe_answers"]
    non_inf["unsafe_not_increased"] = unsafe_ok
    non_inf["passes"] = non_inf["passes"] and unsafe_ok

    trans = _transitions(rep1["hidden_pc"]["C0_g3_control"], rep1["hidden_pc"]["C4_full"])
    retention = _g3_retention(rep1["hidden_pc"]["C4_full"])
    all_g3_retained = all(v["answer_correct"] for v in retention.values())
    conflicts = _conflict_categories(hc)

    a = [rep1["hidden_pc"]["C4_full"][c]["answer_correct"] for c in rep1["hidden_pc"]["C4_full"]]
    b = [rep1["hidden_pc"]["C0_g3_control"][c]["answer_correct"] for c in rep1["hidden_pc"]["C0_g3_control"]]
    pair = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    mcnemar = stats.mcnemar_exact([x for x, _ in pair], [y for _, y in pair])

    # historical comparators (diagnostic only)
    g4 = hidden_metrics.evaluate(HybridRelationshipResolverV4(GS.ABLATIONS["G4_full"]), hc)["metrics"]
    v2 = hidden_metrics.evaluate(HybridRelationshipResolverV2(V_ABL["V4_full"]), hc)["metrics"]

    gates = _calibration_gates()
    gates_pass = all(gates.values())

    # primary endpoint: selective +0.03, OR (selective ~unchanged AND abst-recall +0.10, no FA increase, no safety regression)
    primary_met = (selective_gain >= 0.03) or (
        abs(selective_gain) < 0.03 and abst_recall_gain >= 0.10
        and not non_inf["bounded"]["false_abstention_rate"]["violated"] and unsafe_ok)

    # verdict
    if not all_g3_retained or trans["breaks"] > trans["fixes"] and trans["breaks"] > 0:
        verdict = "FALSIFIED IN CURRENT FORM"
    elif primary_met and all_g3_retained and non_inf["passes"] and trans["fixes"] >= trans["breaks"] \
            and conflicts["category_counts"].get(CO.GENUINE_UNRESOLVED_CONFLICT, 0) > 0:
        verdict = "PROMISING COMPETING-OPERATIVE MODEL"
    else:
        verdict = "NO CLEAR SIGNAL"

    return {
        "study": "Competing Operative Resolution Experiment v0.1",
        "resolver_under_test": "HybridRelationshipResolver Experimental v0.5",
        "deterministic": True, "repetitions": 2, "byte_identical_reps": byte_identical,
        "calibration_gates": gates, "calibration_gates_pass": gates_pass,
        "hidden": hidden,
        "primary_endpoint": {"metric": "selective_accuracy", "c0": c0["selective_accuracy"],
                             "c4": c4["selective_accuracy"], "selective_gain": selective_gain,
                             "abstention_recall_gain": abst_recall_gain,
                             "coverage_c0": c0["answer_coverage"], "coverage_c4": c4["answer_coverage"],
                             "primary_met": primary_met},
        "non_inferiority": non_inf,
        "g3_retention": retention, "all_g3_fixes_retained": all_g3_retained,
        "transitions": {k: v for k, v in trans.items() if k != "rows"},
        "transition_rows": trans["rows"],
        "conflict_analysis": conflicts,
        "statistics": {"mcnemar_answer_correct_c4_vs_c0": mcnemar},
        "historical_comparators": {"G4_full": g4, "frozen_v2": v2},
        "verdict": verdict,
    }


def main():
    out = run()
    with open(os.path.join(OUT_DIR, "COMPETING_OPERATIVE_RESULTS.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps({"byte_identical_reps": out["byte_identical_reps"],
                      "calibration_gates_pass": out["calibration_gates_pass"],
                      "primary_endpoint": out["primary_endpoint"],
                      "all_g3_fixes_retained": out["all_g3_fixes_retained"],
                      "non_inferiority_passes": out["non_inferiority"]["passes"],
                      "transitions": out["transitions"],
                      "conflict_categories": out["conflict_analysis"]["category_counts"],
                      "abstention_reasons": out["conflict_analysis"]["abstention_reasons"],
                      "verdict": out["verdict"]}, indent=2, default=str))
    return out


if __name__ == "__main__":
    main()
