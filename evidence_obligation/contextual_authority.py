"""Phase 11 - Contextual authority validation.

Tests whether an artifact may serve as evidence for its OWN claims, across the canonical cases. Reuses
authority.py (the component under test) and measures: true authority recognition, false authority,
circular self-verification, stale authority, and unsafe self-support. Deterministic.
"""
from __future__ import annotations

from typing import Any, Dict

from evidence_obligation import authority as au, source_role as sr

# (label, source_role, claim_family, expected_verdict)
CASES = [
    ("implementation code describing current behavior", sr.PRIMARY_IMPLEMENTATION, "code_behavior", au.AUTHORITATIVE),
    ("comment contradicting implementation", sr.INTERNAL_OPINION, "code_behavior", au.NOT_AUTHORITATIVE),
    ("README contradicting code", sr.GENERATED_DOCUMENTATION, "code_behavior", au.NOT_AUTHORITATIVE),
    ("approved policy", sr.APPROVED_POLICY, "internal_policy", au.AUTHORITATIVE),
    ("draft policy", sr.DRAFT_POLICY, "internal_policy", au.NOT_AUTHORITATIVE),
    ("expired policy", sr.DRAFT_POLICY, "internal_policy", au.NOT_AUTHORITATIVE),
    ("test result", sr.TEST_ARTIFACT, "code_behavior", au.AUTHORITATIVE),
    ("benchmark claim without raw results", sr.GENERATED_DOCUMENTATION, "measured_performance", au.SELF_REFERENTIAL),
    ("telemetry summary", sr.TELEMETRY_OUTPUT, "measured_performance", au.AUTHORITATIVE),
    ("raw telemetry", sr.TELEMETRY_OUTPUT, "status_report", au.AUTHORITATIVE),
    ("generated report", sr.GENERATED_DOCUMENTATION, "current_fact", au.SELF_REFERENTIAL),
    ("user preference", sr.USER_STATEMENT, "user_preference", au.AUTHORITATIVE),
    ("model self-description", sr.MODEL_GENERATED_TEXT, "current_fact", au.SELF_REFERENTIAL),
    ("vendor marketing copy", sr.EXTERNAL_SECONDARY_SOURCE, "unsupported_marketing", au.SELF_REFERENTIAL),
    ("signed approval record", sr.APPROVED_POLICY, "permission", au.AUTHORITATIVE),
    ("audit log of what occurred", sr.AUDIT_LOG, "historical_fact", au.HISTORICAL_ONLY),
]


def validate() -> Dict[str, Any]:
    rows = []
    true_authority = false_authority = circular = stale = unsafe_self_support = correct = 0
    for label, role, fam, expected in CASES:
        got, codes = au.authority_for(role, fam)
        ok = got == expected
        correct += ok
        if got == au.AUTHORITATIVE:
            true_authority += 1
        if got == au.SELF_REFERENTIAL:
            circular += 1
        if got == au.HISTORICAL_ONLY:
            stale += 1
        # false authority = claimed AUTHORITATIVE where expected NOT/self-referential
        if got == au.AUTHORITATIVE and expected in (au.NOT_AUTHORITATIVE, au.SELF_REFERENTIAL):
            false_authority += 1
        # unsafe self-support = a non-evidentiary source graded AUTHORITATIVE for a factual claim
        if got == au.AUTHORITATIVE and expected == au.SELF_REFERENTIAL:
            unsafe_self_support += 1
        rows.append({"case": label, "expected": expected, "got": got, "ok": ok})
    return {
        "n": len(CASES), "correct": correct, "accuracy": round(correct / len(CASES), 4),
        "true_authority_recognized": true_authority, "false_authority": false_authority,
        "circular_self_verification_detected": circular, "stale_authority_detected": stale,
        "unsafe_self_support": unsafe_self_support, "rows": rows,
    }
