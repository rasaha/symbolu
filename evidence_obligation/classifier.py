"""Phase 9 - Top-level EvidenceObligation classifier entry point.

Thin wrapper over the policy engine that yields a validated EvidenceObligation for an item and never
raises: any structural violation forces INDETERMINATE_OBLIGATION + HUMAN_REVIEW (fail-closed).
"""
from __future__ import annotations

from typing import Any, Dict

from evidence_obligation import schema as s
from evidence_obligation import policy


def classify(item: Dict[str, Any]) -> s.EvidenceObligation:
    try:
        o = policy.assign(item)
    except Exception as e:  # fail-closed
        o = s.new_obligation(item.get("artifact_id", "claim"), item.get("source_path", ""),
                             evidence_obligation_type=s.INDETERMINATE_OBLIGATION,
                             human_review_requirement=True, unresolved_ambiguity=True,
                             reason_codes=[f"CLASSIFIER.EXCEPTION:{type(e).__name__}"])
        return o
    violations = s.validate_obligation(o)
    if violations:
        # a structurally invalid obligation must never stand - escalate to human review
        o.evidence_obligation_type = s.HUMAN_REVIEW_REQUIRED
        o.human_review_requirement = True
        o.reason_codes = o.reason_codes + [f"CLASSIFIER.STRUCTURAL_VIOLATION:{v}" for v in violations]
    return o
