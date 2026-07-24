"""Phases 12-13 - Human-review study.

Real reviewers are NOT available in this environment, so human validation is marked NOT EVALUATED. This
module computes an independent-rubric PROXY on the human-review set - explicitly labelled as NOT human
validation - to characterize label stability and where the minimal policy and the independent gold
diverge. It never claims to be human validation.

Deterministic, read-only. Writes eval_results/review_study.json.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict

from minimal_evidence_policy import dataset, classifier, ground_truth as gt, schema as s

_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

HUMAN_VALIDATION = "NOT_EVALUATED"   # no real reviewers available


def compute() -> Dict[str, Any]:
    review = dataset.load_partition("HUMAN_REVIEW_SET")
    n = len(review)
    rubric_agree = policy_matches_gold = policy_safe_dir = 0
    override_stricter = override_looser = 0

    for it in review:
        # two independent rubrics (proxy reviewers) - NOT humans
        a, b = it["annotator_A"], it["annotator_B"]
        if a == b:
            rubric_agree += 1
        pred = classifier.classify(it).final_obligation
        gold = it["gold_obligation"]
        if pred == gold:
            policy_matches_gold += 1
        # safe direction = policy >= gold (never weaker)
        if s.RANK[pred] >= s.RANK[gold]:
            policy_safe_dir += 1
        else:
            override_looser += 1
        if s.RANK[pred] > s.RANK[gold]:
            override_stricter += 1

    return {
        "human_validation": HUMAN_VALIDATION,
        "method": "independent dual-rubric PROXY on the human-review set - NOT human validation",
        "n": n,
        "rubric_agreement": round(rubric_agree / n, 4),
        "policy_matches_gold": round(policy_matches_gold / n, 4),
        "policy_at_or_above_gold_rate": round(policy_safe_dir / n, 4),
        "policy_below_gold_count": override_looser,       # would-be unsafe overrides (should be ~0)
        "policy_above_gold_count": override_stricter,
        "caveat": "Human validation NOT EVALUATED (no real reviewers). This proxy characterizes label "
                  "stability only and must not be reported as human validation; an external pilot is "
                  "not recommended on this basis.",
    }


def freeze() -> Dict[str, Any]:
    import hashlib
    m = compute()
    m["review_sha256"] = hashlib.sha256(json.dumps(m, sort_keys=True).encode()).hexdigest()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "review_study.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True); fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"human_validation={m['human_validation']}")
    print(f"rubric_agreement={m['rubric_agreement']} policy_matches_gold={m['policy_matches_gold']} "
          f"policy>=gold={m['policy_at_or_above_gold_rate']} policy<gold={m['policy_below_gold_count']}")
