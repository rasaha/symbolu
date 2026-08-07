"""Hiring decision plane — evidence → assessment → gates → eligibility → recommendation.

The governance-first decision layer of the Hiring Decision Authority. It turns
admitted evidence and dimension assessments into a non-compensatory eligibility
determination and an **advisory** recommendation, links them in the
:class:`HiringDecisionCase` aggregate, and reaches shared platform capabilities
(TAP, Decision Authority, ActionGate, Runtime Assurance/ACP, Reconciliation)
through explicit ports — never by copying their logic.

Invariants (see ``docs/HIRING_DECISION_AUTHORITY_DESIGN_SPEC.md``):

- Compatibility ≠ Eligibility  (eligibility derives from gates only)
- Overall Fit ≠ Policy         (analytics is a separate, non-imported path)
- AI Recommendation ≠ Binding  (binding only via DecisionAuthorityPort, HUMAN)
- Missing/unadmitted evidence cannot satisfy a mandatory gate (fail-closed)

The Overall Fit Index lives in :mod:`.analytics` and is deliberately **not**
re-exported here, so importing this plane never loads the analytics path.
"""

from __future__ import annotations

from .action_request import CompensationBounds, HiringActionRequest
from .assessment import AssessmentProvenance, DimensionAssessment
from .decision_case import BindingDecision, HiringDecisionCase
from .eligibility import Eligibility, derive_eligibility
from .enums import (
    ActionAuthorizationVerdict,
    AssessmentOutcome,
    AssuranceResult,
    CalibrationTarget,
    CaseStatus,
    DecisionDisposition,
    EligibilityStatus,
    EmploymentType,
    GateState,
    OutcomeEvidenceType,
    RecommendationDisposition,
    ReviewCheckpoint,
    Trajectory,
)
from .evidence import AdmittedEvidence
from .gates import GateResult, MandatoryGateEvaluator
from .ports import (
    ActionAuthorizationOutcome,
    ActionAuthorizationPort,
    AdmissionOutcome,
    AssuranceCheckResult,
    AssuranceOutcome,
    DecisionAuthorityOutcome,
    DecisionAuthorityPort,
    EvidenceAdmissionPort,
    EvidenceSubmission,
    ReconciliationOutcome,
    ReconciliationPort,
    RuntimeAssurancePort,
)
from .recommendation import (
    Confidence,
    Explanation,
    HiringRecommendation,
    ProposedAction,
    ReasonNode,
    build_recommendation,
    compute_confidence,
)
from .refs import ContractRef, contract_ref_of
from .reviews import CalibrationProposal, ReviewObservation, ReviewRecord

__all__ = [
    # evidence + assessment
    "AdmittedEvidence",
    "DimensionAssessment",
    "AssessmentProvenance",
    "AssessmentOutcome",
    # gates + eligibility
    "MandatoryGateEvaluator",
    "GateResult",
    "GateState",
    "Eligibility",
    "EligibilityStatus",
    "derive_eligibility",
    # recommendation
    "HiringRecommendation",
    "build_recommendation",
    "ProposedAction",
    "Confidence",
    "Explanation",
    "ReasonNode",
    "compute_confidence",
    "RecommendationDisposition",
    # aggregate + decision
    "HiringDecisionCase",
    "BindingDecision",
    "CaseStatus",
    "DecisionDisposition",
    # action
    "HiringActionRequest",
    "CompensationBounds",
    "EmploymentType",
    # reviews / calibration
    "ReviewRecord",
    "ReviewObservation",
    "CalibrationProposal",
    "ReviewCheckpoint",
    "OutcomeEvidenceType",
    "Trajectory",
    "CalibrationTarget",
    # refs
    "ContractRef",
    "contract_ref_of",
    # ports + DTOs
    "EvidenceAdmissionPort",
    "EvidenceSubmission",
    "AdmissionOutcome",
    "DecisionAuthorityPort",
    "DecisionAuthorityOutcome",
    "ActionAuthorizationPort",
    "ActionAuthorizationOutcome",
    "ActionAuthorizationVerdict",
    "RuntimeAssurancePort",
    "AssuranceOutcome",
    "AssuranceCheckResult",
    "AssuranceResult",
    "ReconciliationPort",
    "ReconciliationOutcome",
]
