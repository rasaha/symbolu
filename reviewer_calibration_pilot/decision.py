"""Phases 20-21 - Calibration decision + pilot decision.

Evidence-gated from the frozen state. With no real reviewers the human-validation evidence is absent, so
the calibration decision is Option 8 (NOT ENOUGH HUMAN EVIDENCE) and the pilot decision is Option I (NOT
ENOUGH HUMAN EVIDENCE). Deterministic, read-only. Writes eval_results/decision.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from reviewer_calibration_pilot import outcome_review, verify_evaluation_freeze as vef

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

CALIBRATION_OPTIONS = [
    "1 FREEZE POLICY AS VALIDATED", "2 REVISE REVIEWER GUIDE ONLY",
    "3 REVISE ONE OR TWO POLICY RULES", "4 REVISE SOURCE-AUTHORITY METADATA",
    "5 REVISE EVIDENCE BINDING", "6 REQUIRE HUMAN REVIEW FOR ALL NON-LOW-RISK CASES",
    "7 RUN ANOTHER INTERNAL CALIBRATION ROUND", "8 NOT ENOUGH HUMAN EVIDENCE",
    "9 REJECT POLICY FOR OPERATIONAL USE",
]
PILOT_OPTIONS = [
    "A PROCEED TO SINGLE-CUSTOMER EXTERNAL SHADOW PILOT",
    "B PROCEED TO LOW-RISK EXTERNAL SHADOW PILOT ONLY",
    "C PROCEED TO INTERNAL SINGLE-TENANT PILOT", "D PROCEED ONLY WITH MANDATORY HUMAN REVIEW",
    "E FIX REVIEWER GUIDANCE FIRST", "F FIX POLICY RULES FIRST",
    "G FIX SOURCE AUTHORITY OR EVIDENCE BINDING FIRST", "H RUN ANOTHER HUMAN CALIBRATION ROUND",
    "I NOT ENOUGH HUMAN EVIDENCE", "J DO NOT PROCEED",
]


def decide() -> Dict[str, Any]:
    orv = outcome_review.run()
    cfg = vef.build_manifest()["eval_config"]
    human_validated = orv["status"] == "REVIEW_RAN"     # False in this environment

    if not human_validated:
        cal_idx = 7   # Option 8 NOT ENOUGH HUMAN EVIDENCE
        pilot_idx = 8  # Option I NOT ENOUGH HUMAN EVIDENCE
    else:
        cal_idx = 0
        pilot_idx = 2

    return {
        "human_validation": cfg["human_validation"],
        "reviewer_count": cfg["reviewer_count"],
        "outcome_review_status": orv["status"],
        "calibration_decision": CALIBRATION_OPTIONS[cal_idx],
        "pilot_decision": PILOT_OPTIONS[pilot_idx],
        "separated_dimensions": {
            "reviewer_evidence": "NONE (0 real reviewers; min 2)",
            "policy_safety": "technically 0 unsafe (prior track), NOT human-validated",
            "policy_utility": "48% clean allow system output, NOT human-validated",
            "review_burden": "NOT EVALUATED",
            "explanation_quality": "NOT EVALUATED",
            "high_risk_readiness": "NOT EVALUATED",
            "external_pilot_readiness": "BLOCKED (human validation missing)",
            "production_readiness": "NOT established",
        },
        "rationale": (
            "The apparatus, frozen policy runner, ground-truth protocol, metrics, stop conditions, and "
            "evaluation freeze are all complete and ready, but there are 0 real reviewers (minimum 2). "
            "No human agreement, safety, or utility evidence exists, and none may be synthesized from "
            "mock or rubric output. Therefore the calibration decision is Option 8 (NOT ENOUGH HUMAN "
            "EVIDENCE) and the pilot decision is Option I (NOT ENOUGH HUMAN EVIDENCE). External-pilot "
            "progression is not recommended; the constructive next step, when real reviewers are "
            "available, is to run the frozen outcome-bearing review that is already built."),
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = decide()
    m["decision_sha256"] = hashlib.sha256(json.dumps(
        {"cal": m["calibration_decision"], "pilot": m["pilot_decision"]}, sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "decision.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"CALIBRATION DECISION: {m['calibration_decision']}")
    print(f"PILOT DECISION:       {m['pilot_decision']}")
