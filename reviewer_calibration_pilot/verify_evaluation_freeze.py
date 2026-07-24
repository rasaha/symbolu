"""Phase 15 - Evaluation freeze + verifier.

Pins the SHA-256 of the training/final sets and the dry-run artifact, plus the frozen evaluation config
(final set, frozen minimal-policy version, component versions, interface/guide versions, metrics,
thresholds, stop conditions, adjudication rules, reviewer roster, subgroup analyses, stopping rules). The
outcome-bearing review scores the frozen set once; the final set and policy are not altered after
evaluation begins. Distinct from verify_prior_artifacts.py. Deterministic.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

_PKG = os.path.dirname(os.path.abspath(__file__))

FROZEN_ARTIFACTS = [
    "data/training_v1/training.json", "data/final_review_v1/final_review.json", "data/manifest.json",
    "eval_results/dry_run.json",
]

EVAL_CONFIG = {
    "frozen_minimal_policy_version": "minimal_evidence_policy_v1",
    "obligation_vocabulary": ["E0", "E1", "E2", "E3", "E4", "ER"],
    "interface_version": "review_interface_v1",
    "runner_version": "reviewer_calibration_policy_runner_v1",
    "orchestrator_version": "reviewer_calibration_orchestrator_v1",
    "reviewer_guide_version": "reviewer_calibration_pilot/REVIEWER_GUIDE.md",
    "reviewer_roster": [],                     # pseudonymous IDs - EMPTY (no real reviewers)
    "reviewer_count": 0,
    "training_completed": False,
    "metrics": ["acceptable_obligation_agreement", "unsafe_allow_disagreement",
                "high_risk_unsafe_allow_disagreement", "source_authority_agreement",
                "clean_allow_agreement", "override_rate", "review_time"],
    "thresholds": {
        "min_acceptable_obligation_agreement": 0.70, "max_unsafe_allow_disagreement_rate": 0.02,
        "min_high_risk_obligation_agreement": 0.80, "max_stricter_override_rate": 0.40,
        "min_explanation_usefulness": 2.5, "max_unresolved_rate": 0.20,
    },
    "stop_conditions_frozen": True,
    "adjudication": "independent adjudicator; conservative on safety-relevant disagreement; record unresolved",
    "subgroup_analyses": ["risk_tier", "obligation_level", "trap_type", "action_bearing", "source_authority"],
    "human_validation": "NOT_EVALUATED",
    "external_pilot": "BLOCKED (human validation NOT EVALUATED)",
    "no_final_set_tuning": True, "no_policy_change_during_review": True,
}


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def build_manifest() -> dict:
    hashes = {rel: (_sha(os.path.join(_PKG, rel)) if os.path.exists(os.path.join(_PKG, rel)) else None)
              for rel in FROZEN_ARTIFACTS}
    mh = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    return {"eval_config": EVAL_CONFIG, "artifact_sha256": hashes, "manifest_sha256": mh,
            "n_artifacts": len(FROZEN_ARTIFACTS)}


def freeze() -> dict:
    m = build_manifest()
    with open(os.path.join(_PKG, "eval_results", "evaluation_freeze.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


def verify() -> bool:
    p = os.path.join(_PKG, "eval_results", "evaluation_freeze.json")
    if not os.path.exists(p):
        print("MISSING evaluation_freeze.json"); return False
    frozen = json.load(open(p))
    ok = True
    for rel, expect in frozen["artifact_sha256"].items():
        got = _sha(os.path.join(_PKG, rel)) if os.path.exists(os.path.join(_PKG, rel)) else None
        if got != expect:
            print(f"{'MISSING' if got is None else 'DRIFT'}: {rel}"); ok = False
    print(f"evaluation freeze: {frozen['n_artifacts']} artifacts ({'OK' if ok else 'DRIFT'})")
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        sys.exit(0 if verify() else 1)
    m = freeze()
    print(f"evaluation freeze: {m['n_artifacts']} artifacts, manifest {m['manifest_sha256'][:16]}")
