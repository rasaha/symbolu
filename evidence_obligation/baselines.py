"""Phase 8 - Baselines A-S for obligation assignment.

Nineteen obligation policies scored against the independent gold, so the reference component (Q) is
measured against uniform, single-feature, and unsafe-shortcut comparators, an oracle (R), and a simple
learned comparator (S). Each predictor returns an EvidenceObligation-shaped record.

Deterministic, read-only. Writes eval_results/baselines.json.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any, Dict

from evidence_obligation import schema as s
from evidence_obligation import claim_type, source_role as sr, risk as risk_mod, taxonomy, authority as au
from evidence_obligation import classifier, metrics, dataset

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")


def _obl(item, otype, ct=""):
    return s.new_obligation(item.get("artifact_id", "c"), item.get("source_path", ""),
                            evidence_obligation_type=otype, claim_type=ct,
                            risk_tier=item.get("risk_tier", "medium"))


def A_uniform_strong(it):    return _obl(it, s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED)
def B_uniform_qualify(it):   return _obl(it, s.QUALIFY_BY_DEFAULT)


def C_risk_only(it):
    r = it.get("risk_tier", "medium")
    return _obl(it, s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED if r in ("high", "critical")
                else (s.QUALIFY_BY_DEFAULT if r == "medium" else s.CONTEXTUAL_SUPPORT_SUFFICIENT))


def D_domain_only(it):
    dom = it.get("domain", "")
    high = {"cybersecurity", "compliance_regulatory", "healthcare_admin", "financial_research"}
    return _obl(it, s.INDEPENDENT_CORROBORATION_REQUIRED if dom in high else s.CONTEXTUAL_SUPPORT_SUFFICIENT)


def E_claim_type_only(it):
    fam, _ = claim_type.classify_claim_type(it.get("text", ""))
    return _obl(it, taxonomy.default_obligation(fam, "low"), ct=fam)     # ignore risk


def F_source_role_only(it):
    role, _ = sr.classify_source_role(it.get("source_path", ""), it.get("source_kind", "doc"), it.get("text", ""))
    m = {sr.PRIMARY_IMPLEMENTATION: s.IMPLEMENTATION_EVIDENCE_SUFFICIENT,
         sr.TEST_ARTIFACT: s.IMPLEMENTATION_EVIDENCE_SUFFICIENT,
         sr.APPROVED_POLICY: s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT,
         sr.TELEMETRY_OUTPUT: s.TELEMETRY_OR_MEASUREMENT_REQUIRED,
         sr.EXTERNAL_PRIMARY_AUTHORITY: s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED}
    return _obl(it, m.get(role, s.CONTEXTUAL_SUPPORT_SUFFICIENT))


def G_claim_type_risk(it):
    fam, _ = claim_type.classify_claim_type(it.get("text", ""))
    return _obl(it, taxonomy.default_obligation(fam, it.get("risk_tier", "medium")), ct=fam)


def H_source_authority(it):
    role, _ = sr.classify_source_role(it.get("source_path", ""), it.get("source_kind", "doc"), it.get("text", ""))
    lvl = au.artifact_authority_level(role)
    return _obl(it, s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT if lvl in ("high", "medium")
                else s.INDEPENDENT_CORROBORATION_REQUIRED)


def I_claim_type_source(it):
    fam, _ = claim_type.classify_claim_type(it.get("text", ""))
    role, _ = sr.classify_source_role(it.get("source_path", ""), it.get("source_kind", "doc"), it.get("text", ""))
    base = taxonomy.default_obligation(fam, "low")
    # if artifact-dependent but source not authoritative, escalate
    if base in (s.IMPLEMENTATION_EVIDENCE_SUFFICIENT, s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT):
        v, _ = au.authority_for(role, fam)
        if v in (au.SELF_REFERENTIAL, au.NOT_AUTHORITATIVE):
            base = s.INDEPENDENT_CORROBORATION_REQUIRED
    return _obl(it, base, ct=fam)


def J_claim_type_source_risk(it):
    fam, _ = claim_type.classify_claim_type(it.get("text", ""))
    role, _ = sr.classify_source_role(it.get("source_path", ""), it.get("source_kind", "doc"), it.get("text", ""))
    base = taxonomy.default_obligation(fam, it.get("risk_tier", "medium"))
    if base in (s.IMPLEMENTATION_EVIDENCE_SUFFICIENT, s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT):
        v, _ = au.authority_for(role, fam)
        if v in (au.SELF_REFERENTIAL, au.NOT_AUTHORITATIVE):
            base = s.INDEPENDENT_CORROBORATION_REQUIRED
    return _obl(it, base, ct=fam)


def K_global_threshold_reduction(it):  return _obl(it, s.CONTEXTUAL_SUPPORT_SUFFICIENT)   # unsafe: uniform permissive
def L_lowrisk_bypass(it):
    return _obl(it, s.NO_FACTUAL_EVIDENCE_GATE if it.get("risk_tier") == "low"
                else s.QUALIFY_BY_DEFAULT)                                                  # unsafe: no-gate on low
def M_internal_always_auth(it):  return _obl(it, s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT)  # unsafe
def N_impl_always_auth(it):      return _obl(it, s.IMPLEMENTATION_EVIDENCE_SUFFICIENT)          # unsafe
def O_nogate_all_lowrisk(it):
    return _obl(it, s.NO_FACTUAL_EVIDENCE_GATE if it.get("risk_tier") == "low" else s.CONTEXTUAL_SUPPORT_SUFFICIENT)


def P_simple_contextual(it):
    fam, _ = claim_type.classify_claim_type(it.get("text", ""))
    r = it.get("risk_tier", "medium")
    if r in ("high", "critical"):
        return _obl(it, s.INDEPENDENT_CORROBORATION_REQUIRED, ct=fam)
    return _obl(it, taxonomy.default_obligation(fam, "low"), ct=fam)


def Q_reference(it):  return classifier.classify(it)
def R_oracle(it):     return _obl(it, it["gold_obligation"])


_S_MODEL: Dict = {}


def _train_S(dev):
    """S - a simple learned comparator: most frequent gold obligation per (claim_family, risk_tier),
    fit on DEVELOPMENT only (never on held-out)."""
    from collections import defaultdict
    counts = defaultdict(Counter)
    for it in dev:
        fam, _ = claim_type.classify_claim_type(it.get("text", ""))
        counts[(fam, it.get("risk_tier", "medium"))][it["gold_obligation"]] += 1
    _S_MODEL.clear()
    for key, c in counts.items():
        _S_MODEL[key] = c.most_common(1)[0][0]


def S_learned(it):
    fam, _ = claim_type.classify_claim_type(it.get("text", ""))
    key = (fam, it.get("risk_tier", "medium"))
    return _obl(it, _S_MODEL.get(key, s.QUALIFY_BY_DEFAULT), ct=fam)


BASELINES = {
    "A_uniform_strong": A_uniform_strong, "B_uniform_qualify": B_uniform_qualify,
    "C_risk_only": C_risk_only, "D_domain_only": D_domain_only, "E_claim_type_only": E_claim_type_only,
    "F_source_role_only": F_source_role_only, "G_claim_type_risk": G_claim_type_risk,
    "H_source_authority": H_source_authority, "I_claim_type_source": I_claim_type_source,
    "J_claim_type_source_risk": J_claim_type_source_risk,
    "K_global_threshold_reduction": K_global_threshold_reduction, "L_lowrisk_bypass": L_lowrisk_bypass,
    "M_internal_always_auth": M_internal_always_auth, "N_impl_always_auth": N_impl_always_auth,
    "O_nogate_all_lowrisk": O_nogate_all_lowrisk, "P_simple_contextual": P_simple_contextual,
    "Q_reference": Q_reference, "R_oracle": R_oracle, "S_learned": S_learned,
}


def compute() -> Dict[str, Any]:
    dev = dataset.load_partition("DEVELOPMENT")
    held = dataset.load_partition("HELD_OUT_NATURAL")
    adv = dataset.load_partition("ADVERSARIAL_OBLIGATION")
    _train_S(dev)

    results: Dict[str, Any] = {}
    for name, fn in BASELINES.items():
        results[name] = {
            "held_out_natural": metrics.score_obligations(held, fn),
            "adversarial": metrics.score_obligations(adv, fn),
        }
    return {"dataset_version": "evidence_obligation_v1", "baselines": results,
            "note": "A-J heuristic/single-feature; K-O unsafe shortcuts; P simple; Q reference; "
                    "R oracle; S learned (fit on DEVELOPMENT only)."}


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["baselines_sha256"] = hashlib.sha256(json.dumps(m["baselines"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "baselines.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"{'baseline':30s} {'held_exact':>10s} {'held_accept':>11s} {'held_unsafe':>11s} {'adv_unsafe':>10s}")
    for name in BASELINES:
        h = m["baselines"][name]["held_out_natural"]; a = m["baselines"][name]["adversarial"]
        print(f"{name:30s} {h['exact_accuracy']:>10.3f} {h['acceptable_accuracy']:>11.3f} "
              f"{h['unsafe_assignments']:>11d} {a['unsafe_assignments']:>10d}")
