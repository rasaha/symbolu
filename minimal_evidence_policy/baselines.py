"""Phase 7 - Baselines A-O for the minimal policy.

Each baseline yields (evidence_state, obligation_level) per item, scored downstream through the frozen
EvidenceAssurance. Includes the prior rich EvidenceObligation component (read-only) mapped to the E
vocabulary. Deterministic. Writes eval_results/baselines.json.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any, Callable, Dict, Tuple

from minimal_evidence_policy import schema as s, classifier, adapters, metrics, dataset

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")
_S_MODEL: Dict = {}


def _state_for(level: str, item: Dict[str, Any], av=None) -> Tuple[str, str]:
    dec = s.Decision(claim_id=item.get("artifact_id", "c"), risk_floor=level, final_obligation=level)
    steer = adapters.to_evidence_steer(dec, item, av)
    return steer["evidence_state"], level


# --- baselines: item -> (evidence_state, level) ---
def A_prior_uniform(it):        return ("VERIFIED_WITH_LIMITATIONS", "PRIOR_UNIFORM")   # always qualify
def B_global_threshold(it):     return ("VERIFIED", "GLOBAL_LOW")                       # always allow (unsafe)
def C_lowrisk_bypass(it):
    return ("VERIFIED", s.E0) if it.get("risk_tier") == "low" else _state_for(s.E3, it)
def D_risk_only(it):
    lvl = {"low": s.E1, "medium": s.E2, "high": s.E3, "critical": s.E4, "unknown": s.ER}.get(it.get("risk_tier"), s.ER)
    return _state_for(lvl, it)
def E_claim_type_only(it):
    return _state_for(classifier.classify({**it, "risk_tier": "low"}, ablate=frozenset(["risk_floor", "invariants"])).final_obligation, it)
def F_source_role_only(it):
    role = it.get("source_role", "unknown_source")
    lvl = s.E2 if role in ("primary_implementation", "test_artifact", "approved_policy") else s.E3
    return _state_for(lvl, it)
def G_claim_source(it):
    return _state_for(classifier.classify({**it, "risk_tier": "low"}, ablate=frozenset(["risk_floor"])).final_obligation, it)
def H_claim_source_risk(it):
    return _state_for(classifier.classify(it, ablate=frozenset(["invariants"])).final_obligation, it)
def J_minimal_risk_floor(it):
    return _state_for(classifier.classify(it, ablate=frozenset(["claim_type", "temporal", "actionability"])).final_obligation, it)
def K_minimal_no_invariants(it):
    return _state_for(classifier.classify(it, ablate=frozenset(["invariants"])).final_obligation, it)
def L_minimal_no_upward_only(it):
    # simulate downward allowance: take the claim-type modifier WITHOUT the risk floor
    return _state_for(classifier.classify(it, ablate=frozenset(["risk_floor", "invariants"])).final_obligation, it)
def M_minimal_review_fallback(it):
    d = classifier.classify(it)
    lvl = s.ER if d.unresolved_fields else d.final_obligation
    return _state_for(lvl, it)
def Full_minimal(it):
    return _state_for(classifier.classify(it).final_obligation, it)


def I_rich_component(it):
    """Prior rich EvidenceObligation component (read-only), mapped to the E vocabulary."""
    from evidence_obligation import classifier as rich
    o = rich.classify(it).evidence_obligation_type
    m = {
        "EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED": s.E4,
        "INDEPENDENT_CORROBORATION_REQUIRED": s.E3, "TELEMETRY_OR_MEASUREMENT_REQUIRED": s.E3,
        "POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED": s.E3,
        "INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT": s.E2, "IMPLEMENTATION_EVIDENCE_SUFFICIENT": s.E2,
        "CONTEXTUAL_SUPPORT_SUFFICIENT": s.E1, "ATTRIBUTION_VERIFICATION_REQUIRED": s.E2,
        "TEMPORAL_VERIFICATION_REQUIRED": s.E3, "LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED": s.E2,
        "NO_FACTUAL_EVIDENCE_GATE": s.E0, "QUALIFY_BY_DEFAULT": s.E1,
        "HUMAN_REVIEW_REQUIRED": s.ER, "INDETERMINATE_OBLIGATION": s.ER,
    }
    return _state_for(m.get(o, s.ER), it)


def N_learned(it):
    key = (it.get("claim_family", ""), it.get("risk_tier", "medium"))
    return _state_for(_S_MODEL.get(key, s.E3), it)


def O_oracle(it):
    return _state_for(it["gold_obligation"], it)


def _train_N(dev):
    counts = {}
    for it in dev:
        key = (it.get("claim_family", ""), it.get("risk_tier", "medium"))
        counts.setdefault(key, Counter())[it["gold_obligation"]] += 1
    _S_MODEL.clear()
    for k, c in counts.items():
        _S_MODEL[k] = c.most_common(1)[0][0]


BASELINES: Dict[str, Callable] = {
    "A_prior_uniform": A_prior_uniform, "B_global_threshold": B_global_threshold,
    "C_lowrisk_bypass": C_lowrisk_bypass, "D_risk_only": D_risk_only,
    "E_claim_type_only": E_claim_type_only, "F_source_role_only": F_source_role_only,
    "G_claim_source": G_claim_source, "H_claim_source_risk": H_claim_source_risk,
    "I_rich_component": I_rich_component, "J_minimal_risk_floor": J_minimal_risk_floor,
    "K_minimal_no_invariants": K_minimal_no_invariants, "L_minimal_no_upward_only": L_minimal_no_upward_only,
    "M_minimal_review_fallback": M_minimal_review_fallback, "Full_minimal": Full_minimal,
    "N_learned": N_learned, "O_oracle": O_oracle,
}


def compute() -> Dict[str, Any]:
    _train_N(dataset.load_partition("DEVELOPMENT"))
    held = dataset.load_partition("HELD_OUT_NATURAL")
    adv = dataset.load_partition("ADVERSARIAL_INVARIANTS")
    results = {name: {"held_out_natural": metrics.score(held, fn), "adversarial": metrics.score(adv, fn)}
               for name, fn in BASELINES.items()}
    return {"dataset_version": "minimal_evidence_policy_v1", "baselines": results,
            "prior_reference": {"clean_allow": 0.0, "over_qualification": 0.855}}


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["baselines_sha256"] = hashlib.sha256(json.dumps(m["baselines"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "baselines.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"{'baseline':28s} {'clean':>7s} {'overqual':>9s} {'withhold':>9s} {'unsafe':>7s} {'adv_unsafe':>10s}")
    for name in BASELINES:
        h = m["baselines"][name]["held_out_natural"]; a = m["baselines"][name]["adversarial"]
        print(f"{name:28s} {h['clean_allow_rate']:>7.3f} {h['over_qualification_rate']:>9.3f} "
              f"{h['withholding_rate']:>9.3f} {h['unsafe_allow']:>7d} {a['unsafe_allow']:>10d}")
