"""Phase 16 - Outcome-bearing review.

The outcome-bearing review runs ONLY with >= 2 authorized real reviewers who have completed
qualification. This module checks that precondition against the frozen evaluation config. With an empty
roster (no real reviewers), it returns NOT_ENOUGH_HUMAN_EVIDENCE and runs no review - it never
substitutes mock or rubric output for human labels.

Deterministic, read-only. Writes eval_results/outcome_review.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from reviewer_calibration_pilot import verify_evaluation_freeze as vef

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")
MIN_REAL_REVIEWERS = 2


def run() -> Dict[str, Any]:
    cfg = vef.build_manifest()["eval_config"]
    reviewer_count = cfg["reviewer_count"]
    training_completed = cfg["training_completed"]

    eligible = reviewer_count >= MIN_REAL_REVIEWERS and training_completed
    if not eligible:
        return {
            "status": "NOT_ENOUGH_HUMAN_EVIDENCE",
            "reviewer_count": reviewer_count,
            "min_required": MIN_REAL_REVIEWERS,
            "training_completed": training_completed,
            "reviews_run": 0,
            "human_records": 0,
            "note": ("Fewer than 2 authorized real reviewers with completed qualification. Per the "
                     "governing protocol, the outcome-bearing review does NOT run; no mock or rubric "
                     "output is used as human validation. External-pilot progression is not recommended."),
        }
    # (real-reviewer path - not reachable in this environment)
    return {"status": "REVIEW_RAN", "reviewer_count": reviewer_count, "reviews_run": 0,
            "note": "real-reviewer path"}


def freeze() -> Dict[str, Any]:
    import hashlib
    m = run()
    m["outcome_review_sha256"] = hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "outcome_review.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"OUTCOME-BEARING REVIEW: status={m['status']}")
    print(f"  reviewer_count={m['reviewer_count']} min_required={m['min_required']} "
          f"training_completed={m['training_completed']} reviews_run={m['reviews_run']}")
    print(f"  {m['note']}")
