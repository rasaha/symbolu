#!/usr/bin/env python3
"""
Proposal Validation Experiment v0.1 — orchestrator.

Runs the preregistered ablations V0–V4 on the visible corpus (frozen measurement
package) and the frozen 60-case Hidden Relationship Corpus Pilot v0.2 (reusing the
v0.1 `hidden_metrics`, `hidden_data`, and `stats` modules UNCHANGED). Fully
deterministic; two repetitions must be byte-identical.

Primary endpoint: recovery of discovery precision subject to ≤0.03 recall loss vs V0
(= Hybrid v0.1). Also tallies the per-edge rejection taxonomy on the hidden set,
flagging each rejected edge as removing an incorrect proposal (pair ∉ gold) or
mistakenly rejecting a correct one (pair ∈ gold).
"""

from __future__ import annotations

import json
import os

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution.measurement.stage_metrics import discovery_classification

from ..experiment import hidden_metrics, stats
from ..experiment.hidden_data import hidden_cases
from .hybrid_resolver_v2 import HybridRelationshipResolverV2
from .validator import ABLATIONS, CATEGORIES, validate

OUT_DIR = os.path.dirname(__file__)
ABLATION_ORDER = ["V0_none", "V1_dedupe_only", "V2_evidence_only",
                  "V3_authority_temporal", "V4_full"]
RECALL_LOSS_MARGIN = 0.03


def _resolver(name):
    return HybridRelationshipResolverV2(ABLATIONS[name])


def _bootstrap_precision(pc_a, pc_b, iters=stats.BOOTSTRAP_ITERS, seed=stats.BOOTSTRAP_SEED):
    """Paired bootstrap CI for discovery-precision difference (a − b), recomputed
    over resampled cases (precision is a ratio, so resample then recompute)."""
    import random
    cids = list(pc_a)
    n = len(cids)

    def prec(pc, idxs):
        hit = sum(pc[cids[i]]["discovery_hit"] for i in idxs)
        pred = sum(pc[cids[i]]["pred_pairs"] for i in idxs)
        return hit / pred if pred else 0.0
    allidx = list(range(n))
    obs = prec(pc_a, allidx) - prec(pc_b, allidx)
    rng = random.Random(seed)
    diffs = []
    for _ in range(iters):
        s = [rng.randrange(n) for _ in allidx]
        diffs.append(prec(pc_a, s) - prec(pc_b, s))
    diffs.sort()
    lo = diffs[int((stats.CI_ALPHA / 2) * iters)]
    hi = diffs[int((1 - stats.CI_ALPHA / 2) * iters) - 1]
    return {"observed_diff": round(obs, 4), "ci95": [round(lo, 4), round(hi, 4)],
            "excludes_zero": bool(lo > 0 or hi < 0), "n": n, "iters": iters, "seed": seed}


def _rejection_taxonomy(hcases):
    """Run V4 over the hidden set; tally rejections by category and by correctness."""
    v1 = HybridRelationshipResolverV2(ABLATIONS["V4_full"])._v1  # v0.1 proposal generator
    from agentic.hybrid_handover.resolution.parse import parse_nodes
    counts = {c: 0 for c in CATEGORIES}
    incorrect_removed = correct_rejected = 0
    accepted_correct = accepted_incorrect = 0
    per_edge = []
    for case in hcases:
        gold_pairs = {(s, d) for (s, _t, d) in case["gold"]["edges"]}
        nodes = parse_nodes(case["evidence"])
        edges, conf, prov = v1._propose(nodes)
        edges = [e for e in edges if prov.get(e.triple())]
        validated, records = validate(nodes, edges, conf, prov, ABLATIONS["V4_full"])
        val_pairs = {(e.src, e.dst) for e in validated}
        for r in records:
            pair = (r["src"], r["dst"])
            is_gold = pair in gold_pairs
            if r["decision"] == "reject":
                counts[r["rejection_reason"]] = counts.get(r["rejection_reason"], 0) + 1
                if is_gold and pair not in val_pairs:
                    correct_rejected += 1
                elif not is_gold:
                    incorrect_removed += 1
            else:
                accepted_correct += int(is_gold)
                accepted_incorrect += int(not is_gold)
            per_edge.append({"cid": case["cid"], **r, "pair_in_gold": is_gold})
    return {"counts": counts, "incorrect_removed": incorrect_removed,
            "correct_rejected": correct_rejected,
            "accepted_correct": accepted_correct, "accepted_incorrect": accepted_incorrect,
            "per_edge": per_edge}


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


