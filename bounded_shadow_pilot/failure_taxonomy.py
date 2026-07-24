"""Phase 13 - Natural-language failure taxonomy.

Categorizes how the full governed stack behaves on natural artifacts vs how it behaved on the
structured corpus, and tags each artifact with the natural-language CAUSE. Empirical (derived from the
frozen runtime's own outputs), deterministic, read-only.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from governed_inference_pilot import orchestrator as gip_orch

from bounded_shadow_pilot import case_builder, metrics

_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "natural_pilot_v1")
_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "eval_results")

# behavior categories (mutually exclusive)
CATEGORIES = ["CLEAN_TRANSFER", "OVER_QUALIFICATION", "FALSE_WITHHOLD", "CORRECT_REVIEW",
              "RESIDUAL_UNSAFE_QUALIFY", "UNSAFE_PERMIT"]


def _load():
    corpus = json.load(open(os.path.join(_DATA, "corpus.json")))
    gt = json.load(open(os.path.join(_DATA, "ground_truth.json")))
    return corpus["artifacts"], {g["artifact_id"]: g for g in gt["labels"]}


def _categorize(gt_class: str, final: str) -> str:
    dec = metrics.decision_of(final)
    if gt_class == "ALLOW":
        if final == "WOULD_ALLOW":
            return "CLEAN_TRANSFER"
        if final == "WOULD_QUALIFY":
            return "OVER_QUALIFICATION"
        return "FALSE_WITHHOLD"
    # gt REVIEW
    if final == "WOULD_ALLOW":
        return "UNSAFE_PERMIT"
    if final == "WOULD_QUALIFY":
        return "RESIDUAL_UNSAFE_QUALIFY"
    return "CORRECT_REVIEW"


def _nl_cause(a: Dict[str, Any], gt: Dict[str, Any], evidence_state: str) -> List[str]:
    tags = []
    if evidence_state == "VERIFIED_WITH_LIMITATIONS":
        tags.append("NO_EXTERNAL_EVIDENCE")          # documentation lacks a verifiable evidence bundle
    if gt.get("gt_needs_evidence"):
        tags.append("STRONG_CLAIM_UNBACKED")
    if gt.get("gt_security_sensitive"):
        tags.append("SECURITY_SENSITIVE")
    if gt.get("gt_uncertain"):
        tags.append("HEDGED_UNCERTAIN")
    if not tags:
        tags.append("PLAIN_DESCRIPTIVE")
    return tags


def build() -> Dict[str, Any]:
    artifacts, gts = _load()
    artifacts = sorted(artifacts, key=lambda x: x["artifact_id"])

    cat_counts = {c: 0 for c in CATEGORIES}
    cat_examples: Dict[str, List[str]] = {c: [] for c in CATEGORIES}
    cause_counts: Dict[str, int] = {}
    cause_by_category: Dict[str, Dict[str, int]] = {c: {} for c in CATEGORIES}

    for a in artifacts:
        gt = gts[a["artifact_id"]]
        case = case_builder.build_case(a, gt)
        final = gip_orch.run_case(case, config="FULL_STACK_HIGH_RISK").final_shadow_disposition
        cat = _categorize(gt["gt_expected_class"], final)
        cat_counts[cat] += 1
        if len(cat_examples[cat]) < 5:
            cat_examples[cat].append(a["artifact_id"])
        for tag in _nl_cause(a, gt, case["evidence_steer"]["evidence_state"]):
            cause_counts[tag] = cause_counts.get(tag, 0) + 1
            cause_by_category[cat][tag] = cause_by_category[cat].get(tag, 0) + 1

    n = len(artifacts)
    return {
        "corpus_id": "natural_pilot_v1",
        "n": n,
        "config": "FULL_STACK_HIGH_RISK",
        "category_counts": cat_counts,
        "category_rates": {c: round(cat_counts[c] / n, 4) for c in CATEGORIES},
        "category_examples": cat_examples,
        "nl_cause_counts": dict(sorted(cause_counts.items(), key=lambda kv: -kv[1])),
        "nl_cause_by_category": cause_by_category,
        "interpretation": {
            "dominant_failure": max(CATEGORIES, key=lambda c: cat_counts[c]),
            "over_qualification_driver": "NO_EXTERNAL_EVIDENCE (natural docs lack verifiable evidence "
                                         "bundles; derived evidence base is VERIFIED_WITH_LIMITATIONS)",
        },
    }


def freeze() -> Dict[str, Any]:
    m = build()
    os.makedirs(_OUT, exist_ok=True)
    with open(os.path.join(_OUT, "failure_taxonomy.json"), "w") as fh:
        json.dump(m, fh, indent=2, sort_keys=True)
        fh.write("\n")
    return m


if __name__ == "__main__":
    m = freeze()
    print(f"failure taxonomy on n={m['n']} (config {m['config']})")
    for c in CATEGORIES:
        print(f"  {c:24s} {m['category_counts'][c]:4d}  ({m['category_rates'][c]*100:.1f}%)")
    print("nl causes:", m["nl_cause_counts"])
    print("dominant:", m["interpretation"]["dominant_failure"])
