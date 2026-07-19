#!/usr/bin/env python3
"""
Repaired-measurement runner.

    python -m agentic.hybrid_handover.resolution.measurement.run_measurement

Evaluates the deterministic reference resolvers under the owner-clean stage
metrics (Discovery / Classification / Governance Mode G / Packet Mode P),
abstention decision metrics, parser-owned metrics, the hidden layer, and the
adversarial re-validation. Writes MEASUREMENT_RESULTS.json. Reads only; modifies
no resolver and nothing frozen.
"""

from __future__ import annotations

import json
import os

from agentic.hybrid_handover.evaluation.corpus import all_cases
from agentic.hybrid_handover.resolution.resolvers import ALL_RESOLVERS, RESOLVER_ORDER

from .abstention import abstention_metrics
from .adversarial_revalidation import revalidate
from .hidden import run_hidden
from .owners import METRIC_OWNER, assert_single_owner
from .parser_metrics import parser_metrics
from .stage_metrics import discovery_classification, governance_modeG, packet_modeP

OUT_DIR = os.path.dirname(__file__)


def evaluate(resolver, cases):
    m = {}
    m.update(discovery_classification(resolver, cases))
    gg = governance_modeG(resolver, cases); m["governance_accuracy_modeG"] = gg["governance_accuracy_modeG"]
    pp = packet_modeP(resolver, cases); m["packet_realization_accuracy_modeP"] = pp["packet_realization_accuracy_modeP"]
    ab = abstention_metrics(resolver, cases)
    for k in ("abstention_precision", "abstention_recall", "answer_coverage", "selective_accuracy"):
        m[k] = ab[k]
    m["_abstention_counts"] = ab["_counts"]
    return m


def run():
    assert_single_owner()
    cases = all_cases()
    out = {"benchmark": "SEEB relationship-resolution measurement (repaired)",
           "synthetic": True, "metric_owner": METRIC_OWNER, "resolvers": {}}
    for rname in RESOLVER_ORDER:
        out["resolvers"][rname] = evaluate(ALL_RESOLVERS[rname](), cases)
    out["parser"] = parser_metrics()
    out["hidden"] = {rname: run_hidden(ALL_RESOLVERS[rname]()) for rname in RESOLVER_ORDER}
    out["adversarial_revalidation"] = revalidate()
    return out


def main():
    out = run()
    with open(os.path.join(OUT_DIR, "MEASUREMENT_RESULTS.json"), "w") as f:
        json.dump(out, f, indent=2, default=str)

    caps = ["discovery_recall", "discovery_precision", "classification_accuracy",
            "governance_accuracy_modeG", "packet_realization_accuracy_modeP",
            "abstention_precision", "abstention_recall", "answer_coverage", "selective_accuracy"]
    print("=" * 84)
    print("RELATIONSHIP RESOLUTION — REPAIRED MEASUREMENT (owner-clean; synthetic)")
    print("=" * 84)
    print(f"{'metric':38s} {'owner':16s} " + " ".join(f"{r[:11]:>11s}" for r in RESOLVER_ORDER))
    for c in caps:
        line = f"{c:38s} {METRIC_OWNER[c][:16]:16s} "
        for rname in RESOLVER_ORDER:
            v = out["resolvers"][rname].get(c)
            line += f"{('n/a' if v is None else f'{v:.2f}'):>11s} "
        print(line)
    p = out["parser"]
    print(f"\nParser (SemanticParser, resolver-independent): negation={p['parser_negation_accuracy']} type={p['parser_type_accuracy']}")

    print("\nHidden layer — endpoint discovery by family:")
    for rname in RESOLVER_ORDER:
        rows = out["hidden"][rname]
        fams = {}
        for r in rows:
            fams.setdefault(r["family"], [0, 0])
            fams[r["family"]][1] += 1
            fams[r["family"]][0] += int(r["endpoint_discovered"])
        s = "  ".join(f"{f}:{v[0]}/{v[1]}" for f, v in sorted(fams.items()))
        print(f"    {rname:16s} {s}")

    rv = out["adversarial_revalidation"]
    print("\nAdversarial re-validation:")
    print(f"    gamed capability metrics (cheat >=0.90): {rv['gamed_capability_metrics'] or 'NONE'}")
    print(f"    always_abstain scores poorly overall: {rv['always_abstain_scores_poorly']}")
    print(f"\nWrote {os.path.join(OUT_DIR, 'MEASUREMENT_RESULTS.json')}")


if __name__ == "__main__":
    main()
