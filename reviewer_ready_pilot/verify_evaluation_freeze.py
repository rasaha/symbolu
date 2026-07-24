"""Phase 20 - Future human-evaluation protocol freeze + verifier.

Pins the SHA-256 of the frozen training/final sets and manifest, plus the FUTURE human-evaluation config:
the metrics, thresholds, stop conditions, adjudication rules, subgroup analyses, and decision rules that a
real human pilot MUST use, frozen NOW so they cannot be tuned after seeing real reviewer results.

The freeze is explicit that no human evaluation has occurred: reviewer_roster is empty, reviewer_count is
0, human_validation is NOT_EVALUATED, external_pilot is BLOCKED, production_readiness is NOT_READY. Freezing
the protocol is a readiness step; it is NOT evidence of human agreement.

Distinct from verify_prior_artifacts.py (which guards prior tracks). Deterministic, stdlib-only.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

from reviewer_ready_pilot import stop_conditions as sc

_PKG = os.path.dirname(os.path.abspath(__file__))

FROZEN_ARTIFACTS = [
    "data/training_v1/training.json",
    "data/final_review_v1/final_review.json",
    "data/manifest.json",
]

# The protocol a future human pilot MUST follow. Frozen before any real reviewer runs.
FUTURE_EVAL_CONFIG = {
    "frozen_minimal_policy_version": "minimal_evidence_policy_v1",
    "policy_modified": False,
    "obligation_vocabulary": ["E0", "E1", "E2", "E3", "E4", "ER"],
    "native_actiongate_outcomes": ["ALLOW", "ALLOW_WITH_CONSTRAINTS", "DENY", "ESCALATE_TO_HUMAN",
                                   "REQUEST_MORE_EVIDENCE", "SIMULATE_AND_RETRY"],
    "label_schema_version": "reviewer_label_v1",
    "interface_version": "review_interface_v1",
    "runner_version": "reviewer_ready_policy_runner_v1",
    "audit_version": "review_audit_v1",
    "reviewers_per_artifact": 2,
    "reviewer_roster": [],                 # pseudonymous IDs - EMPTY (no real reviewers)
    "reviewer_count": 0,
    "qualification_required": True,
    "qualification_source": "training set only (never the final set)",
    "metrics": ["reviewer_reviewer_agreement", "reviewer_system_agreement", "trap_catch_rate",
                "override_rate", "disagreement_taxonomy"],
    "frozen_thresholds": sc.FROZEN_THRESHOLDS,
    "immediate_stop_conditions": sc._IMMEDIATE,
    "adjudication": "separated adjudicator; UNRESOLVED is a valid terminus; never forces consensus",
    "subgroup_analyses": ["risk_tier", "claim_family", "trap_type", "edge_type", "action_bearing",
                          "source_kind"],
    "decision_rule": "Metrics describe reviewer behaviour only. No metric outcome converts to a claim of "
                     "policy correctness or human validation without a separately-scoped human study.",
    "no_final_set_tuning": True,
    "no_threshold_lowering": True,
    "no_policy_change_during_review": True,
    "human_validation": "NOT_EVALUATED",
    "external_customer_pilot": "BLOCKED (human validation NOT EVALUATED)",
    "production_readiness": "NOT_READY",
    "enforcement": "DISABLED",
}


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def build_manifest() -> dict:
    hashes = {rel: (_sha(os.path.join(_PKG, rel)) if os.path.exists(os.path.join(_PKG, rel)) else None)
              for rel in FROZEN_ARTIFACTS}
    mh = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    ch = hashlib.sha256(json.dumps(FUTURE_EVAL_CONFIG, sort_keys=True).encode()).hexdigest()
    return {"future_eval_config": FUTURE_EVAL_CONFIG, "config_sha256": ch,
            "artifact_sha256": hashes, "manifest_sha256": mh, "n_artifacts": len(FROZEN_ARTIFACTS)}


def freeze() -> dict:
    m = build_manifest()
    os.makedirs(os.path.join(_PKG, "eval_results"), exist_ok=True)
    with open(os.path.join(_PKG, "eval_results", "future_evaluation_freeze.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


def verify() -> bool:
    p = os.path.join(_PKG, "eval_results", "future_evaluation_freeze.json")
    if not os.path.exists(p):
        print("MISSING future_evaluation_freeze.json"); return False
    frozen = json.load(open(p))
    ok = True
    for rel, expect in frozen["artifact_sha256"].items():
        got = _sha(os.path.join(_PKG, rel)) if os.path.exists(os.path.join(_PKG, rel)) else None
        if got != expect:
            print(f"{'MISSING' if got is None else 'DRIFT'}: {rel}"); ok = False
    cur_cfg = hashlib.sha256(json.dumps(FUTURE_EVAL_CONFIG, sort_keys=True).encode()).hexdigest()
    if cur_cfg != frozen["config_sha256"]:
        print("DRIFT: future_eval_config changed after freeze"); ok = False
    # honesty invariants must remain
    cfg = frozen["future_eval_config"]
    for k, v in (("human_validation", "NOT_EVALUATED"), ("production_readiness", "NOT_READY"),
                 ("policy_modified", False), ("enforcement", "DISABLED")):
        if cfg.get(k) != v:
            print(f"INVARIANT VIOLATED: {k} != {v}"); ok = False
    print(f"future evaluation freeze: {frozen['n_artifacts']} artifacts ({'OK' if ok else 'DRIFT'})")
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "verify":
        sys.exit(0 if verify() else 1)
    m = freeze()
    print(f"future evaluation freeze: {m['n_artifacts']} artifacts, manifest {m['manifest_sha256'][:16]}")