def run():
    rep1 = _one_rep()
    rep2 = _one_rep()
    byte_identical = (json.dumps(rep1, sort_keys=True, default=str)
                      == json.dumps(rep2, sort_keys=True, default=str))

    hidden = rep1["hidden"]
    v0, v4 = hidden["V0_none"], hidden["V4_full"]
    recall_loss = round((v0["discovery_recall"] or 0) - (v4["discovery_recall"] or 0), 4)
    precision_gain = round((v4["discovery_precision"] or 0) - (v0["discovery_precision"] or 0), 4)
    selective_gain = round((v4["selective_accuracy"] or 0) - (v0["selective_accuracy"] or 0), 4)

    primary = {
        "definition": "recover discovery precision with recall loss <= 0.03 vs V0 (Hybrid v0.1)",
        "v0_precision": v0["discovery_precision"], "v4_precision": v4["discovery_precision"],
        "precision_gain": precision_gain,
        "v0_recall": v0["discovery_recall"], "v4_recall": v4["discovery_recall"],
        "recall_loss": recall_loss, "recall_loss_margin": RECALL_LOSS_MARGIN,
        "recall_loss_within_margin": recall_loss <= RECALL_LOSS_MARGIN,
        "endpoint_met": (precision_gain > 0 and recall_loss <= RECALL_LOSS_MARGIN),
    }

    # success criteria (preregistered)
    gov_unchanged = v4["governance_accuracy_modeG"] == v0["governance_accuracy_modeG"]
    pkt_unchanged = v4["packet_realization_accuracy_modeP"] == v0["packet_realization_accuracy_modeP"]
    unsafe_ok = v4["unsafe_answers"] <= v0["unsafe_answers"]
    success = {
        "discovery_precision_improves": precision_gain > 0,
        "recall_loss_within_margin": recall_loss <= RECALL_LOSS_MARGIN,
        "selective_accuracy_improves": selective_gain > 0,
        "unsafe_not_increased": unsafe_ok,
        "governance_unchanged": gov_unchanged,
        "packet_unchanged": pkt_unchanged,
    }
    all_success = all(success.values())

    # stats: V4 vs V0
    mcnemar_disc = stats.mcnemar_exact(
        [rep1["hidden_pc"]["V4_full"][c]["discovery_complete"] for c in rep1["hidden_pc"]["V4_full"]],
        [rep1["hidden_pc"]["V0_none"][c]["discovery_complete"] for c in rep1["hidden_pc"]["V0_none"]])
    boot_prec = _bootstrap_precision(rep1["hidden_pc"]["V4_full"], rep1["hidden_pc"]["V0_none"])

    taxonomy = _rejection_taxonomy(hidden_cases())

    if success["discovery_precision_improves"] and taxonomy["accepted_correct"] > 0 and recall_loss <= 0.5:
        if all_success:
            verdict = "PROMISING VALIDATION LAYER"
        elif recall_loss > RECALL_LOSS_MARGIN:
            verdict = "NO CLEAR SIGNAL (precision bought with recall)"
        else:
            verdict = "PROMISING VALIDATION LAYER (with caveats)"
    else:
        verdict = "FALSIFIED (validation removes genuine discovery)" \
            if recall_loss > 0.5 else "NO CLEAR SIGNAL"

    return {
        "study": "Proposal Validation Experiment v0.1",
        "resolver_under_test": "HybridRelationshipResolver Experimental v0.2",
        "deterministic": True, "repetitions": 2, "byte_identical_reps": byte_identical,
        "visible": rep1["visible"], "hidden": hidden,
        "primary_endpoint": primary, "success_criteria": success, "all_success": all_success,
        "statistics": {"mcnemar_discovery_complete_v4_vs_v0": mcnemar_disc,
                       "bootstrap_precision_v4_minus_v0": boot_prec},
        "rejection_taxonomy": {k: v for k, v in taxonomy.items() if k != "per_edge"},
        "verdict": verdict,
        "_per_edge": taxonomy["per_edge"],
    }


def main():
    out = run()
    to_save = {k: v for k, v in out.items() if k != "_per_edge"}
    with open(os.path.join(OUT_DIR, "VALIDATION_RESULTS.json"), "w") as f:
        json.dump(to_save, f, indent=2, default=str)
    with open(os.path.join(OUT_DIR, "VALIDATION_EDGE_RECORDS.json"), "w") as f:
        json.dump(out["_per_edge"], f, indent=2, default=str)
    print(json.dumps({"byte_identical_reps": out["byte_identical_reps"],
                      "primary_endpoint": out["primary_endpoint"],
                      "success_criteria": out["success_criteria"],
                      "verdict": out["verdict"],
                      "rejection_taxonomy": out["rejection_taxonomy"]}, indent=2, default=str))
    return out


if __name__ == "__main__":
    main()
