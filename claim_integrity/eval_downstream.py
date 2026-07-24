"""Phase 18 (downstream impact) + Phase 19 (error propagation) evaluation. Deterministic. Writes
eval_results/downstream.json."""
from __future__ import annotations

import json
import os
from dataclasses import asdict

from . import dataset, baselines, downstream


def run() -> dict:
    exs = [asdict(e) for e in dataset.all_examples()]
    methods = {}
    for name, fn in baselines.BASELINES.items():
        methods[name] = downstream.score_method(exs, fn)
    return {"corpus": dataset.DATASET_VERSION, "n_examples": len(exs),
            "phase18_downstream": methods,
            "phase19_error_propagation": downstream.propagation_matrix(exs)}


def main() -> None:
    r = run()
    out = os.path.join(os.path.dirname(__file__), "eval_results", "downstream.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)
    print(f"corpus={r['corpus']} n={r['n_examples']}")
    print("\nPhase 18 - downstream impact (unsafe delivery is the primary safety endpoint):")
    print(f"  {'method':24} {'unsafe_deliv':>12} {'false_rej':>10} {'evq_altered':>12}")
    for name, s in sorted(r["phase18_downstream"].items(), key=lambda x: x[1]["unsafe_delivery_rate"]):
        print(f"  {name:24} {s['unsafe_delivery_rate']:>12.3f} {s['false_rejection_rate']:>10.3f} "
              f"{s['evidence_query_altered_rate']:>12.3f}")
    print("\nPhase 19 - error propagation (does the drift reach unsafe delivery?):")
    print(f"  {'perturbation':24} {'unsafe_deliv':>12} {'false_rej':>10} {'evq_altered':>12}")
    for kind, s in r["phase19_error_propagation"].items():
        print(f"  {kind:24} {s['unsafe_delivery_rate']:>12.3f} {s['false_rejection_rate']:>10.3f} "
              f"{s['evidence_query_altered_rate']:>12.3f}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
