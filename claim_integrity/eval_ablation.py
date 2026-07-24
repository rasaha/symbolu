"""Cost proxy (Phase 21), ablation (Phase 22), complexity comparators (Phase 23). Deterministic.
Writes eval_results/ablation.json."""
from __future__ import annotations

import json
import os
import re
from dataclasses import asdict

from . import dataset, downstream, claims
from .claims import ALL_FEATURES

# Phase 21: probe cost per component stage (deterministic proxy; not wall-clock).
STAGE_COST = {"span_detection": 1, "segmentation": 1, "reference_resolution": 2, "safe_split": 2,
              "nonassertive_filter": 1, "dimension_detect": 3, "validation": 4, "audit": 1}


def _component(enabled):
    def m(e):
        return [c.text for c in claims.decompose(e["original_text"], enabled=enabled).claims]
    return m


# Phase 23: deliberately simple comparators
def sc1_sentence_negation(e):
    # sentence split; negation preserved automatically by not stripping
    return re.split(r"(?<=[.!?])\s+", e["original_text"].strip())

def sc2_clause_qualifier(e):
    out = []
    for s in re.split(r"(?<=[.!?])\s+", e["original_text"].strip()):
        for c in re.split(r",\s+", s):
            out.append(c.rstrip(". ") + ".")
    return out

def sc3_preserve_unless_conj(e):
    t = e["original_text"].strip()
    if " and " in t and " unless " not in t and " except " not in t:
        return re.split(r"(?<=[.!?])\s+", t)
    return [t]


def run() -> dict:
    exs = [asdict(e) for e in dataset.all_examples()]

    # Phase 22 ablation: full, then leave-one-out
    ablation = {}
    ablation["FULL"] = downstream.score_method(exs, _component(ALL_FEATURES))
    for feat in ALL_FEATURES:
        ablation[f"-{feat}"] = downstream.score_method(exs, _component(ALL_FEATURES - {feat}))

    # Phase 23 complexity comparators + the full component
    comparators = {
        "SC1_sentence+negation": downstream.score_method(exs, sc1_sentence_negation),
        "SC2_clause+qualifier": downstream.score_method(exs, sc2_clause_qualifier),
        "SC3_preserve_unless_conj": downstream.score_method(exs, sc3_preserve_unless_conj),
        "FULL_component": ablation["FULL"],
    }
    return {"corpus": dataset.DATASET_VERSION,
            "phase21_stage_cost": STAGE_COST,
            "phase22_ablation": ablation,
            "phase23_comparators": comparators}


def main() -> None:
    r = run()
    out = os.path.join(os.path.dirname(__file__), "eval_results", "ablation.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)

    print("Phase 22 - ablation (remove one feature; watch unsafe delivery / evidence-query):")
    print(f"  {'config':28} {'unsafe':>8} {'evq_altered':>12} {'false_rej':>10}")
    for name, s in r["phase22_ablation"].items():
        print(f"  {name:28} {s['unsafe_delivery_rate']:>8.3f} {s['evidence_query_altered_rate']:>12.3f} "
              f"{s['false_rejection_rate']:>10.3f}")
    print("\nPhase 23 - complexity comparators vs full component:")
    print(f"  {'method':28} {'unsafe':>8} {'evq_altered':>12} {'cost_probes':>11}")
    full_cost = sum(STAGE_COST.values())
    costs = {"SC1_sentence+negation": 2, "SC2_clause+qualifier": 3, "SC3_preserve_unless_conj": 2,
             "FULL_component": full_cost}
    for name, s in r["phase23_comparators"].items():
        print(f"  {name:28} {s['unsafe_delivery_rate']:>8.3f} {s['evidence_query_altered_rate']:>12.3f} "
              f"{costs[name]:>11}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
