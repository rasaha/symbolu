#!/usr/bin/env python3
"""
Capability-isolation experiment (analysis only — reads SEEB, modifies nothing).

For every SEEB case:
  1. Establish the strongest-conventional baseline status (BM25 ≈ embedding ≈
     hybrid on v1's short corpora — BM25 is used as the representative).
  2. Run the OracleRetriever counterfactual (perfect retrieval + shared reasoning).
  3. Classify:
       ALREADY SOLVED        — baseline already solves it (not "unresolved").
       RETRIEVAL LIMITED     — oracle retrieval solves it → the deficit was retrieval.
       RETRIEVAL INSUFFICIENT — oracle retrieval still fails → deficit is NOT retrieval.

    python -m agentic.hybrid_handover.analysis.capability_isolation
"""

from __future__ import annotations

import json
import os

from agentic.hybrid_handover.baselines.bm25 import BM25Extractor
from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.evaluation.harness import evaluate_case
from agentic.hybrid_handover.evaluation.validators import DEFAULT_VALIDATORS

from .annotations import ANNOTATIONS
from .oracle import OracleRetriever

OUT_DIR = os.path.dirname(__file__)


def _solved(r) -> bool:
    """A case is solved iff its expected outcome is achieved with complete,
    sufficient evidence (completeness-first)."""
    if r.expected_routing == "REFUSE":
        return r.system_decision == "REFUSE"
    if r.system_decision != "ESCALATE":
        return False
    complete = (
        r.decisive[0] == r.decisive[1]
        and r.defeater[0] == r.defeater[1]
        and r.definition[0] == r.definition[1]
        and r.precedence[0] == r.precedence[1]
    )
    return (not r.unsafe_handover) and complete and r.packet_sufficient


def run_all():
    bm25 = BM25Extractor()
    out = {"benchmark": "SEEB", "benchmark_version": "1.0.0", "synthetic": True, "cases": []}
    for case in all_cases():
        base_r = evaluate_case(case, bm25, DEFAULT_VALIDATORS, "augmented")
        orc_r = evaluate_case(case, OracleRetriever(case), DEFAULT_VALIDATORS, "augmented")
        base_solved = _solved(base_r)
        oracle_solved = _solved(orc_r)

        if base_solved:
            classification = "ALREADY SOLVED"
        elif oracle_solved:
            classification = "RETRIEVAL LIMITED"
        else:
            classification = "RETRIEVAL INSUFFICIENT"

        ann = ANNOTATIONS[case.case_id]
        out["cases"].append({
            "case_id": case.case_id,
            "taxonomy_level": ann["level"],
            "category": ann["category"],
            "baseline_solved": base_solved,
            "oracle_solved": oracle_solved,
            "classification": classification,
            "requires_graph_reasoning": ann["graph_required"],
            "why": ann["why"],
            "baseline": {
                "decision": base_r.system_decision, "expected": base_r.expected_routing,
                "decisive": list(base_r.decisive), "defeater": list(base_r.defeater),
                "definition": list(base_r.definition), "precedence": list(base_r.precedence),
                "unsafe": base_r.unsafe_handover, "sufficient": base_r.packet_sufficient,
            },
            "oracle": {
                "decision": orc_r.system_decision,
                "decisive": list(orc_r.decisive), "defeater": list(orc_r.defeater),
                "definition": list(orc_r.definition), "precedence": list(orc_r.precedence),
                "unsafe": orc_r.unsafe_handover, "sufficient": orc_r.packet_sufficient,
            },
        })

    unresolved = [c for c in out["cases"] if c["classification"] != "ALREADY SOLVED"]
    out["summary"] = {
        "n_cases": len(out["cases"]),
        "already_solved": sum(c["classification"] == "ALREADY SOLVED" for c in out["cases"]),
        "retrieval_limited": sum(c["classification"] == "RETRIEVAL LIMITED" for c in out["cases"]),
        "retrieval_insufficient": sum(c["classification"] == "RETRIEVAL INSUFFICIENT" for c in out["cases"]),
        "unresolved_case_ids": [c["case_id"] for c in unresolved],
        "retrieval_insufficient_ids": [c["case_id"] for c in out["cases"] if c["classification"] == "RETRIEVAL INSUFFICIENT"],
        "retrieval_saturated": all(c["classification"] != "RETRIEVAL LIMITED" for c in out["cases"]),
    }
    return out


def main():
    out = run_all()
    with open(os.path.join(OUT_DIR, "CAPABILITY_ISOLATION.json"), "w") as f:
        json.dump(out, f, indent=2)
    s = out["summary"]
    print("=" * 78)
    print("SEEB v1.0.0 — CAPABILITY ISOLATION (oracle-retrieval counterfactual)")
    print("=" * 78)
    print(f"{'case':26s} {'level':6s} {'baseline':9s} {'oracle':7s} classification")
    for c in out["cases"]:
        print(f"{c['case_id']:26s} L{c['taxonomy_level']:<5d} "
              f"{'SOLVED' if c['baseline_solved'] else 'fail':9s} "
              f"{'SOLVED' if c['oracle_solved'] else 'fail':7s} {c['classification']}")
    print()
    print(f"already solved by baseline      : {s['already_solved']}")
    print(f"RETRIEVAL LIMITED (oracle fixes): {s['retrieval_limited']}")
    print(f"RETRIEVAL INSUFFICIENT          : {s['retrieval_insufficient']}  {s['retrieval_insufficient_ids']}")
    print()
    print(f"Retrieval component SATURATED by conventional baselines: {s['retrieval_saturated']}")


if __name__ == "__main__":
    main()
