"""Phase 14 - Error-propagation study.

Injects each canonical obligation error into the correct (gold) obligation and measures how many
correctly-withheld claims become unsafe clean ALLOWs downstream through the frozen EvidenceAssurance.
Deterministic, read-only. Writes eval_results/error_propagation.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict

from governed_inference_pilot.adapters import evidence_assurance as ea
from minimal_evidence_policy import schema as s, adapters, dataset

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")
_NEEDS_IND = {s.E3, s.E4}


def _deliver(level: str, item: Dict[str, Any]) -> str:
    dec = s.Decision(claim_id=item.get("artifact_id", "c"), risk_floor=level, final_obligation=level)
    return ea.run(adapters.to_evidence_steer(dec, item), item.get("risk_tier", "medium")).local_disposition


# each error maps the correct level to an erroneous (usually weaker) one
_ERRORS: Dict[str, Callable[[str], str]] = {
    "risk_downgrade": lambda g: s.E1 if s.RANK[g] >= s.RANK[s.E3] else g,
    "factual_as_opinion": lambda g: s.E0 if g in (s.E3, s.E4) else g,
    "source_authoritative_no_basis": lambda g: s.E2 if g == s.E3 else g,
    "generated_as_evidence": lambda g: s.E1 if g in (s.E3, s.E4) else g,
    "fixture_as_telemetry": lambda g: s.E2 if g == s.E3 else g,
    "stale_as_current": lambda g: s.E2 if g == s.E3 else g,
    "actionability_omitted": lambda g: s.E1 if g == s.E3 else g,
    "current_as_timeless": lambda g: s.E1 if g == s.E3 else g,
    "attribution_as_truth": lambda g: s.E0 if g == s.E2 else g,
    "unknown_forced_internal": lambda g: s.E2 if g == s.ER else g,
    "E4_downgraded_to_E2": lambda g: s.E2 if g == s.E4 else g,
    "ER_forced_to_E1": lambda g: s.E1 if g == s.ER else g,
}


def compute() -> Dict[str, Any]:
    items = dataset.load_partition("HELD_OUT_NATURAL") + dataset.load_partition("ADVERSARIAL_INVARIANTS")
    base_unsafe = sum(1 for it in items
                      if _deliver(it["gold_obligation"], it) == "ALLOW"
                      and (it["gold_obligation"] in _NEEDS_IND or it.get("synthetic")))

    rows = []
    for name, tf in _ERRORS.items():
        induced = changed = 0
        for it in items:
            g = it["gold_obligation"]
            err = tf(g)
            if err == g:
                continue
            changed += 1
            if _deliver(err, it) == "ALLOW" and (g in _NEEDS_IND or it.get("synthetic")):
                induced += 1
        rows.append({"error": name, "items_affected": changed, "induced_unsafe_allows": induced,
                     "propagates_to_unsafe": induced > 0})
    rows.sort(key=lambda r: -r["induced_unsafe_allows"])
    return {
        "n_items": len(items), "baseline_unsafe_allows_at_gold": base_unsafe,
        "errors": rows,
        "most_dangerous": [r["error"] for r in rows if r["induced_unsafe_allows"] > 0][:5],
        "note": "each error mutates the correct obligation; induced_unsafe = correctly-withheld claims "
                "turned into clean ALLOWs. Burden-stripping errors propagate; evidence-absent errors are "
                "absorbed by the contract's fail-closed asymmetry.",
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["error_propagation_sha256"] = hashlib.sha256(json.dumps(m["errors"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "error_propagation.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"baseline unsafe at gold: {m['baseline_unsafe_allows_at_gold']}")
    for r in m["errors"]:
        print(f"  {r['error']:30s} affected={r['items_affected']:4d} induced_unsafe={r['induced_unsafe_allows']:4d}")
    print("most dangerous:", m["most_dangerous"])
