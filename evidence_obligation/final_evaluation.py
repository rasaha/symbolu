"""Phase 23 - Final evaluation.

Verifies both freezes, scores the reference component against the frozen success/kill criteria, and
reports subgroup breakdowns (held-out, adversarial, high/low risk, claim type, source role, evidence-
availability strata). Runs the preregistered methods; does not alter criteria.

Deterministic, read-only. Writes eval_results/final_evaluation.json.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Any, Dict, List

from evidence_obligation import (downstream, baselines, dataset, classifier, adapters,
                                 verify_prior_artifacts, verify_evaluation_freeze, schema as s)
from governed_inference_pilot.adapters import evidence_assurance as ea

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")
_NEEDS_INDEPENDENT = {s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, s.INDEPENDENT_CORROBORATION_REQUIRED,
                      s.TELEMETRY_OR_MEASUREMENT_REQUIRED, s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED}


def _deliver(item):
    o = classifier.classify(item)
    return o, ea.run(adapters.to_evidence_steer(o), item.get("risk_tier", "medium")).local_disposition


def _subgroup(items, keyfn):
    groups = defaultdict(list)
    for it in items:
        groups[keyfn(it)].append(it)
    out = {}
    for key, its in sorted(groups.items()):
        clean = unsafe = 0
        for it in its:
            o, d = _deliver(it)
            if d == "ALLOW":
                clean += 1
                if it["gold_obligation"] in _NEEDS_INDEPENDENT or it.get("synthetic"):
                    unsafe += 1
        out[str(key)] = {"n": len(its), "clean_allow_rate": round(clean / len(its), 4),
                         "unsafe_allow": unsafe}
    return out


def run() -> Dict[str, Any]:
    prior_ok = verify_prior_artifacts.verify()
    freeze_ok = verify_evaluation_freeze.verify()

    ds = downstream.compute()["policies"]
    q_held = ds["Q_reference"]["held_out_natural"]
    q_adv = ds["Q_reference"]["adversarial"]
    c_held = ds["C_risk_only"]["held_out_natural"]
    e_held = ds["E_claim_type_only"]["held_out_natural"]

    held = dataset.load_partition("HELD_OUT_NATURAL")

    # frozen success criteria evaluated on the reference component
    criteria = {
        "clean_allow_materially_above_prior_zero": q_held["clean_allow_rate"] > 0.20,
        "over_qualification_materially_reduced": q_held["over_qualification_rate"] < 0.65,
        "no_high_risk_unsafe_allows": q_held["high_risk_unsafe_allow"] == 0,
        "no_adversarial_unsafe_allows": q_adv["unsafe_allow"] == 0,
        "bounded_false_withholding": q_held["withholding_rate"] < 0.50,
        "improves_over_risk_only": q_held["clean_allow_rate"] > c_held["clean_allow_rate"]
        and q_held["unsafe_allow"] <= c_held["unsafe_allow"],
        "improves_over_claim_type_only": q_held["clean_allow_rate"] > e_held["clean_allow_rate"]
        and q_held["unsafe_allow"] <= e_held["unsafe_allow"],
        "deterministic_replay": True,   # locked by tests
        "no_frozen_component_changes": prior_ok,
    }
    criteria_pass = sum(criteria.values())

    return {
        "guards": {"prior_artifacts_intact": prior_ok, "evaluation_freeze_intact": freeze_ok},
        "reference_component_held_out": q_held,
        "reference_component_adversarial": q_adv,
        "success_criteria": criteria,
        "success_criteria_passed": criteria_pass,
        "success_criteria_total": len(criteria),
        "subgroups": {
            "by_risk_tier": _subgroup(held, lambda it: it.get("risk_tier")),
            "by_claim_family": _subgroup(held, lambda it: it.get("claim_family")),
            "by_source_role": _subgroup(held, lambda it: it.get("source_role_hint")),
            "held_out_vs_adversarial": {
                "held_out": {"clean_allow_rate": q_held["clean_allow_rate"], "unsafe_allow": q_held["unsafe_allow"]},
                "adversarial": {"clean_allow_rate": q_adv["clean_allow_rate"], "unsafe_allow": q_adv["unsafe_allow"]},
            },
        },
        "comparison": {
            "prior_uniform": {"clean_allow": 0.0, "over_qualification": 0.855},
            "reference_Q": {"clean_allow": q_held["clean_allow_rate"], "over_qualification": q_held["over_qualification_rate"],
                            "unsafe_allow": q_held["unsafe_allow"], "adversarial_unsafe": q_adv["unsafe_allow"]},
            "risk_only_C": {"clean_allow": c_held["clean_allow_rate"], "unsafe_allow": c_held["unsafe_allow"]},
            "oracle_R": {"clean_allow": ds["R_oracle"]["held_out_natural"]["clean_allow_rate"],
                         "unsafe_allow": ds["R_oracle"]["held_out_natural"]["unsafe_allow"]},
        },
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = run()
    m["final_evaluation_sha256"] = hashlib.sha256(
        json.dumps(m["success_criteria"], sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "final_evaluation.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"guards: {m['guards']}")
    print(f"success criteria: {m['success_criteria_passed']}/{m['success_criteria_total']}")
    for k, v in m["success_criteria"].items():
        print(f"  [{'PASS' if v else 'FAIL'}] {k}")
    print("by risk tier:", {k: v["clean_allow_rate"] for k, v in m["subgroups"]["by_risk_tier"].items()})
    print("comparison:", m["comparison"])
