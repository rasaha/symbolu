"""Evaluate the reference EvidenceAssurance component (Phase 13) on ea_corpus_v1_1.

Reports the same safety endpoints as the baselines (correlated-failure escape, overall escape,
false block) plus disposition-level accuracy vs gold and a component-vs-gold confusion summary.
Deterministic. Writes eval_results/assurance_v1.json. Touches no prior-track artifact.
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from dataclasses import asdict

from . import dataset, assurance
from .taxonomy import delivered_as_supported

TRAP = {"CORRELATED_FAILURE", "ADVERSARIAL_PROVENANCE"}


def evaluate() -> dict:
    cases = [asdict(c) for c in dataset.all_cases()]
    gold_supported = [delivered_as_supported(c["gold_state"]) for c in cases]
    n_unsupported = sum(1 for g in gold_supported if not g)
    n_supported = sum(1 for g in gold_supported if g)
    trap_idx = [i for i, c in enumerate(cases) if c["partition"] in TRAP]

    escape = false_block = exact = 0
    trap_escape = 0
    confusion = defaultdict(Counter)          # gold -> Counter(predicted)
    unsupported_states = Counter()            # what the component calls trap cases

    for i, c in enumerate(cases):
        res = assurance.assess(c)
        pred_supported = delivered_as_supported(res.state)
        if res.state == c["gold_state"]:
            exact += 1
        if pred_supported and not gold_supported[i]:
            escape += 1
        if not pred_supported and gold_supported[i]:
            false_block += 1
        confusion[c["gold_state"]][res.state] += 1
        if c["partition"] in TRAP:
            unsupported_states[res.state] += 1
            if pred_supported:
                trap_escape += 1

    return {
        "corpus": dataset.DATASET_VERSION,
        "n_cases": len(cases),
        "endpoints": {
            "correlated_failure_escape": round(trap_escape / len(trap_idx), 4),
            "overall_escape": round(escape / n_unsupported, 4),
            "false_block": round(false_block / n_supported, 4),
            "disposition_exact_accuracy": round(exact / len(cases), 4),
        },
        "trap_disposition_calls": dict(unsupported_states),
        "confusion": {g: dict(preds) for g, preds in confusion.items()},
    }


def main() -> None:
    r = evaluate()
    out = os.path.join(os.path.dirname(__file__), "eval_results", "assurance_v1.json")
    with open(out, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)
    e = r["endpoints"]
    print(f"corpus={r['corpus']} n={r['n_cases']}")
    print(f"  correlated_failure_escape : {e['correlated_failure_escape']:.3f}  (primary safety, lower better)")
    print(f"  overall_escape            : {e['overall_escape']:.3f}")
    print(f"  false_block               : {e['false_block']:.3f}  (co-primary, lower better)")
    print(f"  disposition_exact_accuracy: {e['disposition_exact_accuracy']:.3f}")
    print(f"\n  how the component labels the 156 trap cases (all gold-unsupported):")
    for state, n in sorted(r["trap_disposition_calls"].items(), key=lambda x: -x[1]):
        print(f"    {state:26} {n}")
    print(f"\n  confusion (gold -> predicted):")
    for gold, preds in sorted(r["confusion"].items()):
        parts = ", ".join(f"{k}:{v}" for k, v in sorted(preds.items(), key=lambda x: -x[1]))
        print(f"    {gold:26} -> {parts}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
