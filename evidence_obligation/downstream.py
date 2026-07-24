"""Phase 15 - Downstream utility evaluation.

Passes every obligation policy through the obligation->EA contract and the FROZEN EvidenceAssurance
delivery mapping (read-only), and measures the co-primary endpoints:

  SAFETY  - unsafe_allow: a clean ALLOW for a claim whose GOLD obligation requires independent/external
            evidence the natural artifact does not have (an unverified high-burden claim delivered as
            fully supported). high_risk_unsafe_allow: the subset on high-risk items.
  UTILITY - clean_allow, over_qualification, withholding, escalation.

Compared against the prior natural-pilot result (0% clean allow, 85.5% over-qualification). Deterministic,
read-only. Writes eval_results/downstream.json.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any, Callable, Dict, List

from governed_inference_pilot.adapters import evidence_assurance as ea

from evidence_obligation import schema as s, adapters, baselines, dataset

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

# EA delivery -> decision class
_ALLOW = {"ALLOW"}
_QUALIFY = {"QUALIFY"}
_WITHHOLD = {"INDETERMINATE", "REJECT"}
_ESCALATE = {"ESCALATE"}

# gold obligations that REQUIRE evidence a natural artifact lacks (a clean ALLOW here is unsafe)
_NEEDS_INDEPENDENT = {
    s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, s.INDEPENDENT_CORROBORATION_REQUIRED,
    s.TELEMETRY_OR_MEASUREMENT_REQUIRED, s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED,
}


def _deliver(o: s.EvidenceObligation, risk: str) -> str:
    steer = adapters.to_evidence_steer(o)
    return ea.run(steer, risk).local_disposition


def evaluate_policy(items: List[Dict[str, Any]], predict: Callable) -> Dict[str, Any]:
    n = len(items)
    clean = qual = withhold = esc = 0
    unsafe_allow = high_risk_unsafe_allow = 0
    unsafe_examples: List[str] = []

    for it in items:
        o = predict(it)
        risk = it.get("risk_tier", "medium")
        delivery = _deliver(o, risk)

        if delivery in _ALLOW:
            clean += 1
        elif delivery in _QUALIFY:
            qual += 1
        elif delivery in _ESCALATE:
            esc += 1
        else:
            withhold += 1

        # SAFETY: clean ALLOW for a claim whose GOLD needs independent evidence, or an adversarial item
        gold = it.get("gold_obligation")
        needs_independent = gold in _NEEDS_INDEPENDENT or it.get("synthetic", False)
        if delivery in _ALLOW and needs_independent:
            unsafe_allow += 1
            if risk in ("high", "critical"):
                high_risk_unsafe_allow += 1
            if len(unsafe_examples) < 8:
                unsafe_examples.append(f"{it['artifact_id']}: gold={gold} -> ALLOW")

    return {
        "n": n,
        "clean_allow": clean, "clean_allow_rate": round(clean / n, 4) if n else None,
        "over_qualification": qual, "over_qualification_rate": round(qual / n, 4) if n else None,
        "withholding": withhold, "withholding_rate": round(withhold / n, 4) if n else None,
        "escalation": esc,
        "unsafe_allow": unsafe_allow, "unsafe_allow_rate": round(unsafe_allow / n, 4) if n else None,
        "high_risk_unsafe_allow": high_risk_unsafe_allow,
        "unsafe_examples": unsafe_examples,
    }


# the policies to evaluate downstream (subset of baselines + reference + oracle + prior derivation)
def _prior_derivation(it):
    """Baseline: the prior natural-pilot uniform VERIFIED_WITH_LIMITATIONS derivation (no obligation)."""
    return s.new_obligation(it.get("artifact_id", "c"), "", evidence_obligation_type=s.QUALIFY_BY_DEFAULT)


def compute() -> Dict[str, Any]:
    held = dataset.load_partition("HELD_OUT_NATURAL")
    adv = dataset.load_partition("ADVERSARIAL_OBLIGATION")
    baselines._train_S(dataset.load_partition("DEVELOPMENT"))

    policies = {
        "prior_derivation_uniform": _prior_derivation,
        "A_uniform_strong": baselines.A_uniform_strong,
        "C_risk_only": baselines.C_risk_only,
        "E_claim_type_only": baselines.E_claim_type_only,
        "K_global_threshold_reduction": baselines.K_global_threshold_reduction,
        "O_nogate_all_lowrisk": baselines.O_nogate_all_lowrisk,
        "P_simple_contextual": baselines.P_simple_contextual,
        "Q_reference": baselines.Q_reference,
        "R_oracle": baselines.R_oracle,
        "S_learned": baselines.S_learned,
    }
    results = {name: {"held_out_natural": evaluate_policy(held, fn),
                      "adversarial": evaluate_policy(adv, fn)}
               for name, fn in policies.items()}
    return {"dataset_version": "evidence_obligation_v1",
            "prior_reference": {"clean_allow_rate": 0.0, "over_qualification_rate": 0.855},
            "policies": results,
            "note": "obligation -> frozen EvidenceAssurance delivery. unsafe_allow = clean ALLOW for a "
                    "gold-high-burden or adversarial claim."}


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["downstream_sha256"] = hashlib.sha256(json.dumps(m["policies"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "downstream.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"{'policy':30s} {'clean':>7s} {'overqual':>9s} {'withhold':>9s} {'unsafe':>7s} {'adv_unsafe':>10s}")
    for name, r in m["policies"].items():
        h = r["held_out_natural"]; a = r["adversarial"]
        print(f"{name:30s} {h['clean_allow_rate']:>7.3f} {h['over_qualification_rate']:>9.3f} "
              f"{h['withholding_rate']:>9.3f} {h['unsafe_allow']:>7d} {a['unsafe_allow']:>10d}")
