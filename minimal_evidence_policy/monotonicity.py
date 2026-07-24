"""Phase 15 - Monotonicity and invariant testing.

Exhaustively verifies that increasing any risk-relevant dimension NEVER lowers the obligation. Any
violation is a pilot blocker. Deterministic, read-only.
"""
from __future__ import annotations

import itertools
from typing import Any, Dict, List

from minimal_evidence_policy import classifier, schema as s

_RISK_ORDER = ["low", "medium", "high", "critical"]
_FAMILIES = ["subjective_opinion", "process_description", "code_behavior", "internal_policy",
             "current_fact", "measured_performance", "security_capability", "medical",
             "action_proposal", "attribution", "recommendation", "scientific"]

# each transform monotonically INCREASES a dimension; obligation must not drop
_TRANSFORMS = {
    "raise_risk": lambda it: {**it, "risk_tier": _next(_RISK_ORDER, it.get("risk_tier", "low"))},
    "add_actionability": lambda it: {**it, "claim_actionability": "action_directive"},
    "add_temporal": lambda it: {**it, "temporal_sensitivity": "current_status"},
    "source_to_unknown": lambda it: {**it, "source_role": "unknown_source", "high_impact": True},
    "add_contradiction": lambda it: {**it, "doc_contradicts_impl": True},
    "add_regulated": lambda it: {**it, "claim_family": "medical"},
    "add_self_verification": lambda it: {**it, "source_role": "model_generated_text", "self_verification": True},
    "add_ambiguity": lambda it: {**it, "risk_tier": "unknown"},
    "remove_approval": lambda it: {**it, "claim_actionability": "action_directive", "approval_evidence": False},
    "add_high_impact": lambda it: {**it, "high_impact": True},
    "add_absolute_stale": lambda it: {**it, "authority_stale": True, "temporal_sensitivity": "current_status"},
}


def _next(order: List[str], val: str) -> str:
    if val not in order:
        return val
    i = order.index(val)
    return order[min(i + 1, len(order) - 1)]


def _base_items() -> List[Dict[str, Any]]:
    out = []
    for fam, risk in itertools.product(_FAMILIES, _RISK_ORDER):
        out.append({"artifact_id": f"{fam}-{risk}", "claim_family": fam, "risk_tier": risk,
                    "source_role": "generated_documentation"})
    return out


def check() -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []
    tested = 0
    for it in _base_items():
        before = s.RANK[classifier.classify(it).final_obligation]
        for name, tf in _TRANSFORMS.items():
            after_item = tf(it)
            after = s.RANK[classifier.classify(after_item).final_obligation]
            tested += 1
            if after < before:                       # obligation DROPPED after an increase -> violation
                violations.append({"base": it["artifact_id"], "transform": name,
                                   "before_rank": before, "after_rank": after})
    return {
        "tested_transitions": tested,
        "violations": len(violations),
        "monotonic": len(violations) == 0,
        "blocker": len(violations) > 0,             # PILOT BLOCKER on any violation
        "violation_examples": violations[:10],
        "transforms": list(_TRANSFORMS),
    }


if __name__ == "__main__":
    m = check()
    print(f"tested transitions: {m['tested_transitions']}")
    print(f"monotonicity violations: {m['violations']} -> monotonic={m['monotonic']} blocker={m['blocker']}")
    if m["violation_examples"]:
        for v in m["violation_examples"]:
            print(" ", v)
