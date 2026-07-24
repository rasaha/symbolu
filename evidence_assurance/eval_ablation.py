"""Ablation (Phase 18), cost/latency proxy (Phase 17), and complexity comparator (Phase 19).

Phase 18: remove one layer at a time and measure the effect on escape / false-block / accuracy. A
layer is load-bearing iff removing it raises escape (or materially moves false-block).

Phase 17: a deterministic cost proxy — each layer costs a fixed number of "probes" (metadata reads /
search strategies). No wall-clock timing (non-deterministic); the proxy is comparable across methods.

Phase 19: complexity vs marginal safety — is the full stack justified over the cheapest layer set that
achieves the same escape? Reports the minimal sufficient subset found by greedy removal.

Deterministic. Writes eval_results/ablation_v1.json. Touches no prior-track artifact.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict

from . import dataset, assurance, counterevidence
from .assurance import LAYERS, ALL_LAYERS
from .taxonomy import delivered_as_supported

TRAP = {"CORRELATED_FAILURE", "ADVERSARIAL_PROVENANCE"}

# Phase 17 cost proxy: probes per layer (metadata reads / search strategies). counterevidence is the
# expensive one (it runs the strategy set); the rest are cheap metadata inspections.
LAYER_COST = {
    "provenance": 3,      # upstream, hashes, retrieval paths
    "independence": 2,    # verdict over provenance graph
    "alignment": 2,       # passage + scope/temporal/jurisdiction checks
    "counterevidence": len(counterevidence.STRATEGIES),   # the search strategy set (expensive)
    "authority": 1,
    "freshness": 1,
}


def _score(cases, enabled) -> dict:
    esc = fb = exact = 0
    n_unsup = n_sup = 0
    trap_esc = 0
    for c in cases:
        res = assurance.assess(c, enabled=enabled)
        gs = delivered_as_supported(c["gold_state"])
        ps = delivered_as_supported(res.state)
        if res.state == c["gold_state"]:
            exact += 1
        if gs:
            n_sup += 1
        else:
            n_unsup += 1
        if ps and not gs:
            esc += 1
            if c["partition"] in TRAP:
                trap_esc += 1
        if not ps and gs:
            fb += 1
    n_trap = sum(1 for c in cases if c["partition"] in TRAP)
    return {
        "escape": round(esc / n_unsup, 4) if n_unsup else 0.0,
        "correlated_failure_escape": round(trap_esc / n_trap, 4) if n_trap else 0.0,
        "false_block": round(fb / n_sup, 4) if n_sup else 0.0,
        "accuracy": round(exact / len(cases), 4),
        "cost_probes": sum(LAYER_COST[l] for l in enabled),
    }


def ablation(cases) -> dict:
    full = _score(cases, ALL_LAYERS)
    rows = {"FULL": full}
    for layer in LAYERS:
        rows[f"-{layer}"] = _score(cases, ALL_LAYERS - {layer})
    return rows


def minimal_sufficient_subset(cases) -> dict:
    """Greedy removal: drop the cheapest layer whose removal does NOT raise correlated-failure escape,
    repeat. Returns the surviving subset and its cost — the honest 'is the whole stack needed?' test."""
    enabled = set(ALL_LAYERS)
    base_escape = _score(cases, frozenset(enabled))["correlated_failure_escape"]
    removed = []
    changed = True
    while changed:
        changed = False
        # try removing the most expensive removable layer first (maximize cost savings)
        for layer in sorted(enabled, key=lambda l: -LAYER_COST[l]):
            trial = frozenset(enabled - {layer})
            if _score(cases, trial)["correlated_failure_escape"] <= base_escape:
                enabled.discard(layer)
                removed.append(layer)
                changed = True
                break
    final = _score(cases, frozenset(enabled))
    return {
        "minimal_subset": sorted(enabled),
        "removed_without_raising_cf_escape": removed,
        "subset_result": final,
        "full_cost": sum(LAYER_COST[l] for l in ALL_LAYERS),
        "subset_cost": final["cost_probes"],
    }


def _fully_fabricate(c):
    """Adversary fabricates ALL provenance metadata to look independent and authoritative."""
    d = dict(c)
    d["observed_upstream_ids"] = [f"u{i}" for i in range(4)]
    d["observed_provenance_confidence"] = 0.95
    d["observed_distinct_publishers"] = 6
    d["observed_distinct_domains"] = 6
    d["observed_distinct_retrieval_paths"] = 5
    d["observed_content_hashes"] = [f"h{i}" for i in range(6)]
    d["observed_publication_years"] = [2024, 2024, 2024]
    d["observed_authority_classes"] = ["reputable"] * 4
    return d


def defense_in_depth(cases) -> dict:
    """The complexity justification. On benign data, independence alone matches the full stack — but
    against an adversary who fabricates all provenance metadata, independence alone is fully fooled and
    only the redundant layers (alignment, counterevidence) restore zero correlated-failure escape."""
    trap = [c for c in cases if c["partition"] in TRAP]
    attacked = [_fully_fabricate(c) for c in trap]
    subsets = {
        "independence_only": frozenset({"independence"}),
        "independence+alignment": frozenset({"independence", "alignment"}),
        "independence+counterevidence": frozenset({"independence", "counterevidence"}),
        "FULL": ALL_LAYERS,
    }
    return {name: {"benign_cf_escape": _score(trap, en)["correlated_failure_escape"],
                   "fabricated_cf_escape": _score(attacked, en)["correlated_failure_escape"],
                   "cost_probes": sum(LAYER_COST[l] for l in en)}
            for name, en in subsets.items()}


def run() -> dict:
    cases = [asdict(c) for c in dataset.all_cases()]
    return {
        "corpus": dataset.DATASET_VERSION,
        "phase18_ablation": ablation(cases),
        "phase17_layer_cost_probes": LAYER_COST,
        "phase19_minimal_sufficient_benign": minimal_sufficient_subset(cases),
        "phase19_defense_in_depth_adversarial": defense_in_depth(cases),
    }


def main() -> None:
    r = run()
    out = os.path.join(os.path.dirname(__file__), "eval_results", "ablation_v1.json")
    with open(out, "w") as fh:
        json.dump(r, fh, indent=2, sort_keys=True)

    print(f"corpus={r['corpus']}")
    print("\nPhase 18 — ablation (remove one layer; watch correlated-failure escape rise):")
    print(f"  {'config':18} {'cf_escape':>10} {'escape':>8} {'false_block':>12} {'acc':>6} {'cost':>5}")
    fullcf = r["phase18_ablation"]["FULL"]["correlated_failure_escape"]
    for name, s in r["phase18_ablation"].items():
        delta = "" if name == "FULL" else (
            f"  <-- +{s['correlated_failure_escape']-fullcf:.3f} cf-escape"
            if s["correlated_failure_escape"] > fullcf else "")
        print(f"  {name:18} {s['correlated_failure_escape']:>10.3f} {s['escape']:>8.3f} "
              f"{s['false_block']:>12.3f} {s['accuracy']:>6.3f} {s['cost_probes']:>5}{delta}")

    m = r["phase19_minimal_sufficient_benign"]
    print(f"\nPhase 19a — minimal sufficient subset on BENIGN data (same cf-escape, lowest cost):")
    print(f"  minimal subset: {m['minimal_subset']}")
    print(f"  removable without raising cf-escape: {m['removed_without_raising_cf_escape'] or '(none)'}")
    print(f"  cost: full={m['full_cost']} probes -> subset={m['subset_cost']} probes")
    print(f"  subset also lets OVERALL escape = {m['subset_result']['escape']:.3f} "
          f"(misses non-correlated failure states)")

    print(f"\nPhase 19b — defense in depth: benign vs FULLY-FABRICATED provenance:")
    print(f"  {'subset':32} {'benign':>8} {'fabricated':>11} {'cost':>5}")
    for name, s in r["phase19_defense_in_depth_adversarial"].items():
        print(f"  {name:32} {s['benign_cf_escape']:>8.3f} {s['fabricated_cf_escape']:>11.3f} "
              f"{s['cost_probes']:>5}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
