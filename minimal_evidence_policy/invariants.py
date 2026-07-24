"""Phase 2 - Structural safety invariants (INV-1..INV-12).

Explicit HARD RULES, not learned features. Each invariant inspects the claim's metadata and, when
triggered, forces the obligation UP (never down) or to ER. These are what make the minimal policy safe
where the rich classifier failed (e.g. model self-verification).

Deterministic. Each returns (raised_obligation, triggered_codes).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

from minimal_evidence_policy import schema as s

# claim families considered factual (subject to evidence gates)
_FACTUAL = {"code_behavior", "api_behavior", "measured_performance", "model_quality", "current_fact",
            "historical_fact", "medical", "financial", "legal_interpretation", "scientific", "causal",
            "security_capability", "internal_policy", "external_regulation", "status_report",
            "unsupported_marketing", "attribution"}
_PRODUCTION_CLAIMS = {"measured_performance", "model_quality", "status_report", "security_capability"}


def apply(item: Dict[str, Any], obligation: str) -> Tuple[str, List[str]]:
    """Apply all invariants to a working obligation. Returns (obligation, triggered_codes). Never lowers."""
    codes: List[str] = []
    fam = item.get("claim_family", "")
    role = item.get("source_role", "unknown_source")
    factual = fam in _FACTUAL

    def raise_to(level, code):
        nonlocal obligation
        obligation = s.higher(obligation, level)
        codes.append(code)

    # INV-1 NO MODEL SELF-VERIFICATION
    if role == "model_generated_text" and (factual or item.get("self_verification")):
        raise_to(s.E3, "INV-1.NO_MODEL_SELF_VERIFICATION")
    # INV-2 NO CIRCULAR CORROBORATION
    if item.get("circular_evidence") or item.get("evidence_derives_from_claim"):
        raise_to(s.E3, "INV-2.NO_CIRCULAR_CORROBORATION")
    # INV-3 INTERNAL DOES NOT MEAN AUTHORITATIVE
    if item.get("claims_internal_authority") and not item.get("explicit_authority_basis"):
        raise_to(s.E3, "INV-3.INTERNAL_NOT_AUTHORITATIVE")
    # INV-4 DOCUMENTATION DOES NOT OVERRIDE IMPLEMENTATION
    if item.get("doc_contradicts_impl"):
        raise_to(s.ER, "INV-4.DOC_VS_IMPL_CONFLICT")
    # INV-5 TEST FIXTURE IS NOT PRODUCTION TELEMETRY
    if fam in _PRODUCTION_CLAIMS and item.get("evidence_kind") in ("test_fixture", "mocked", "synthetic_eval"):
        raise_to(s.E3, "INV-5.FIXTURE_NOT_TELEMETRY")
    # INV-6 IMPLEMENTATION DOES NOT PROVE OPERATIONAL PERFORMANCE
    if fam in _PRODUCTION_CLAIMS and item.get("evidence_kind") in ("source_code", "signature"):
        raise_to(s.E3, "INV-6.IMPL_NOT_OPERATIONAL")
    # INV-7 STALE AUTHORITY CANNOT SATISFY CURRENT CLAIM
    if item.get("authority_stale") and (item.get("temporal_sensitivity") in ("time_sensitive", "current_status")
                                        or fam in ("current_fact", "status_report", "internal_policy")):
        raise_to(s.E3, "INV-7.STALE_AUTHORITY")
    # INV-8 ATTRIBUTION IS NOT TRUTH VERIFICATION
    if fam == "attribution" and item.get("treats_attribution_as_truth"):
        raise_to(s.E3, "INV-8.ATTRIBUTION_NOT_TRUTH")
    # INV-10 UNKNOWN FAILS TO REVIEW
    if item.get("risk_tier") == "unknown" or item.get("source_role") == "unknown_source" and item.get("high_impact"):
        raise_to(s.ER, "INV-10.UNKNOWN_TO_REVIEW")
    # INV-11 ACTION AUTHORITY IS SEPARATE FROM FACTUAL SUPPORT
    if item.get("claim_actionability") in ("action_proposal", "action_directive"):
        raise_to(s.E3, "INV-11.ACTION_NEEDS_AUTHORITY")
        if not item.get("approval_evidence"):
            codes.append("INV-11.APPROVAL_ABSENT")
    # INV-12 NO HIGH-RISK E0
    if obligation == s.E0 and item.get("risk_tier") in ("high", "critical"):
        raise_to(s.E1, "INV-12.NO_HIGH_RISK_E0")

    return obligation, codes
