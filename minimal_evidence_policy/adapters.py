"""Phase 9 - Minimal obligation -> frozen EvidenceAssurance contract.

Maps an E-level obligation + available evidence into the evidence_steer the FROZEN EvidenceAssurance
consumes. Preserves the rule: meeting an obligation does NOT imply universal truth. A met low-burden
obligation (E0/E1, or E2 with the artifact's own evidence) maps to an OBLIGATION-RELATIVE VERIFIED;
E3/E4 without independent evidence stay INSUFFICIENT/ESCALATE (never VERIFIED). ER -> ESCALATE.

Represents separately: obligation level, obligation satisfaction, factual truth status, evidence state.
Read-only over frozen EA. Deterministic. No frozen threshold modified.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from minimal_evidence_policy import schema as s

CONTRACT_VERSION = "minimal_obligation_ea_contract_v1"

_VERIFIED, _VWL, _INSUFFICIENT, _ESCALATE = "VERIFIED", "VERIFIED_WITH_LIMITATIONS", "INSUFFICIENT", "ESCALATE"


def available_evidence_for(item: Dict[str, Any], override: Optional[Dict[str, bool]] = None) -> Dict[str, bool]:
    role = item.get("source_role", "unknown_source")
    av = {
        "implementation": role in ("primary_implementation", "test_artifact"),
        "internal_authoritative": role == "approved_policy",
        "context": True,
        "external": False, "telemetry": False, "policy": False, "approval": False,
    }
    if override:
        av.update(override)
    return av


def obligation_to_evidence_state(level: str, av: Dict[str, bool]):
    """Return (evidence_state, reason_codes, obligation_relative)."""
    R = "MEOC"
    if level == s.E0:
        return _VERIFIED, [f"{R}.E0_NO_FACTUAL_GATE", f"{R}.OBLIGATION_RELATIVE"], True
    if level == s.E1:
        return (_VERIFIED, [f"{R}.E1_CONTEXT_MET", f"{R}.OBLIGATION_RELATIVE"], True) if av["context"] \
            else (_VWL, [f"{R}.E1_PARTIAL"], False)
    if level == s.E2:
        if av["implementation"] or av["internal_authoritative"]:
            return _VERIFIED, [f"{R}.E2_MET", f"{R}.OBLIGATION_RELATIVE"], True
        return _INSUFFICIENT, [f"{R}.E2_ARTIFACT_EVIDENCE_ABSENT"], False
    if level == s.E3:
        if av["external"] or av["telemetry"]:
            return _VERIFIED, [f"{R}.E3_MET"], False
        return _INSUFFICIENT, [f"{R}.E3_INDEPENDENT_EVIDENCE_ABSENT"], False
    if level == s.E4:
        # E4 mandates human review regardless -> escalate (never a clean allow from the policy alone)
        return _ESCALATE, [f"{R}.E4_MANDATORY_REVIEW"], False
    # ER
    return _ESCALATE, [f"{R}.ER_HUMAN_REVIEW"], False


def to_evidence_steer(decision: s.Decision, item: Dict[str, Any],
                      available: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    av = available if available is not None else available_evidence_for(item)
    state, codes, obligation_relative = obligation_to_evidence_state(decision.final_obligation, av)
    met = state == _VERIFIED
    return {
        "evidence_state": state,
        "grounding": 0.9 if met else (0.6 if state == _VWL else 0.3),
        "entailment": "supports" if met else "neutral",
        "adequacy": 0.9 if met else (0.6 if state == _VWL else 0.3),
        "authority": "authorized",
        "conflict": "none",
        "provenance_present": True,
        "age_days": 30.0,
        # separated representations (obligation != truth)
        "obligation_level": decision.final_obligation,
        "obligation_relative_verified": obligation_relative,
        "factual_truth_status": "not_independently_established",
        "contract_reason_codes": codes,
        "contract_version": CONTRACT_VERSION,
    }
