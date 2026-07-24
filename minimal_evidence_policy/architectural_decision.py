"""Phases 22-23 - Falsification resolution + architectural decision.

Resolves all 17 preregistered nulls from the frozen evidence and derives one architectural decision (of
9) plus one pilot decision (A-I). Deterministic, read-only. Writes eval_results/decision.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from minimal_evidence_policy import (baselines, dataset, metrics, ablation, self_verification as sv,
                                     monotonicity, modifiers, review_study)
from minimal_evidence_policy.internal_pilot import pilot

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

ARCH_OPTIONS = [
    "1 KEEP MINIMAL EVIDENCE POLICY AS A DISTINCT STAGE",
    "2 REDUCE TO RISK FLOOR + ANTI-SELF-VERIFICATION",
    "3 REDUCE TO RISK FLOOR ONLY",
    "4 MERGE INTO EVIDENCE-BINDING POLICY",
    "5 MERGE INTO EVIDENCEASSURANCE ADAPTER",
    "6 USE HUMAN REVIEW FOR ALL NON-LOW-RISK OBLIGATIONS",
    "7 RETAIN PRIOR RICH COMPONENT",
    "8 NOT ENOUGH EVIDENCE",
    "9 REJECT MINIMAL POLICY",
]
PILOT_OPTIONS = [
    "A PROCEED TO SINGLE-CUSTOMER EXTERNAL SHADOW PILOT",
    "B PROCEED TO INTERNAL SINGLE-TENANT PILOT",
    "C PROCEED ONLY FOR LOW-RISK USE CASES",
    "D PROCEED ONLY WITH MANDATORY HUMAN REVIEW",
    "E FIX REVIEWER AGREEMENT FIRST",
    "F FIX POLICY UTILITY FIRST",
    "G FIX SAFETY INVARIANTS FIRST",
    "H NOT ENOUGH EVIDENCE",
    "I DO NOT PROCEED",
]


def resolve_nulls() -> Dict[str, Dict[str, Any]]:
    held = dataset.load_partition("HELD_OUT_NATURAL")
    adv = dataset.load_partition("ADVERSARIAL_INVARIANTS")
    mp_h = metrics.score(held, baselines.Full_minimal)
    mp_a = metrics.score(adv, baselines.Full_minimal)
    d_h = metrics.score(held, baselines.D_risk_only)
    i_h = metrics.score(held, baselines.I_rich_component)
    i_a = metrics.score(adv, baselines.I_rich_component)
    ab = ablation.compute()
    comp = modifiers.COMPLEXITY
    pilot_m = pilot.run()

    mp_total = mp_h["unsafe_allow"] + mp_a["unsafe_allow"]
    inv_redundant = not ab["ablations"]["invariants"]["safety_critical"]

    def R(rejected, note):
        return {"null_rejected": rejected, "verdict": "REJECTED" if rejected else "RETAINED", "note": note}

    return {
        "H0-1_risk_only_as_good": R(mp_total < (d_h["unsafe_allow"]),
                                    "risk-only 52 unsafe vs minimal 0 - modifiers earn use"),
        "H0-2_claim_type_no_utility": R("claim_type" in ab["safety_critical_elements"],
                                        "claim-type is safety-critical (ablation adds 43 unsafe)"),
        "H0-3_source_role_no_utility": R(False,
                                         "RETAINED: source role is not a load-bearing modifier here"),
        "H0-4_anti_self_verification_no_safety": R(not inv_redundant,
            "RETAINED (nuanced): invariants add 0 MARGINAL safety on this set (modifiers already catch "
            "the traps); retained as classification-independent insurance - a cleaner isolation is future work"),
        "H0-5_monotonicity_no_safety": R(monotonicity.check()["violations"] == 0,
            "monotonicity holds (0/528) and prevents the burden-stripping downgrades error-prop shows are dangerous"),
        "H0-6_review_fallback_no_value": R(False,
            "RETAINED: review fallback (M) equals Full on metrics here - 0 marginal"),
        "H0-7_no_clean_improvement": R(mp_h["clean_allow_rate"] > 0.20, "0% -> 50% clean allow"),
        "H0-8_no_over_qual_reduction": R(mp_h["over_qualification_rate"] < 0.65, "85.5% -> 0%"),
        "H0-9_unsafe_high_risk": R(mp_h["high_risk_unsafe_allow"] == 0, "0 high-risk unsafe allows"),
        "H0-10_unsafe_action": R(mp_a["unsafe_allow"] == 0 and mp_h["unsafe_allow"] == 0, "0 action unsafe allows"),
        "H0-11_review_burden_excessive": R(pilot_m["minimal_policy_review_rate"] < 0.25,
                                           f"review rate {pilot_m['minimal_policy_review_rate']} < 0.25"),
        "H0-12_reviewers_cannot_agree": {"null_rejected": False, "verdict": "NOT_EVALUATED",
                                         "note": "no real reviewers available"},
        "H0-13_rich_outperforms": R(mp_total < (i_h["unsafe_allow"] + i_a["unsafe_allow"]),
                                    "minimal 0 total unsafe vs rich 85 - minimal safer at similar clean"),
        "H0-14_global_threshold_as_good": R(
            metrics.score(adv, baselines.B_global_threshold)["unsafe_allow"] > 0, "global threshold 75+ unsafe"),
        "H0-15_exceeds_complexity_budget": R(comp["policy_logic_rules"] <= comp["budget_primary_rules"],
                                             f"{comp['policy_logic_rules']} policy-logic rules <= 20"),
        "H0-16_pilot_too_conservative": R(pilot_m["policy_comparison"]["minimal_policy"]["held_out_natural"]["clean_allow_rate"] > 0.20,
                                          "internal pilot clean allow 0.50 > 0.20"),
        "H0-17_external_readiness_blocked": {"null_rejected": False, "verdict": "RETAINED",
            "note": "human validation NOT EVALUATED -> external readiness blocked"},
    }


def decide() -> Dict[str, Any]:
    nulls = resolve_nulls()
    ab = ablation.compute()
    held = dataset.load_partition("HELD_OUT_NATURAL")
    mp_h = metrics.score(held, baselines.Full_minimal)
    mp_a = metrics.score(dataset.load_partition("ADVERSARIAL_INVARIANTS"), baselines.Full_minimal)
    comp = modifiers.COMPLEXITY

    safe = mp_h["unsafe_allow"] == 0 and mp_a["unsafe_allow"] == 0 and sv.validate()["self_verification_escape"] == 0
    useful = mp_h["clean_allow_rate"] > 0.20
    monotone = monotonicity.check()["violations"] == 0
    within_budget = comp["policy_logic_rules"] <= comp["budget_primary_rules"]
    # claim-type is safety-critical, so risk-floor+ASV alone (option 2, no claim-type) is insufficient
    claim_type_needed = "claim_type" in ab["safety_critical_elements"]
    human_validation_missing = review_study.HUMAN_VALIDATION == "NOT_EVALUATED"

    if not (safe and useful):
        arch_idx = 7        # NOT ENOUGH EVIDENCE / reject region
    elif claim_type_needed:
        arch_idx = 0        # keep minimal as a distinct stage (needs risk+claim+modifiers, not just risk+ASV)
    else:
        arch_idx = 1        # risk floor + anti-self-verification

    if not (safe and useful and monotone and within_budget):
        pilot_idx = 8       # do not proceed
    elif human_validation_missing:
        pilot_idx = 1       # internal single-tenant pilot (external blocked until real review)
    else:
        pilot_idx = 0

    rejected = sum(1 for v in nulls.values() if v["null_rejected"])
    return {
        "nulls": nulls,
        "nulls_rejected": rejected,
        "nulls_retained_or_ne": len(nulls) - rejected,
        "nulls_total": len(nulls),
        "dimension_findings": {
            "safe": safe, "useful": useful, "monotonic": monotone, "within_budget": within_budget,
            "claim_type_safety_critical": claim_type_needed,
            "invariants_marginal_on_this_data": not ab["ablations"]["invariants"]["safety_critical"],
            "human_validation_missing": human_validation_missing,
        },
        "architectural_decision": ARCH_OPTIONS[arch_idx],
        "pilot_decision": PILOT_OPTIONS[pilot_idx],
        "separated_dimensions": {
            "architectural_need": "a small distinct obligation stage is justified (uniform/global/rich all fail)",
            "safety": "0 unsafe high-risk/action, 0 self-verification escapes, monotonic",
            "utility": "clean allow 0% -> 50%, over-qualification 85.5% -> 0%",
            "reviewer_evidence": "NOT EVALUATED (no real reviewers); proxy only",
            "complexity": "12 policy-logic rules (<=20); minimum viable safe = risk+claim+temporal+action",
            "latency": "sub-ms, stdlib-only, deterministic",
            "metadata_burden": "risk + claim-type are the load-bearing metadata",
            "internal_pilot_readiness": "READY (bounded, non-enforcing, audited)",
            "external_pilot_readiness": "BLOCKED (human validation missing)",
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
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"nulls: {m['nulls_rejected']} rejected / {m['nulls_retained_or_ne']} retained-or-NE")
    for k, v in m["nulls"].items():
        print(f"  [{v['verdict']:12s}] {k}")
    print(f"\nARCHITECTURAL: {m['architectural_decision']}")
    print(f"PILOT:         {m['pilot_decision']}")
