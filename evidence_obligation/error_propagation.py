"""Phase 16 - Error propagation.

Injects each canonical obligation error into the CORRECT (oracle) obligation and measures how far it
propagates into the frozen EvidenceAssurance delivery - specifically how many injected errors turn a
correctly-withheld claim into an unsafe clean ALLOW. Quantifies which obligation mistakes are dangerous.

Deterministic, read-only. Writes eval_results/error_propagation.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List

from governed_inference_pilot.adapters import evidence_assurance as ea

from evidence_obligation import schema as s, adapters, dataset

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

# each error maps a correct obligation to an erroneous one (the injected mistake)
_ERRORS: Dict[str, Callable[[str], str]] = {
    "external_reduced_to_context": lambda o: s.CONTEXTUAL_SUPPORT_SUFFICIENT
        if o == s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED else o,
    "impl_assigned_to_marketing": lambda o: s.IMPLEMENTATION_EVIDENCE_SUFFICIENT
        if o in (s.INDEPENDENT_CORROBORATION_REQUIRED, s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED) else o,
    "policy_treated_as_impl": lambda o: s.IMPLEMENTATION_EVIDENCE_SUFFICIENT
        if o == s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED else o,
    "stale_policy_as_current": lambda o: s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT
        if o == s.TEMPORAL_VERIFICATION_REQUIRED else o,
    "opinion_as_factual": lambda o: s.INDEPENDENT_CORROBORATION_REQUIRED
        if o == s.NO_FACTUAL_EVIDENCE_GATE else o,
    "factual_as_opinion": lambda o: s.NO_FACTUAL_EVIDENCE_GATE
        if o in (s.INDEPENDENT_CORROBORATION_REQUIRED, s.TELEMETRY_OR_MEASUREMENT_REQUIRED) else o,
    "high_risk_as_low_risk": lambda o: s.CONTEXTUAL_SUPPORT_SUFFICIENT
        if o in (s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, s.INDEPENDENT_CORROBORATION_REQUIRED,
                 s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED) else o,
    "attribution_as_truth": lambda o: s.NO_FACTUAL_EVIDENCE_GATE
        if o == s.ATTRIBUTION_VERIFICATION_REQUIRED else o,
    "internal_as_independent": lambda o: s.INDEPENDENT_CORROBORATION_REQUIRED
        if o == s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT else o,
    "fixture_as_telemetry": lambda o: s.TELEMETRY_OR_MEASUREMENT_REQUIRED
        if o == s.IMPLEMENTATION_EVIDENCE_SUFFICIENT else o,
    "unknown_forced_authoritative": lambda o: s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT
        if o in (s.INDETERMINATE_OBLIGATION, s.HUMAN_REVIEW_REQUIRED) else o,
    "human_review_suppressed": lambda o: s.CONTEXTUAL_SUPPORT_SUFFICIENT
        if o == s.HUMAN_REVIEW_REQUIRED else o,
}

_NEEDS_INDEPENDENT = {s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, s.INDEPENDENT_CORROBORATION_REQUIRED,
                      s.TELEMETRY_OR_MEASUREMENT_REQUIRED, s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED}


def _deliver(obligation_type: str, item) -> str:
    o = s.new_obligation(item.get("artifact_id", "c"), item.get("source_path", ""),
                         evidence_obligation_type=obligation_type,
                         implementation_inspectability=(item.get("source_role_hint") in
                                                        ("primary_implementation", "test_artifact")),
                         artifact_authority="high" if item.get("source_role_hint") == "approved_policy" else "none")
    return ea.run(adapters.to_evidence_steer(o), item.get("risk_tier", "medium")).local_disposition


def compute() -> Dict[str, Any]:
    items = dataset.load_partition("HELD_OUT_NATURAL") + dataset.load_partition("ADVERSARIAL_OBLIGATION")

    # baseline (no error): deliver each item at its GOLD obligation
    base_unsafe = 0
    for it in items:
        gold = it["gold_obligation"]
        if _deliver(gold, it) == "ALLOW" and (gold in _NEEDS_INDEPENDENT or it.get("synthetic")):
            base_unsafe += 1

    rows = []
    for name, transform in _ERRORS.items():
        induced_unsafe = 0
        changed = 0
        for it in items:
            gold = it["gold_obligation"]
            erroneous = transform(gold)
            if erroneous == gold:
                continue
            changed += 1
            deliver = _deliver(erroneous, it)
            if deliver == "ALLOW" and (gold in _NEEDS_INDEPENDENT or it.get("synthetic")):
                induced_unsafe += 1
        rows.append({"error": name, "items_affected": changed,
                     "induced_unsafe_allows": induced_unsafe,
                     "propagates_to_unsafe": induced_unsafe > 0})

    rows.sort(key=lambda r: -r["induced_unsafe_allows"])
    return {
        "n_items": len(items),
        "baseline_unsafe_allows_at_gold": base_unsafe,
        "errors": rows,
        "most_dangerous": [r["error"] for r in rows if r["induced_unsafe_allows"] > 0][:5],
        "note": "each error mutates the correct (gold) obligation; induced_unsafe_allows = correctly-"
                "withheld claims turned into clean ALLOWs by the error.",
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["error_propagation_sha256"] = hashlib.sha256(
        json.dumps(m["errors"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "error_propagation.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"baseline unsafe at gold: {m['baseline_unsafe_allows_at_gold']}")
    print(f"{'error':34s} {'affected':>9s} {'induced_unsafe':>15s}")
    for r in m["errors"]:
        print(f"{r['error']:34s} {r['items_affected']:>9d} {r['induced_unsafe_allows']:>15d}")
    print("most dangerous:", m["most_dangerous"])
