"""Hiring decision plane — canonical import surface.

Re-exports the decision layer (evidence → assessment → gates → eligibility →
advisory recommendation → case aggregate, plus integration ports) so consumers
can depend on ``ugence_ai_hiring.hiring.decision`` alongside the other canonical
hiring-domain surfaces. Implementation lives under
``ugence_ai_hiring.hiring_decision``; object identity is preserved.

The Overall Fit Index (``hiring_decision.analytics``) is intentionally **not**
re-exported here — it is analytics-only and must never be reachable from
gate/eligibility/policy code.

See ``docs/HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md`` §§4–11.
"""

from __future__ import annotations

from ugence_ai_hiring.hiring_decision import (  # noqa: F401
    ActionAuthorizationOutcome,
    ActionAuthorizationPort,
    AdmissionOutcome,
    AdmittedEvidence,
    AssessmentOutcome,
    AssessmentProvenance,
    AssuranceOutcome,
    BindingDecision,
    CalibrationProposal,
    CaseStatus,
    CompensationBounds,
    Confidence,
    ContractRef,
    DecisionAuthorityOutcome,
    DecisionAuthorityPort,
    DecisionDisposition,
    DimensionAssessment,
    Eligibility,
    EligibilityStatus,
    EmploymentType,
    EvidenceAdmissionPort,
    EvidenceSubmission,
    Explanation,
    GateResult,
    GateState,
    HiringActionRequest,
    HiringDecisionCase,
    HiringRecommendation,
    MandatoryGateEvaluator,
    ProposedAction,
    ReconciliationOutcome,
    ReconciliationPort,
    RecommendationDisposition,
    ReviewObservation,
    ReviewRecord,
    RuntimeAssurancePort,
    build_recommendation,
    compute_confidence,
    contract_ref_of,
    derive_eligibility,
)

__all__ = [
    "AdmittedEvidence",
    "DimensionAssessment",
    "AssessmentProvenance",
    "AssessmentOutcome",
    "MandatoryGateEvaluator",
    "GateResult",
    "GateState",
    "Eligibility",
    "EligibilityStatus",
    "derive_eligibility",
    "HiringRecommendation",
    "build_recommendation",
    "ProposedAction",
    "Confidence",
    "Explanation",
    "compute_confidence",
    "RecommendationDisposition",
    "HiringDecisionCase",
    "BindingDecision",
    "CaseStatus",
    "DecisionDisposition",
    "HiringActionRequest",
    "CompensationBounds",
    "EmploymentType",
    "ReviewRecord",
    "ReviewObservation",
    "CalibrationProposal",
    "ContractRef",
    "contract_ref_of",
    "EvidenceAdmissionPort",
    "EvidenceSubmission",
    "AdmissionOutcome",
    "DecisionAuthorityPort",
    "DecisionAuthorityOutcome",
    "ActionAuthorizationPort",
    "ActionAuthorizationOutcome",
    "RuntimeAssurancePort",
    "AssuranceOutcome",
    "ReconciliationPort",
    "ReconciliationOutcome",
]
