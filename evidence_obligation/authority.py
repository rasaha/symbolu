"""Phase 4 - Authority model.

Authority is what a source can LEGITIMATELY attest to - distinct from its role. A source may be
authoritative for one claim class and not another (code is authoritative for current implementation
behavior but not for production reliability; a user is authoritative for their own preference but not
for a factual claim; a model's own output is never evidence for its own factual claim).

Returns, per (source_role, claim_family), an authority verdict:
  AUTHORITATIVE          - the source can attest to this claim class
  HISTORICAL_ONLY        - authoritative for what occurred, not for current state
  NOT_AUTHORITATIVE      - the source cannot attest to this claim class
  SELF_REFERENTIAL       - the source would be verifying its own claim (circular; unsafe)

Deterministic, fail-closed: unknown pairings are NOT_AUTHORITATIVE.
"""
from __future__ import annotations

from typing import Tuple

from evidence_obligation import source_role as sr

AUTHORITATIVE = "AUTHORITATIVE"
HISTORICAL_ONLY = "HISTORICAL_ONLY"
NOT_AUTHORITATIVE = "NOT_AUTHORITATIVE"
SELF_REFERENTIAL = "SELF_REFERENTIAL"

# claim families each role can attest to (current, non-circular). Anything not listed -> NOT_AUTHORITATIVE.
_ROLE_AUTHORITY = {
    sr.PRIMARY_IMPLEMENTATION: {"code_behavior", "api_behavior", "process_description"},
    sr.TEST_ARTIFACT: {"code_behavior", "api_behavior"},
    sr.APPROVED_POLICY: {"internal_policy", "permission", "prohibition", "requirement"},
    sr.TECHNICAL_DESIGN_DOCUMENT: {"design_rationale", "implementation_plan"},
    sr.OPERATIONAL_RUNBOOK: {"process_description"},
    sr.TELEMETRY_OUTPUT: {"measured_performance", "model_quality", "status_report", "current_fact"},
    sr.AUDIT_LOG: {"historical_fact", "status_report"},
    sr.EXTERNAL_PRIMARY_AUTHORITY: {"external_regulation", "medical", "financial", "legal_interpretation",
                                    "scientific", "historical_fact", "current_fact"},
    sr.USER_STATEMENT: {"user_preference", "subjective_opinion"},
}
# roles that are authoritative only historically (not for current state)
_HISTORICAL_ROLES = {sr.AUDIT_LOG, sr.DRAFT_POLICY}
# roles that must NEVER self-verify their own factual claims
_NON_EVIDENTIARY = {sr.MODEL_GENERATED_TEXT, sr.GENERATED_DOCUMENTATION, sr.INTERNAL_OPINION,
                    sr.EXTERNAL_SECONDARY_SOURCE, sr.DRAFT_POLICY}
# factual claim families that a non-evidentiary source cannot self-support
_FACTUAL = {"historical_fact", "current_fact", "medical", "financial", "scientific", "causal",
            "measured_performance", "model_quality", "external_regulation", "unsupported_marketing"}


def authority_for(source_role: str, claim_family: str) -> Tuple[str, list]:
    """Return (authority_verdict, reason_codes) for a source attesting to a claim family."""
    # a non-evidentiary source verifying its OWN factual claim is circular self-verification
    if source_role in _NON_EVIDENTIARY and claim_family in _FACTUAL:
        return SELF_REFERENTIAL, ["AUTH.SELF_REFERENTIAL"]
    allowed = _ROLE_AUTHORITY.get(source_role, set())
    if claim_family in allowed:
        if source_role in _HISTORICAL_ROLES:
            return HISTORICAL_ONLY, ["AUTH.HISTORICAL_ONLY"]
        return AUTHORITATIVE, ["AUTH.AUTHORITATIVE"]
    return NOT_AUTHORITATIVE, ["AUTH.NOT_AUTHORITATIVE"]     # fail-closed default


def artifact_authority_level(source_role: str) -> str:
    """Coarse artifact-authority level used by the policy engine."""
    if source_role in (sr.APPROVED_POLICY, sr.EXTERNAL_PRIMARY_AUTHORITY, sr.AUDIT_LOG,
                       sr.TELEMETRY_OUTPUT):
        return "high"
    if source_role in (sr.PRIMARY_IMPLEMENTATION, sr.TEST_ARTIFACT, sr.TECHNICAL_DESIGN_DOCUMENT,
                       sr.OPERATIONAL_RUNBOOK):
        return "medium"
    if source_role in (sr.DRAFT_POLICY, sr.USER_STATEMENT):
        return "low"
    return "none"
