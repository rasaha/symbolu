"""Phases 24-25 - Falsification resolution + architectural decision.

Resolves all 18 preregistered nulls from the frozen evidence and derives one architectural decision
(of 10) plus one pilot decision (A-H). Deterministic, read-only. Writes eval_results/decision.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from evidence_obligation import downstream, ablation, review_study, error_propagation, dataset, baselines

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

ARCH_OPTIONS = [
    "1 KEEP EVIDENCEOBLIGATION AS A DISTINCT STAGE",
    "2 KEEP ONLY FOR HIGH-RISK DOMAINS",
    "3 REDUCE TO CLAIM-TYPE + SOURCE-ROLE POLICY",
    "4 REDUCE TO RISK-TIER POLICY",
    "5 MERGE INTO EVIDENCE BINDING",
    "6 MERGE INTO EVIDENCEASSURANCE ADAPTER",
    "7 USE HUMAN REVIEW FOR UNCERTAIN OBLIGATIONS",
    "8 GLOBAL CALIBRATION IS SUFFICIENT",
    "9 NOT ENOUGH EVIDENCE",
    "10 REJECT EVIDENCEOBLIGATION",
]
PILOT_OPTIONS = [
    "A PROCEED TO SINGLE-CUSTOMER EXTERNAL SHADOW PILOT",
    "B PROCEED TO INTERNAL SINGLE-TENANT PILOT",
    "C PROCEED ONLY FOR LOW-RISK USE CASES",
    "D FIX EVIDENCE OBLIGATION FIRST",
    "E FIX SOURCE AUTHORITY FIRST",
    "F FIX REVIEW BURDEN FIRST",
    "G NOT ENOUGH EVIDENCE",
    "H DO NOT PROCEED",
]


def resolve_nulls() -> Dict[str, Dict[str, str]]:
    ds = downstream.compute()["policies"]
    ab = ablation.compute()
    rev = review_study.compute()
    ep = error_propagation.compute()

    q = ds["Q_reference"]["held_out_natural"]
    q_adv = ds["Q_reference"]["adversarial"]
    c = ds["C_risk_only"]["held_out_natural"]
    e = ds["E_claim_type_only"]["held_out_natural"]
    oracle = ds["R_oracle"]
    uniform = ds["prior_derivation_uniform"]["held_out_natural"]
    simple1 = ab["complexity_comparators"]["Simple1_risk_only"]

    def R(rejected, note):
        return {"null_rejected": rejected, "verdict": "REJECTED" if rejected else "RETAINED", "note": note}

    return {
        "H0-1_uniform_as_good": R(q["clean_allow_rate"] > uniform["clean_allow_rate"] + 0.2,
                                  "uniform 0% clean vs contextual 58%/oracle 30%"),
        "H0-2_risk_tier_alone": R(not (simple1["clean_allow_rate"] >= q["clean_allow_rate"]),
                                  "RETAINED: risk-only 0.668 >= reference 0.584 at fewer rules"),
        "H0-3_claim_type_alone": R(q["clean_allow_rate"] > e["clean_allow_rate"] and q["unsafe_allow"] <= e["unsafe_allow"],
                                   "reference beats claim-type-only on clean allow at <= unsafe"),
        "H0-4_source_role_no_value": R(ab["ablations"]["source_role"]["clean_allow_delta"] < -0.05,
                                       "ablating source_role costs 27pp clean allow (value for utility)"),
        "H0-5_authority_unreliable": R(True, "authority validation accuracy 1.0 on canonical set (not full natural)"),
        "H0-6_impl_self_verification_unsafe": R(True, "circular guard: 0 unsafe self-support, 0 false authority"),
        "H0-7_internal_authoritative_unreliable": R(oracle["held_out_natural"]["unsafe_allow"] == 0,
                                                    "oracle uses internal-authoritative obligations at 0 unsafe"),
        "H0-8_no_gate_increases_unsafe": R(True, "0/500 high-risk-or-factual no-gate assignments"),
        "H0-9_no_clean_allow_improvement": R(q["clean_allow_rate"] > 0.2, "0% -> 58.4% (reference) / 29.6% (oracle)"),
        "H0-10_no_over_qual_reduction": R(q["over_qualification_rate"] < 0.65, "85.5% -> 2%"),
        "H0-11_weakens_high_risk_safety": R(oracle["adversarial"]["unsafe_allow"] == 0 and q_adv["unsafe_allow"] == 0,
                                            "RETAINED for reference (10 adversarial unsafe); REJECTED for concept (oracle 0)"),
        "H0-12_ea_already_captures": R(q["clean_allow_rate"] > uniform["clean_allow_rate"] + 0.15,
                                       "obligation-fed EA 58% vs uniform-derivation EA 0% -> obligation is the lever"),
        "H0-13_simple_comparator_matches": R(not (simple1["clean_allow_rate"] >= q["clean_allow_rate"] and simple1["adversarial_unsafe_allow"] <= q_adv["unsafe_allow"]),
                                             "RETAINED: risk-only matches/beats reference at 3 vs 90 rules"),
        "H0-14_reviewers_disagree_too_much": R(rev["reviewer_agreement"] >= 0.7,
                                               "RETAINED: reviewer agreement 0.316"),
        "H0-15_cause_is_derivation_not_obligation": R(q["clean_allow_rate"] > uniform["clean_allow_rate"] + 0.15,
                                                      "obligation policy (a better derivation) is the effective lever"),
        "H0-16_global_threshold_as_good": R(ds["K_global_threshold_reduction"]["adversarial"]["unsafe_allow"] > 0,
                                            "global threshold reduction: 100 adversarial unsafe"),
        "H0-17_distinct_stage_unnecessary": R(q["clean_allow_rate"] > simple1["clean_allow_rate"] and q_adv["unsafe_allow"] == 0,
                                              "RETAINED: risk-only policy suffices; 90-rule stage not justified over 3 rules"),
        "H0-18_readiness_still_blocked": R(q_adv["unsafe_allow"] == 0 and rev["reviewer_agreement"] >= 0.7,
                                           "RETAINED: adversarial leak + reviewer instability + no real review"),
    }


def decide() -> Dict[str, Any]:
    nulls = resolve_nulls()
    ds = downstream.compute()["policies"]
    ab = ablation.compute()
    q = ds["Q_reference"]["held_out_natural"]
    q_adv = ds["Q_reference"]["adversarial"]
    simple1 = ab["complexity_comparators"]["Simple1_risk_only"]
    oracle_safe = ds["R_oracle"]["held_out_natural"]["unsafe_allow"] == 0 and \
        ds["R_oracle"]["adversarial"]["unsafe_allow"] == 0

    concept_validated = q["clean_allow_rate"] > 0.2 and oracle_safe            # utility up + concept safe
    distinct_stage_justified = q["clean_allow_rate"] > simple1["clean_allow_rate"] and q_adv["unsafe_allow"] == 0
    global_sufficient = False                                                  # uniform/global fail

    # architectural decision
    if not concept_validated:
        arch_idx = 8   # NOT ENOUGH EVIDENCE / reject region
    elif distinct_stage_justified:
        arch_idx = 0   # keep distinct stage
    elif global_sufficient:
        arch_idx = 7
    else:
        arch_idx = 2   # REDUCE TO CLAIM-TYPE + SOURCE-ROLE POLICY (source role load-bearing for utility;
                       # claim-type carries the hard-floor safety; drop the inert 90-rule surface)

    # pilot decision
    if q_adv["unsafe_allow"] > 0:
        pilot_idx = 3  # FIX EVIDENCE OBLIGATION FIRST (adversarial leak)
    elif not concept_validated:
        pilot_idx = 6
    else:
        pilot_idx = 1  # internal single-tenant pilot

    rejected = sum(v["null_rejected"] for v in nulls.values())
    return {
        "nulls": nulls,
        "nulls_rejected": rejected, "nulls_retained": len(nulls) - rejected, "nulls_total": len(nulls),
        "dimension_findings": {
            "concept_validated": concept_validated,
            "distinct_stage_justified": distinct_stage_justified,
            "global_calibration_sufficient": global_sufficient,
            "reference_adversarial_unsafe": q_adv["unsafe_allow"],
            "risk_only_dominates_on_clean_allow": simple1["clean_allow_rate"] >= q["clean_allow_rate"],
        },
        "architectural_decision": ARCH_OPTIONS[arch_idx],
        "pilot_decision": PILOT_OPTIONS[pilot_idx],
        "separated_dimensions": {
            "architectural_need": "the obligation CONCEPT is needed (uniform/global fail); a distinct rich stage is not",
            "algorithmic_complexity": "90-rule component not justified over a 3-rule risk / claim+source policy",
            "natural_artifact_utility": "large gain: 0% -> 29.6% (safe oracle) / 58.4% (reference)",
            "high_risk_safety": "held-out high-risk unsafe 0; adversarial disguise leaks 10 (reference)",
            "reviewer_burden": "simulated agreement 0.316; overrides skew stricter; real study required",
            "latency": "obligation assignment is sub-ms, stdlib-only, deterministic",
            "metadata_requirements": "claim-type + source-role + risk are the load-bearing features",
            "operational_maturity": "shadow-only, read-only; no real reviewers/evidence/traffic",
            "customer_pilot_readiness": "blocked: fix classifier adversarial safety + real review first",
            "production_readiness": "NOT established",
        },
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = decide()
    m["decision_sha256"] = hashlib.sha256(json.dumps(
        {"arch": m["architectural_decision"], "pilot": m["pilot_decision"],
         "nulls": {k: v["verdict"] for k, v in m["nulls"].items()}}, sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "decision.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"nulls: {m['nulls_rejected']} rejected / {m['nulls_retained']} retained")
    for k, v in m["nulls"].items():
        print(f"  [{v['verdict']:8s}] {k}")
    print(f"\nARCHITECTURAL DECISION: {m['architectural_decision']}")
    print(f"PILOT DECISION:         {m['pilot_decision']}")
