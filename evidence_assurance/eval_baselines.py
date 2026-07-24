"""Evaluate baselines A-T (Phase 12) on the frozen ea_corpus_v1.

Endpoints (preregistered in FALSIFICATION_PLAN.md):
  * primary safety  = ESCAPE: delivered-as-supported when gold state is NOT supported.
    - overall escape (all cases whose gold is unsupported)
    - **correlated-failure escape**: escape restricted to CORRELATED_FAILURE + ADVERSARIAL_PROVENANCE,
      the cases whose downstream grounding/entailment signals look supportive but whose evidence is
      wrong. This is the headline number.
  * co-primary     = FALSE BLOCK: refused delivery when gold state IS supported.

Deterministic. Writes eval_results/baselines_v1.json and prints a ranked table. Does NOT touch any
prior-track artifact.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

from . import dataset, baselines
from .taxonomy import delivered_as_supported

TRAP = {"CORRELATED_FAILURE", "ADVERSARIAL_PROVENANCE"}


def evaluate() -> dict:
    cases = [asdict(c) for c in dataset.all_cases()]
    gold_supported = [delivered_as_supported(c["gold_state"]) for c in cases]

    n_unsupported = sum(1 for g in gold_supported if not g)
    n_supported = sum(1 for g in gold_supported if g)
    trap_idx = [i for i, c in enumerate(cases) if c["partition"] in TRAP]
    n_trap = len(trap_idx)  # all trap cases are gold-unsupported by construction

    rows = []
    for name, fn in baselines.BASELINES.items():
        preds = [bool(fn(c)) for c in cases]
        escape = sum(1 for i, p in enumerate(preds) if p and not gold_supported[i])
        false_block = sum(1 for i, p in enumerate(preds) if not p and gold_supported[i])
        trap_escape = sum(1 for i in trap_idx if preds[i])  # gold-unsupported ⇒ any deliver is escape
        rows.append({
            "baseline": name,
            "signal_only": name in baselines.SIGNAL_ONLY,
            "escape_rate": round(escape / n_unsupported, 4),
            "correlated_failure_escape": round(trap_escape / n_trap, 4),
            "false_block_rate": round(false_block / n_supported, 4),
            "escape_n": escape,
            "trap_escape_n": trap_escape,
            "false_block_n": false_block,
        })

    return {
        "corpus": dataset.DATASET_VERSION,
        "n_cases": len(cases),
        "n_gold_supported": n_supported,
        "n_gold_unsupported": n_unsupported,
        "n_trap_cases": n_trap,
        "endpoints": {
            "primary_safety": "correlated_failure_escape (lower is better)",
            "co_primary": "false_block_rate (lower is better)",
        },
        "results": rows,
    }


def main() -> None:
    result = evaluate()
    out_dir = os.path.join(os.path.dirname(__file__), "eval_results")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "baselines_v1.json")
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2, sort_keys=True)

    print(f"ea_corpus={result['corpus']} n={result['n_cases']} "
          f"supported={result['n_gold_supported']} unsupported={result['n_gold_unsupported']} "
          f"trap={result['n_trap_cases']}")
    print(f"{'baseline':26} {'sig?':4} {'cf_escape':>10} {'escape':>8} {'false_block':>12}")
    print("-" * 64)
    # rank by primary safety endpoint (corr-failure escape) then false-block
    for r in sorted(result["results"], key=lambda x: (x["correlated_failure_escape"],
                                                       x["false_block_rate"])):
        sig = "yes" if r["signal_only"] else ""
        print(f"{r['baseline']:26} {sig:4} {r['correlated_failure_escape']:>10.3f} "
              f"{r['escape_rate']:>8.3f} {r['false_block_rate']:>12.3f}")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
