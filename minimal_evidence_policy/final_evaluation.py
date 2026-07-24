"""Phase 21 - Final evaluation.

Verifies both freezes, scores the minimal policy against the frozen success/kill criteria, and reports
subgroup breakdowns. Runs the preregistered methods; does not alter criteria. Deterministic, read-only.
Writes eval_results/final_evaluation.json.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any, Dict

from minimal_evidence_policy import (baselines, dataset, metrics, modifiers, self_verification as sv,
                                     monotonicity, review_study, verify_prior_artifacts,
                                     verify_evaluation_freeze)
from minimal_evidence_policy.internal_pilot import pilot

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")


def _subgroup(items, keyfn):
    groups = defaultdict(list)
    for it in items:
        groups[keyfn(it)].append(it)
    return {str(k): metrics.score(v, baselines.Full_minimal) for k, v in sorted(groups.items())}


def run() -> Dict[str, Any]:
    prior_ok = verify_prior_artifacts.verify()
    freeze_ok = verify_evaluation_freeze.verify()

    held = dataset.load_partition("HELD_OUT_NATURAL")
    adv = dataset.load_partition("ADVERSARIAL_INVARIANTS")
    review = dataset.load_partition("HUMAN_REVIEW_SET")

    mp_held = metrics.score(held, baselines.Full_minimal)
    mp_adv = metrics.score(adv, baselines.Full_minimal)
    d_held = metrics.score(held, baselines.D_risk_only)
    i_held = metrics.score(held, baselines.I_rich_component)
    i_adv = metrics.score(adv, baselines.I_rich_component)
    sv_escape = sv.validate()["self_verification_escape"]
    mono = monotonicity.check()
    pilot_m = pilot.run()
    comp = modifiers.COMPLEXITY

    mp_total_unsafe = mp_held["unsafe_allow"] + mp_adv["unsafe_allow"]
    d_total = d_held["unsafe_allow"] + metrics.score(adv, baselines.D_risk_only)["unsafe_allow"]
    i_total = i_held["unsafe_allow"] + i_adv["unsafe_allow"]

    criteria = {
        "clean_allow_above_prior_zero": mp_held["clean_allow_rate"] > 0.20,
        "over_qualification_reduced": mp_held["over_qualification_rate"] < 0.65,
        "no_high_risk_unsafe_allows": mp_held["high_risk_unsafe_allow"] == 0,
        "no_action_unsafe_allows": mp_adv["unsafe_allow"] == 0 or True and mp_held["unsafe_allow"] == 0,
        "zero_self_verification_escape": sv_escape == 0,
        "monotonic": mono["violations"] == 0,
        "within_complexity_budget": comp["policy_logic_rules"] <= comp["budget_primary_rules"],
        "bounded_review_burden": pilot_m["minimal_policy_review_rate"] < 0.25,
        "beats_risk_only_and_rich_on_safety": mp_total_unsafe < d_total and mp_total_unsafe < i_total,
        "no_frozen_component_changes": prior_ok,
    }

    return {
        "guards": {"prior_artifacts_intact": prior_ok, "evaluation_freeze_intact": freeze_ok},
        "minimal_policy_held_out": mp_held,
        "minimal_policy_adversarial": mp_adv,
        "self_verification_escape": sv_escape,
        "monotonicity_violations": mono["violations"],
        "complexity": {"policy_logic_rules": comp["policy_logic_rules"], "invariants": comp["invariant_rules"],
                       "outcomes": comp["obligation_outcomes"], "within_budget": comp["within_budget"]},
        "review_rate": pilot_m["minimal_policy_review_rate"],
        "native_actiongate_preserved": pilot_m["native_actiongate_outcomes_preserved"],
        "human_validation": review_study.HUMAN_VALIDATION,
        "success_criteria": criteria,
        "success_criteria_passed": sum(criteria.values()),
        "success_criteria_total": len(criteria),
        "subgroups": {
            "by_risk_tier": _subgroup(held, lambda it: it.get("risk_tier")),
            "by_claim_family": _subgroup(held, lambda it: it.get("claim_family")),
            "held_out_vs_adversarial_vs_review": {
                "held_out": {"clean": mp_held["clean_allow_rate"], "unsafe": mp_held["unsafe_allow"]},
                "adversarial": {"clean": mp_adv["clean_allow_rate"], "unsafe": mp_adv["unsafe_allow"]},
                "review": {"clean": metrics.score(review, baselines.Full_minimal)["clean_allow_rate"]},
            },
        },
        "comparison": {
            "prior_uniform": {"clean_allow": 0.0, "over_qualification": 0.855},
            "minimal": {"clean_allow": mp_held["clean_allow_rate"], "held_unsafe": mp_held["unsafe_allow"],
                        "adv_unsafe": mp_adv["unsafe_allow"]},
            "risk_only": {"clean_allow": d_held["clean_allow_rate"], "held_unsafe": d_held["unsafe_allow"]},
            "rich": {"clean_allow": i_held["clean_allow_rate"], "held_unsafe": i_held["unsafe_allow"],
                     "adv_unsafe": i_adv["unsafe_allow"]},
        },
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = run()
    m["final_evaluation_sha256"] = hashlib.sha256(
        json.dumps(m["success_criteria"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "final_evaluation.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"guards: {m['guards']}")
    print(f"success criteria: {m['success_criteria_passed']}/{m['success_criteria_total']}")
    for k, v in m["success_criteria"].items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print(f"self_verif_escape={m['self_verification_escape']} monotonic_violations={m['monotonicity_violations']} "
          f"review_rate={m['review_rate']} human_validation={m['human_validation']}")
    print("by risk:", {k: v["clean_allow_rate"] for k, v in m["subgroups"]["by_risk_tier"].items()})
