"""Phase 3 - Claim-to-obligation taxonomy.

Maps each claim family to a DEFAULT evidence obligation plus adjustment rules (risk escalation,
source-role/authority adjustment, freshness, independence, allowable evidence classes). Data only - the
classifier (Phase 9) applies these; the policy engine composes them with risk/source/authority.

Fail-closed: an unrecognized claim family defaults to QUALIFY_BY_DEFAULT (not a low-burden class).
"""
from __future__ import annotations

from typing import Dict, List

from evidence_obligation import schema as s

# claim_family -> rule dict:
#   default: default obligation type
#   high_risk: obligation when risk is high/critical (escalation)
#   allow_classes: evidence source classes that can satisfy the obligation
#   freshness / independence: default requirement flags
#   unsafe_if: the unsafe misclassification to guard against
TAXONOMY: Dict[str, Dict] = {
    "code_behavior": {
        "default": s.IMPLEMENTATION_EVIDENCE_SUFFICIENT, "high_risk": s.TELEMETRY_OR_MEASUREMENT_REQUIRED,
        "allow_classes": ["source_code", "unit_test", "integration_test"],
        "freshness": False, "independence": False,
        "unsafe_if": "treating a comment as behavior evidence"},
    "api_behavior": {
        "default": s.IMPLEMENTATION_EVIDENCE_SUFFICIENT, "high_risk": s.TELEMETRY_OR_MEASUREMENT_REQUIRED,
        "allow_classes": ["source_code", "schema", "integration_test"],
        "freshness": False, "independence": False, "unsafe_if": "signature != runtime behavior"},
    "internal_policy": {
        "default": s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT,
        "high_risk": s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED,
        "allow_classes": ["approved_policy", "signed_spec"], "freshness": True, "independence": False,
        "unsafe_if": "draft/expired policy treated as approved/current"},
    "external_regulation": {
        "default": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "high_risk": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "allow_classes": ["external_primary_authority"], "freshness": True, "independence": True,
        "unsafe_if": "internal artifact treated as regulatory authority"},
    "product_capability": {
        "default": s.IMPLEMENTATION_EVIDENCE_SUFFICIENT, "high_risk": s.INDEPENDENT_CORROBORATION_REQUIRED,
        "allow_classes": ["source_code", "integration_test"], "freshness": False, "independence": False,
        "unsafe_if": "marketing capability treated as implemented"},
    "measured_performance": {
        "default": s.TELEMETRY_OR_MEASUREMENT_REQUIRED, "high_risk": s.TELEMETRY_OR_MEASUREMENT_REQUIRED,
        "allow_classes": ["telemetry", "measurement"], "freshness": True, "independence": False,
        "unsafe_if": "test fixture treated as production telemetry"},
    "model_quality": {
        "default": s.TELEMETRY_OR_MEASUREMENT_REQUIRED, "high_risk": s.INDEPENDENT_CORROBORATION_REQUIRED,
        "allow_classes": ["measurement", "benchmark_raw"], "freshness": True, "independence": False,
        "unsafe_if": "benchmark claim without raw results"},
    "historical_fact": {
        "default": s.INDEPENDENT_CORROBORATION_REQUIRED, "high_risk": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "allow_classes": ["external_primary_authority", "audit_log"], "freshness": False, "independence": True,
        "unsafe_if": "unsourced historical assertion"},
    "current_fact": {
        "default": s.TEMPORAL_VERIFICATION_REQUIRED, "high_risk": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "allow_classes": ["external_primary_authority", "telemetry"], "freshness": True, "independence": True,
        "unsafe_if": "stale claim treated as current"},
    "medical": {
        "default": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, "high_risk": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "allow_classes": ["external_primary_authority"], "freshness": True, "independence": True,
        "unsafe_if": "any low-burden shortcut"},
    "financial": {
        "default": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, "high_risk": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "allow_classes": ["external_primary_authority"], "freshness": True, "independence": True,
        "unsafe_if": "any low-burden shortcut"},
    "legal_interpretation": {
        "default": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED, "high_risk": s.HUMAN_REVIEW_REQUIRED,
        "allow_classes": ["external_primary_authority"], "freshness": True, "independence": True,
        "unsafe_if": "opinion treated as legal fact"},
    "scientific": {
        "default": s.INDEPENDENT_CORROBORATION_REQUIRED, "high_risk": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "allow_classes": ["external_primary_authority", "measurement"], "freshness": False, "independence": True,
        "unsafe_if": "single-source scientific claim"},
    "attribution": {
        "default": s.ATTRIBUTION_VERIFICATION_REQUIRED, "high_risk": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "allow_classes": ["quoted_source", "cited_source"], "freshness": False, "independence": False,
        "unsafe_if": "attribution verification treated as truth verification"},
    "recommendation": {
        "default": s.CONTEXTUAL_SUPPORT_SUFFICIENT, "high_risk": s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED,
        "allow_classes": ["context"], "freshness": False, "independence": False,
        "unsafe_if": "high-impact recommendation with no authority"},
    "action_proposal": {
        "default": s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED, "high_risk": s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED,
        "allow_classes": ["approval_record", "authority_grant"], "freshness": True, "independence": False,
        "unsafe_if": "action without policy/approval evidence"},
    "permission": {
        "default": s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED, "high_risk": s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED,
        "allow_classes": ["approved_policy", "authority_grant"], "freshness": True, "independence": False,
        "unsafe_if": "permission asserted without authority"},
    "prohibition": {
        "default": s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT, "high_risk": s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED,
        "allow_classes": ["approved_policy"], "freshness": True, "independence": False,
        "unsafe_if": "unsourced prohibition"},
    "requirement": {
        "default": s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT, "high_risk": s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED,
        "allow_classes": ["approved_policy", "signed_spec"], "freshness": True, "independence": False,
        "unsafe_if": "draft requirement treated as approved"},
    "user_preference": {
        "default": s.NO_FACTUAL_EVIDENCE_GATE, "high_risk": s.CONTEXTUAL_SUPPORT_SUFFICIENT,
        "allow_classes": [], "freshness": False, "independence": False,
        "unsafe_if": "factual claim disguised as preference"},
    "subjective_opinion": {
        "default": s.NO_FACTUAL_EVIDENCE_GATE, "high_risk": s.CONTEXTUAL_SUPPORT_SUFFICIENT,
        "allow_classes": [], "freshness": False, "independence": False,
        "unsafe_if": "consequential claim disguised as opinion"},
    "hypothetical": {
        "default": s.NO_FACTUAL_EVIDENCE_GATE, "high_risk": s.CONTEXTUAL_SUPPORT_SUFFICIENT,
        "allow_classes": [], "freshness": False, "independence": False,
        "unsafe_if": "real claim framed as hypothetical"},
    "mathematical": {
        "default": s.LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED,
        "high_risk": s.LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED,
        "allow_classes": ["derivation", "computation"], "freshness": False, "independence": False,
        "unsafe_if": "unverified calculation asserted"},
    "causal": {
        "default": s.INDEPENDENT_CORROBORATION_REQUIRED, "high_risk": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "allow_classes": ["measurement", "external_primary_authority"], "freshness": False, "independence": True,
        "unsafe_if": "correlation asserted as causation"},
    "prediction": {
        "default": s.QUALIFY_BY_DEFAULT, "high_risk": s.INDEPENDENT_CORROBORATION_REQUIRED,
        "allow_classes": ["measurement"], "freshness": True, "independence": False,
        "unsafe_if": "speculative prediction asserted as fact"},
    "uncertainty": {
        "default": s.CONTEXTUAL_SUPPORT_SUFFICIENT, "high_risk": s.QUALIFY_BY_DEFAULT,
        "allow_classes": ["context"], "freshness": False, "independence": False,
        "unsafe_if": "hedged high-risk claim under-gated"},
    "process_description": {
        "default": s.CONTEXTUAL_SUPPORT_SUFFICIENT, "high_risk": s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT,
        "allow_classes": ["context", "source_code"], "freshness": False, "independence": False,
        "unsafe_if": "description treated as guarantee"},
    "implementation_plan": {
        "default": s.CONTEXTUAL_SUPPORT_SUFFICIENT, "high_risk": s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT,
        "allow_classes": ["context"], "freshness": False, "independence": False,
        "unsafe_if": "plan treated as completed capability"},
    "design_rationale": {
        "default": s.CONTEXTUAL_SUPPORT_SUFFICIENT, "high_risk": s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT,
        "allow_classes": ["context"], "freshness": False, "independence": False,
        "unsafe_if": "rationale treated as evidence of correctness"},
    "status_report": {
        "default": s.TEMPORAL_VERIFICATION_REQUIRED, "high_risk": s.TELEMETRY_OR_MEASUREMENT_REQUIRED,
        "allow_classes": ["telemetry", "audit_log"], "freshness": True, "independence": False,
        "unsafe_if": "stale status treated as current"},
    "unsupported_marketing": {
        "default": s.INDEPENDENT_CORROBORATION_REQUIRED, "high_risk": s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED,
        "allow_classes": ["measurement", "external_primary_authority"], "freshness": False, "independence": True,
        "unsafe_if": "marketing superlative treated as fact"},
}

CLAIM_FAMILIES = tuple(TAXONOMY.keys())


def default_obligation(claim_family: str, risk_tier: str) -> str:
    rule = TAXONOMY.get(claim_family)
    if rule is None:
        return s.QUALIFY_BY_DEFAULT                       # fail-closed: unknown family is NOT low-burden
    if risk_tier in ("high", "critical"):
        return rule["high_risk"]
    return rule["default"]


def rule_for(claim_family: str) -> Dict:
    return TAXONOMY.get(claim_family, {"default": s.QUALIFY_BY_DEFAULT, "high_risk": s.QUALIFY_BY_DEFAULT,
                                       "allow_classes": [], "freshness": False, "independence": False,
                                       "unsafe_if": "unknown family"})
