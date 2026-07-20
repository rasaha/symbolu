#!/usr/bin/env python3
"""
Post-run analysis for the Exploratory Resolver Study v0.1. Runs ONLY after every
preregistered evaluation is complete (per the preregistration, no per-case hidden
failure is inspected before then). Deterministic; recomputing is byte-identical.

Produces:
  * generalization slices (seed vs pilot; by capability; by difficulty; by gold
    edge-type; by wording/variation family; negative-control subset) for
    GraphTraversal vs Hybrid — macro + discovery F1;
  * per-case failure attribution to exactly one primary stage;
  * a reproducibility record.
"""

from __future__ import annotations

import json
import os

from agentic.hybrid_handover.resolution.resolvers import GraphTraversalResolver

from . import hidden_metrics
from .hidden_data import hidden_cases
from .hybrid_resolver import HybridRelationshipResolver

HERE = os.path.dirname(__file__)


def _macro(records):
    from .run_experiment import _macro_from_records
    return round(_macro_from_records(records), 4)


def _disc_f1(records):
    hit = sum(r["discovery_hit"] for r in records)
    pred = sum(r["pred_pairs"] for r in records)
    ref = sum(r["gold_pairs"] for r in records)
    p = hit / pred if pred else 0.0
    rc = hit / ref if ref else 0.0
    return round(2 * p * rc / (p + rc), 4) if (p + rc) else 0.0


def _slice(pc: dict, keep) -> list[dict]:
    return [dict(v, cid=k) for k, v in pc.items() if keep(v)]


def _attribute(rec: dict) -> str:
    """Map an incorrect case to exactly one PRIMARY failure stage."""
    if not rec["discovery_complete"]:
        return "relationship_discovery"          # missed a required edge
    if rec["pred_pairs"] > rec["gold_pairs"]:
        return "relationship_discovery_overproposal"
    if rec["class_tot"] and rec["class_ok"] < rec["class_tot"]:
        return "relationship_classification"
    if rec["owned"] and rec["governanceG"] is False:
        return "governance_application"
    if rec["owned"] and rec["packetP"] is False:
        return "packet_realization"
    if rec["answered"] and rec["answer_correct"] is False:
        return "packet_realization"
    return "none"


def run() -> dict:
    cases = hidden_cases()
    gt = hidden_metrics.evaluate(GraphTraversalResolver(), cases)["per_case"]
    hy = hidden_metrics.evaluate(HybridRelationshipResolver(), cases)["per_case"]

    def slices_for(pc):
        caps = sorted({c for v in pc.values() for c in v["capability"]})
        diffs = sorted({v["difficulty"] for v in pc.values() if v["difficulty"]})
        etypes = sorted({e for v in pc.values() for e in v["edge_types"]})
        varis = sorted({x for v in pc.values() for x in v["variation"]}) or ["<none>"]
        out = {
            "by_source": {s: {"n": len(_slice(pc, lambda v, s=s: v["source"] == s)),
                              "macro": _macro(_slice(pc, lambda v, s=s: v["source"] == s)),
                              "disc_f1": _disc_f1(_slice(pc, lambda v, s=s: v["source"] == s))}
                          for s in ("seed", "pilot")},
            "by_capability": {c: {"n": len(_slice(pc, lambda v, c=c: c in v["capability"])),
                                  "macro": _macro(_slice(pc, lambda v, c=c: c in v["capability"])),
                                  "disc_f1": _disc_f1(_slice(pc, lambda v, c=c: c in v["capability"]))}
                              for c in caps},
            "by_difficulty": {dv: {"n": len(_slice(pc, lambda v, dv=dv: v["difficulty"] == dv)),
                                   "macro": _macro(_slice(pc, lambda v, dv=dv: v["difficulty"] == dv)),
                                   "disc_f1": _disc_f1(_slice(pc, lambda v, dv=dv: v["difficulty"] == dv))}
                              for dv in diffs},
            "by_gold_edge_type": {e: {"n": len(_slice(pc, lambda v, e=e: e in v["edge_types"])),
                                      "disc_f1": _disc_f1(_slice(pc, lambda v, e=e: e in v["edge_types"]))}
                                  for e in etypes},
            "by_variation": {x: {"n": len(_slice(pc, lambda v, x=x: x in (v["variation"] or ["<none>"]))),
                                 "macro": _macro(_slice(pc, lambda v, x=x: x in (v["variation"] or ["<none>"])))}
                             for x in varis},
            "negative_control": {"n": len(_slice(pc, lambda v: v["negative_control"])),
                                 "macro": _macro(_slice(pc, lambda v: v["negative_control"]))},
        }
        return out

    # failure attribution (per resolver)
    def attribution(pc):
        counts = {}
        rows = []
        for cid, v in pc.items():
            stage = _attribute(v)
            rows.append({"cid": cid, "primary_stage": stage,
                         "source": v["source"], "difficulty": v["difficulty"]})
            if stage != "none":
                counts[stage] = counts.get(stage, 0) + 1
        return {"counts": counts, "rows": rows}

    out = {
        "study": "Exploratory Resolver Study v0.1",
        "generalization": {"graph_traversal": slices_for(gt), "hybrid_relationship": slices_for(hy)},
        "failure_attribution": {"graph_traversal": attribution(gt),
                                "hybrid_relationship": attribution(hy)},
    }
    return out


def main():
    out = run()
    with open(os.path.join(HERE, "EXPERIMENT_ANALYSIS.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)
    g = out["generalization"]
    print("seed/pilot macro  graph:", {k: v["macro"] for k, v in g["graph_traversal"]["by_source"].items()})
    print("seed/pilot macro hybrid:", {k: v["macro"] for k, v in g["hybrid_relationship"]["by_source"].items()})
    print("hybrid failure stages:", out["failure_attribution"]["hybrid_relationship"]["counts"])
    return out


if __name__ == "__main__":
    main()
