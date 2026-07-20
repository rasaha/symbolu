#!/usr/bin/env python3
"""
Governance Semantics Experiment v0.1 — orchestrator.

Runs the preregistered conditions G0–G4 on the visible corpus (frozen measurement
package, for the calibration gates) and the frozen 60-case Hidden Relationship Corpus
Pilot v0.2 (reusing the v0.1 `hidden_metrics`, `hidden_data`, `stats` modules
UNCHANGED). Fully deterministic; two byte-identical repetitions required.

Primary endpoint: full-pipeline selective accuracy, G4 vs G0 (paired). Also computes
the non-inferiority table, fix/break transitions, competing-authority analysis,
failure attribution, and diagnostic subgroups. Governance-status accuracies that would
require gold status labels absent from the frozen annotations are reported as
NOT EVALUABLE (honest), never fabricated.
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
from . import governance_semantics as GS
from .hybrid_resolver_v4 import HybridRelationshipResolverV4

OUT_DIR = os.path.dirname(__file__)
ABLATION_ORDER = ["G0_frozen", "G1_supersession_amendment", "G2_parallel",
                  "G3_operative", "G4_full"]

# non-inferiority: metrics that must be EXACTLY identical vs G0
IDENTICAL = ["discovery_precision", "discovery_recall", "discovery_f1",
             "classification_accuracy", "packet_realization_accuracy_modeP"]
# non-inferiority: bounded degradations vs G0
BOUNDED = {"governance_accuracy_modeG": ("decrease", 0.03),
           "answer_coverage": ("decrease", 0.05),
           "false_abstention_rate": ("increase", 0.05),
           "missed_abstention_rate": ("increase", 0.05)}


def _resolver(name):
    return HybridRelationshipResolverV4(GS.ABLATIONS[name])


def _one_rep():
    vcases = all_cases()
    hcases = hidden_cases()
    visible, hidden, hidden_pc = {}, {}, {}
    for name in ABLATION_ORDER:
        visible[name] = discovery_classification(_resolver(name), vcases)
        ev = hidden_metrics.evaluate(_resolver(name), hcases)
        hidden[name] = ev["metrics"]
        hidden_pc[name] = ev["per_case"]
    return {"visible": visible, "hidden": hidden, "hidden_pc": hidden_pc}


def _calibration_gates():
    """G0–G4 identity gates on the VISIBLE corpus (must all pass pre-lock)."""
    vcases = all_cases()
    v2 = HybridRelationshipResolverV2(V_ABL["V4_full"])
    base_dc = discovery_classification(v2, vcases)
    gates = {}
    # G0 == v0.2
    g0_dc = discovery_classification(_resolver("G0_frozen"), vcases)
    gates["G0_control_reproduces_v2"] = (g0_dc == base_dc)
    # G1/G2: discovery + classification identical across all ablations
    disc_ident = all(discovery_classification(_resolver(n), vcases) == base_dc for n in ABLATION_ORDER)
    gates["G1_discovery_identical"] = disc_ident
    gates["G2_classification_identical"] = disc_ident
    # G3: validation records identical (delegated to v0.2, unchanged)
    c = vcases[0]
    from agentic.hybrid_handover.resolution.modes import mode_oracle
    recs = [json.dumps(HybridRelationshipResolverV4(GS.ABLATIONS[n])._v2.validation_records(
        c.question, mode_oracle(c)), sort_keys=True, default=str) for n in ABLATION_ORDER]
    gates["G3_validation_records_identical"] = len(set(recs)) == 1
    return gates


def _competing_authority(hcases):
    """Cases with >=2 governance sources: G0 vs G4 decision, fix/break, mechanism."""
    g0, g4 = _resolver("G0_frozen"), _resolver("G4_full")
    rows, reprioritized = [], 0
    for case in hcases:
        graph = g4.resolve_relationships(case["question"], case["evidence"])
        srcs = sorted({e.src for e in graph.edges if e.type in GS.GOVERNANCE_SOURCE_TYPES})
        if len(srcs) < 2:
            continue
        r0 = g0.resolve(case["question"], case["evidence"])
        r4 = g4.resolve(case["question"], case["evidence"])
        gr = g4.governance_result(case["question"], case["evidence"])
        gold = case["gold"]
        d0 = (r0.governance.abstain, r0.tfc, r0.notice_days, r0.penalty)
        d4 = (r4.governance.abstain, r4.tfc, r4.notice_days, r4.penalty)
        reprioritized += 1
        rows.append({
            "cid": case["cid"], "governance_sources": srcs,
            "operative_nodes": gr.get("operative_nodes"),
            "governance_abstention": gr.get("governance_abstention"),
            "abstention_reason": gr.get("governance_abstention_reason"),
            "g0_decision": str(d0), "g4_decision": str(d4), "changed": d0 != d4,
            "gold_abstain": gold["abstain"], "gold_packet": gold.get("packet"),
            "capability": gold["capability"],
        })
    return {"cases_with_competition": reprioritized, "rows": rows}


def _fix_break(pc0, pc4):
    fixes = breaks = unchanged_correct = unchanged_incorrect = 0
    detail = {"fix": [], "break": []}
    for cid in pc0:
        a, b = pc0[cid]["answer_correct"], pc4[cid]["answer_correct"]
        if a is None or b is None:
            continue
        if not a and b:
            fixes += 1; detail["fix"].append(cid)
        elif a and not b:
            breaks += 1; detail["break"].append(cid)
        elif a and b:
            unchanged_correct += 1
        else:
            unchanged_incorrect += 1
    return {"fixes": fixes, "breaks": breaks, "unchanged_correct": unchanged_correct,
            "unchanged_incorrect": unchanged_incorrect, "detail": detail}


def _subgroups(pc0, pc4):
    caps = sorted({c for v in pc0.values() for c in v["capability"]})
    out = {"by_capability": {}, "by_difficulty": {}, "by_source": {}}
    def sel(pc, keep):
        ans = [v for v in pc.values() if v["answered"] and keep(v)]
        ok = sum(1 for v in ans if v["answer_correct"])
        return round(ok / len(ans), 4) if ans else None
    for c in caps:
        out["by_capability"][c] = {"g0": sel(pc0, lambda v, c=c: c in v["capability"]),
                                   "g4": sel(pc4, lambda v, c=c: c in v["capability"])}
    for d in sorted({v["difficulty"] for v in pc0.values() if v["difficulty"]}):
        out["by_difficulty"][d] = {"g0": sel(pc0, lambda v, d=d: v["difficulty"] == d),
                                   "g4": sel(pc4, lambda v, d=d: v["difficulty"] == d)}
    for s in ("seed", "pilot"):
        out["by_source"][s] = {"g0": sel(pc0, lambda v, s=s: v["source"] == s),
                               "g4": sel(pc4, lambda v, s=s: v["source"] == s)}
    return out


def _failure_attribution(pc4):
    """Primary stage for each incorrect G4 case (governance layer only blamed for its own)."""
    counts = {}
    for cid, v in pc4.items():
        if not v["owned"]:
            continue
        wrong = (v["answer_correct"] is False) or (v["governanceG"] is False)
        if not wrong:
            continue
        if not v["discovery_complete"]:
            stage = "proposal_generation"          # missing edge (frozen proposal)
        elif v["governanceG"] is False:
            stage = "governance_applicability"
        elif v["answer_correct"] is False:
            stage = "operative_source_or_frozen_packet"
        else:
            stage = "none"
        counts[stage] = counts.get(stage, 0) + 1
    return counts


def run():
    rep1 = _one_rep()
    rep2 = _one_rep()
    byte_identical = (json.dumps(rep1, sort_keys=True, default=str)
                      == json.dumps(rep2, sort_keys=True, default=str))

    hidden = rep1["hidden"]
    g0, g4 = hidden["G0_frozen"], hidden["G4_full"]
    selective_gain = round((g4["selective_accuracy"] or 0) - (g0["selective_accuracy"] or 0), 4)

    non_inf = {"identical": {}, "bounded": {}, "passes": True}
    for m in IDENTICAL:
        same = g0.get(m) == g4.get(m)
        non_inf["identical"][m] = {"g0": g0.get(m), "g4": g4.get(m), "identical": same}
        non_inf["passes"] = non_inf["passes"] and same
    for m, (direction, margin) in BOUNDED.items():
        v0, v4 = g0.get(m) or 0, g4.get(m) or 0
        violated = (v0 - v4) > margin if direction == "decrease" else (v4 - v0) > margin
        non_inf["bounded"][m] = {"g0": g0.get(m), "g4": g4.get(m), "margin": margin,
                                 "direction": direction, "violated": violated}
        non_inf["passes"] = non_inf["passes"] and not violated
    unsafe_ok = g4["unsafe_answers"] <= g0["unsafe_answers"]
    non_inf["unsafe_not_increased"] = unsafe_ok
    non_inf["passes"] = non_inf["passes"] and unsafe_ok

    fb = _fix_break(rep1["hidden_pc"]["G0_frozen"], rep1["hidden_pc"]["G4_full"])
    a = [rep1["hidden_pc"]["G4_full"][c]["answer_correct"] for c in rep1["hidden_pc"]["G4_full"]]
    b = [rep1["hidden_pc"]["G0_frozen"][c]["answer_correct"] for c in rep1["hidden_pc"]["G0_frozen"]]
    paired = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    mcnemar = stats.mcnemar_exact([x for x, _ in paired], [y for _, y in paired])
    # bootstrap on per-answered selective (paired)
    boot = _bootstrap_selective(rep1["hidden_pc"]["G4_full"], rep1["hidden_pc"]["G0_frozen"])

    comp = _competing_authority(hidden_cases())
    subgroups = _subgroups(rep1["hidden_pc"]["G0_frozen"], rep1["hidden_pc"]["G4_full"])
    attribution = _failure_attribution(rep1["hidden_pc"]["G4_full"])
    gates = _calibration_gates()

    # verdict per preregistered criteria
    all_ni = non_inf["passes"]
    if not all_ni or selective_gain < -0.0001:
        verdict = "FALSIFIED IN CURRENT FORM" if selective_gain < -0.03 or not unsafe_ok \
            else "NO CLEAR SIGNAL"
    elif selective_gain >= 0.03 and fb["fixes"] > fb["breaks"] and comp["cases_with_competition"] > 0:
        verdict = "PROMISING GOVERNANCE SEMANTICS"
    else:
        verdict = "NO CLEAR SIGNAL"

    return {
        "study": "Governance Semantics Experiment v0.1",
        "resolver_under_test": "HybridRelationshipResolver Experimental v0.4",
        "deterministic": True, "repetitions": 2, "byte_identical_reps": byte_identical,
        "calibration_gates": gates,
        "visible": rep1["visible"], "hidden": hidden,
        "primary_endpoint": {"metric": "selective_accuracy", "g0": g0["selective_accuracy"],
                             "g4": g4["selective_accuracy"], "selective_gain": selective_gain,
                             "practical_threshold": 0.03,
                             "practically_significant": selective_gain >= 0.03},
        "non_inferiority": non_inf,
        "fix_break": fb,
        "statistics": {"mcnemar_answer_correct_g4_vs_g0": mcnemar,
                       "bootstrap_selective_g4_minus_g0": boot},
        "competing_authority": comp,
        "subgroups": subgroups,
        "failure_attribution": attribution,
        "verdict": verdict,
    }


def _bootstrap_selective(pc4, pc0, iters=stats.BOOTSTRAP_ITERS, seed=stats.BOOTSTRAP_SEED):
    import random
    cids = list(pc4)
    n = len(cids)

    def sel(pc, idxs):
        ans = [pc[cids[i]] for i in idxs if pc[cids[i]]["answered"]]
        ok = sum(1 for v in ans if v["answer_correct"])
        return ok / len(ans) if ans else 0.0
    allidx = list(range(n))
    obs = sel(pc4, allidx) - sel(pc0, allidx)
    rng = random.Random(seed)
    diffs = []
    for _ in range(iters):
        s = [rng.randrange(n) for _ in allidx]
        diffs.append(sel(pc4, s) - sel(pc0, s))
    diffs.sort()
    lo = diffs[int((stats.CI_ALPHA / 2) * iters)]
    hi = diffs[int((1 - stats.CI_ALPHA / 2) * iters) - 1]
    return {"observed_diff": round(obs, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "excludes_zero": bool(lo > 0 or hi < 0), "n": n, "iters": iters, "seed": seed}


def main():
    out = run()
    with open(os.path.join(OUT_DIR, "GOVERNANCE_SEMANTICS_RESULTS.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    print(json.dumps({"byte_identical_reps": out["byte_identical_reps"],
                      "calibration_gates": out["calibration_gates"],
                      "primary_endpoint": out["primary_endpoint"],
                      "non_inferiority_passes": out["non_inferiority"]["passes"],
                      "fix_break": {k: out["fix_break"][k] for k in
                                    ("fixes", "breaks", "unchanged_correct", "unchanged_incorrect")},
                      "competition_cases": out["competing_authority"]["cases_with_competition"],
                      "verdict": out["verdict"]}, indent=2, default=str))
    return out


if __name__ == "__main__":
    main()
