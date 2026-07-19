#!/usr/bin/env python3
"""
Single-command resolution evaluation.

    python -m agentic.hybrid_handover.resolution.run

Writes RESOLUTION_RESULTS.json + PER_CASE_RESOLUTION.csv and prints a summary.
Reads SEEB; modifies nothing.
"""

from __future__ import annotations

import csv
import json
import os

from .harness import run_all
from .modes import MODES
from .resolvers import RESOLVER_ORDER

OUT_DIR = os.path.dirname(__file__)

KEY_METRICS = [
    "relationship_edge_recall", "relationship_edge_precision",
    "relationship_type_accuracy", "precedence_resolution_accuracy",
    "override_resolution_accuracy", "definition_resolution_accuracy",
    "negation_interpretation_accuracy", "cycle_detection_accuracy",
    "version_selection_accuracy", "abstention_accuracy",
]


def main():
    out = run_all()
    with open(os.path.join(OUT_DIR, "RESOLUTION_RESULTS.json"), "w") as f:
        json.dump(out, f, indent=2)

    rows = []
    for rname in RESOLVER_ORDER:
        for mode in MODES:
            for pc in out["resolvers"][rname][mode]["per_case"]:
                rows.append({"resolver": rname, "mode": mode, "case_id": pc["case_id"],
                             "correct": int(pc["correct"]), "failure_stage": pc["failure_stage"],
                             "abstained": int(pc["abstained"]),
                             "edges": len(pc["relationship_graph"])})
    with open(os.path.join(OUT_DIR, "PER_CASE_RESOLUTION.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    print("=" * 78)
    print("SEEB v1.0.0 — RELATIONSHIP RESOLUTION LAYER (component metrics, synthetic)")
    print("=" * 78)
    for mode in MODES:
        print(f"\n--- Mode {mode} ---")
        print(f"{'metric':38s} " + " ".join(f"{r[:13]:>14s}" for r in RESOLVER_ORDER))
        for m in KEY_METRICS:
            line = f"{m:38s} "
            for rname in RESOLVER_ORDER:
                v = out["resolvers"][rname][mode]["metrics"].get(m)
                line += f"{('n/a' if v is None else f'{v:.2f}'):>14s} "
            print(line)
        print(f"{'cases correct (end-to-end)':38s} " + " ".join(
            f"{str(out['resolvers'][r][mode]['n_correct'])+'/16':>14s}" for r in RESOLVER_ORDER))
        print(f"{'failure attribution':38s}")
        for rname in RESOLVER_ORDER:
            fa = out["resolvers"][rname][mode]["failure_attribution"]
            fa = {k: v for k, v in fa.items() if k != "none"}
            print(f"    {rname:20s} {fa}")

    print("\n--- SEEB pipeline metrics (unchanged; via frozen aggregator, mode B) ---")
    pm_keys = ["precedence_recall", "packet_sufficiency", "unsafe_handover_rate",
               "fail_closed_rate", "routing_accuracy"]
    print(f"{'pipeline metric':38s} " + " ".join(f"{r[:13]:>14s}" for r in RESOLVER_ORDER))
    for k in pm_keys:
        line = f"{k:38s} "
        for rname in RESOLVER_ORDER:
            v = out["resolvers"][rname]["pipeline_metrics_seeb_B_bm25"].get(k)
            line += f"{('n/a' if v is None else f'{v}'):>14s} "
        print(line)

    print(f"\nWrote:\n  {os.path.join(OUT_DIR,'RESOLUTION_RESULTS.json')}"
          f"\n  {os.path.join(OUT_DIR,'PER_CASE_RESOLUTION.csv')}")


if __name__ == "__main__":
    main()
