"""Phase 10 - Obligation -> EvidenceAssurance contract.

Translates an evidence obligation + the evidence actually AVAILABLE into the evidence_steer the FROZEN
EvidenceAssurance consumes. EvidenceAssurance remains responsible for judging sufficiency; this adapter
only expresses, honestly, whether the APPLICABLE standard is met by the available evidence.

The cardinal rule (never violated): "no external evidence required" is NOT transformed into "claim is
verified true". A low-external-burden obligation whose standard is met by the artifact maps to an
OBLIGATION-RELATIVE VERIFIED - reason-coded as "standard met by context/implementation; factual truth
not independently established". A HIGH-external-burden obligation WITHOUT external evidence never maps to
VERIFIED (stays INSUFFICIENT) - this is what preserves safety.

Read-only over frozen EA. Deterministic.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from evidence_obligation import schema as s

CONTRACT_VERSION = "obligation_ea_contract_v1"

# frozen EA evidence states (delivery effect in comments)
_VERIFIED = "VERIFIED"                          # -> ALLOW
_VWL = "VERIFIED_WITH_LIMITATIONS"              # -> QUALIFY
_INSUFFICIENT = "INSUFFICIENT"                  # -> INDETERMINATE (withhold)
_CONFLICTED = "CONFLICTED"                      # -> ESCALATE
_ESCALATE = "ESCALATE"                          # -> ESCALATE
_INDETERMINATE = "INDETERMINATE"               # -> INDETERMINATE


def available_evidence_for(o: s.EvidenceObligation,
                           override: Optional[Dict[str, bool]] = None) -> Dict[str, bool]:
    """What evidence is intrinsically available for a natural artifact. Natural artifacts carry NO
    external/telemetry/policy/approval evidence unless explicitly injected (error-propagation study)."""
    av = {
        "implementation": o.implementation_inspectability,
        "internal_authoritative": o.artifact_authority == "high",
        "context": True,                          # local context always present
        "external": False, "telemetry": False, "policy": False, "approval": False,
        "attribution_verified": False, "temporal_current": False, "logical_checked": False,
    }
    if override:
        av.update(override)
    return av


def obligation_to_evidence_state(o: s.EvidenceObligation,
                                 available: Dict[str, bool]) -> Tuple[str, list, bool]:
    """Return (evidence_state, reason_codes, obligation_relative). obligation_relative=True marks a
    VERIFIED that is relative to a met contextual/implementation standard, not a truth claim."""
    t = o.evidence_obligation_type
    R = "EOC"

    # --- low-external-burden: satisfiable by the artifact's OWN evidence ---
    if t == s.NO_FACTUAL_EVIDENCE_GATE:
        return _VERIFIED, [f"{R}.NO_FACTUAL_GATE", f"{R}.OBLIGATION_RELATIVE"], True
    if t == s.CONTEXTUAL_SUPPORT_SUFFICIENT:
        return (_VERIFIED, [f"{R}.CONTEXT_MET", f"{R}.OBLIGATION_RELATIVE"], True) if available["context"] \
            else (_VWL, [f"{R}.CONTEXT_PARTIAL"], False)
    if t == s.IMPLEMENTATION_EVIDENCE_SUFFICIENT:
        return (_VERIFIED, [f"{R}.IMPL_MET", f"{R}.OBLIGATION_RELATIVE"], True) if available["implementation"] \
            else (_INSUFFICIENT, [f"{R}.IMPL_ABSENT"], False)
    if t == s.INTERNAL_AUTHORITATIVE_ARTIFACT_SUFFICIENT:
        return (_VERIFIED, [f"{R}.INTERNAL_AUTH_MET", f"{R}.OBLIGATION_RELATIVE"], True) \
            if available["internal_authoritative"] else (_INSUFFICIENT, [f"{R}.INTERNAL_AUTH_ABSENT"], False)

    # --- standards requiring evidence the natural artifact does not intrinsically carry ---
    if t == s.EXTERNAL_AUTHORITATIVE_EVIDENCE_REQUIRED:
        return (_VERIFIED, [f"{R}.EXTERNAL_MET"], False) if available["external"] \
            else (_INSUFFICIENT, [f"{R}.EXTERNAL_ABSENT"], False)
    if t == s.INDEPENDENT_CORROBORATION_REQUIRED:
        return (_VERIFIED, [f"{R}.CORROB_MET"], False) if available["external"] \
            else (_INSUFFICIENT, [f"{R}.CORROB_ABSENT"], False)
    if t == s.TELEMETRY_OR_MEASUREMENT_REQUIRED:
        return (_VERIFIED, [f"{R}.TELEMETRY_MET"], False) if available["telemetry"] \
            else (_INSUFFICIENT, [f"{R}.TELEMETRY_ABSENT"], False)
    if t == s.POLICY_AND_AUTHORITY_EVIDENCE_REQUIRED:
        return (_VERIFIED, [f"{R}.POLICY_MET"], False) if (available["policy"] and available["approval"]) \
            else (_INSUFFICIENT, [f"{R}.POLICY_ABSENT"], False)
    if t == s.ATTRIBUTION_VERIFICATION_REQUIRED:
        return (_VERIFIED, [f"{R}.ATTRIBUTION_VERIFIED"], False) if available["attribution_verified"] \
            else (_VWL, [f"{R}.ATTRIBUTION_UNVERIFIED"], False)
    if t == s.TEMPORAL_VERIFICATION_REQUIRED:
        return (_VERIFIED, [f"{R}.TEMPORAL_CURRENT"], False) if available["temporal_current"] \
            else (_INSUFFICIENT, [f"{R}.TEMPORAL_UNVERIFIED"], False)
    if t == s.LOGICAL_OR_MATHEMATICAL_VERIFICATION_REQUIRED:
        return (_VERIFIED, [f"{R}.LOGIC_CHECKED"], False) if available["logical_checked"] \
            else (_VWL, [f"{R}.LOGIC_UNCHECKED"], False)

    # --- non-evidentiary dispositions ---
    if t == s.QUALIFY_BY_DEFAULT:
        return _VWL, [f"{R}.QUALIFY_DEFAULT"], False
    if t == s.HUMAN_REVIEW_REQUIRED:
        return _ESCALATE, [f"{R}.HUMAN_REVIEW"], False
    return _INDETERMINATE, [f"{R}.INDETERMINATE_OBLIGATION"], False   # fail-closed


def to_evidence_steer(o: s.EvidenceObligation,
                      available: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    """Build the evidence_steer the frozen EvidenceAssurance consumes. adequacy/grounding are
    OBLIGATION-RELATIVE (met vs unmet for the applicable standard), never a truth score."""
    av = available if available is not None else available_evidence_for(o)
    state, codes, obligation_relative = obligation_to_evidence_state(o, av)
    met = state in (_VERIFIED,)
    return {
        "evidence_state": state,
        "grounding": 0.9 if met else (0.6 if state == _VWL else 0.3),
        "entailment": "supports" if met else "neutral",
        "adequacy": 0.9 if met else (0.6 if state == _VWL else 0.3),
        "authority": "authorized" if o.authority_requirement is False or met else "unverified",
        "conflict": "none",
        "provenance_present": True,
        "age_days": 30.0,
        "obligation_type": o.evidence_obligation_type,
        "obligation_relative_verified": obligation_relative,
        "contract_reason_codes": codes,
        "contract_version": CONTRACT_VERSION,
    }
