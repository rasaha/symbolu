#!/usr/bin/env python3
"""
Edge Prioritization Experiment v0.1 — orchestrator.

Runs the preregistered ablations P0–P4 on the visible corpus (frozen measurement
package) and the frozen 60-case Hidden Relationship Corpus Pilot v0.2 (reusing the
v0.1 `hidden_metrics`, `hidden_data`, and `stats` modules UNCHANGED). Fully
deterministic; two byte-identical repetitions required.

Primary endpoint: selective accuracy, subject to no degradation of discovery
precision/recall, classification, governance Mode G, packet Mode P, or unsafe answers.
Also counts competing edges reprioritized and full-pipeline governance decisions that
changed (P4 vs P0).
"""

from __future__ import annotations

import json
import os

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution.measurement.stage_metrics import discovery_classification

from ..experiment import hidden_metrics, stats
from ..experiment.hidden_data import hidden_cases
from .hybrid_resolver_v3 import HybridRelationshipResolverV3
from .prioritizer import ABLATIONS

OUT_DIR = os.path.dirname(__file__)
ABLATION_ORDER = ["P0_none", "P1_authority", "P2_authority_temporal",
                  "P3_auth_temporal_specificity", "P4_full"]
# metrics that must NOT degrade
PROTECTED = ["discovery_precision", "discovery_recall", "classification_accuracy",
             "governance_accuracy_modeG", "packet_realization_accuracy_modeP", "unsafe_answers"]


def _resolver(name):
    return HybridRelationshipResolverV3(ABLATIONS[name])


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


def _competition_and_decision_deltas(hcases):
    """Count competitions reprioritized (P4) and governance decisions changed (P4 vs P0)."""
    p0 = _resolver("P0_none")
    p4 = _resolver("P4_full")
    reprioritized = 0
    cases_with_competition = 0
    decisions_changed = 0
    changed_cases = []
    per_competition = []
    for case in hcases:
        recs = p4.competition_records(case["question"], case["evidence"])
        if recs:
            cases_with_competition += 1
            reprioritized += len(recs)
            for r in recs:
                per_competition.append({"cid": case["cid"], **r})
        r0 = p0.resolve(case["question"], case["evidence"])
        r4 = p4.resolve(case["question"], case["evidence"])
        d0 = (r0.governance.abstain, tuple(sorted(r0.governance.governing)),
              r0.tfc, r0.notice_days, r0.penalty)
        d4 = (r4.governance.abstain, tuple(sorted(r4.governance.governing)),
              r4.tfc, r4.notice_days, r4.penalty)
        if d0 != d4:
            decisions_changed += 1
            changed_cases.append({"cid": case["cid"], "p0": str(d0), "p4": str(d4)})
    return {"cases_with_competition": cases_with_competition,
            "competing_edges_reprioritized": reprioritized,
            "governance_decisions_changed": decisions_changed,
            "changed_cases": changed_cases, "per_competition": per_competition}


def run():
    rep1 = _one_rep()
    rep2 = _one_rep()
    byte_identical = (json.dumps(rep1, sort_keys=True, default=str)
                      == json.dumps(rep2, sort_keys=True, default=str))

    hidden = rep1["hidden"]
    p0, p4 = hidden["P0_none"], hidden["P4_full"]
    selective_gain = round((p4["selective_accuracy"] or 0) - (p0["selective_accuracy"] or 0), 4)

    # protected-metric integrity
    protected = {}
    no_degradation = True
    for m in PROTECTED:
        v0v, v4v = p0.get(m), p4.get(m)
        if m == "unsafe_answers":
            degraded = (v4v or 0) > (v0v or 0)
        else:
            degraded = (v0v is not None and v4v is not None and v4v < v0v)
        protected[m] = {"p0": v0v, "p4": v4v, "unchanged": v0v == v4v, "degraded": degraded}
        no_degradation = no_degradation and not degraded

    comp = _competition_and_decision_deltas(hidden_cases())

    success = {
        "selective_accuracy_improves": selective_gain > 0,
        "discovery_unchanged": protected["discovery_precision"]["unchanged"]
        and protected["discovery_recall"]["unchanged"]
        and protected["classification_accuracy"]["unchanged"],
        "precision_unchanged": protected["discovery_precision"]["unchanged"],
        "recall_unchanged": protected["discovery_recall"]["unchanged"],
        "unsafe_unchanged": protected["unsafe_answers"]["unchanged"],
    }
    all_success = all(success.values())

    # paired McNemar on full-pipeline answer correctness (P4 vs P0), owned+answered
    a = [rep1["hidden_pc"]["P4_full"][c]["answer_correct"] for c in rep1["hidden_pc"]["P4_full"]]
    b = [rep1["hidden_pc"]["P0_none"][c]["answer_correct"] for c in rep1["hidden_pc"]["P0_none"]]
    paired = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    mcnemar = stats.mcnemar_exact([x for x, _ in paired], [y for _, y in paired])

    if not no_degradation:
        verdict = "FALSIFIED (prioritization harmed a protected metric)"
    elif selective_gain > 0 and all_success:
        verdict = "PROMISING PRIORITIZATION"
    elif comp["governance_decisions_changed"] == 0:
        verdict = "NO CLEAR SIGNAL (no governance decision changed)"
    elif selective_gain <= 0:
        verdict = "NO CLEAR SIGNAL (reshuffled edges without improving decisions)"
    else:
        verdict = "NO CLEAR SIGNAL"

    return {
        "study": "Edge Prioritization Experiment v0.1",
        "resolver_under_test": "HybridRelationshipResolver Experimental v0.3",
        "deterministic": True, "repetitions": 2, "byte_identical_reps": byte_identical,
        "visible": rep1["visible"], "hidden": hidden,
        "primary_endpoint": {"metric": "selective_accuracy",
                             "p0": p0["selective_accuracy"], "p4": p4["selective_accuracy"],
                             "selective_gain": selective_gain,
                             "no_protected_degradation": no_degradation},
        "protected_metrics": protected,
        "success_criteria": success, "all_success": all_success,
        "competition": {k: v for k, v in comp.items() if k not in ("per_competition", "changed_cases")},
        "statistics": {"mcnemar_answer_correct_p4_vs_p0": mcnemar},
        "verdict": verdict,
        "_per_competition": comp["per_competition"], "_changed_cases": comp["changed_cases"],
    }


def main():
    out = run()
    save = {k: v for k, v in out.items() if not k.startswith("_")}
    with open(os.path.join(OUT_DIR, "PRIORITIZATION_RESULTS.json"), "w") as f:
        json.dump(save, f, indent=2, default=str)
    with open(os.path.join(OUT_DIR, "PRIORITIZATION_COMPETITIONS.json"), "w") as f:
        json.dump({"per_competition": out["_per_competition"],
                   "changed_cases": out["_changed_cases"]}, f, indent=2, default=str)
    print(json.dumps({"byte_identical_reps": out["byte_identical_reps"],
                      "primary_endpoint": out["primary_endpoint"],
                      "success_criteria": out["success_criteria"],
                      "competition": out["competition"],
                      "verdict": out["verdict"]}, indent=2, default=str))
    return out


if __name__ == "__main__":
    main()
