"""Ugence Agent Value Readiness Contracts (GV-3R-a).

A narrow **internal technical leaf** (not a customer-facing module) holding the
**non-financial** contract *shapes* for the Agent Value Readiness engine of
Ugence Value Intelligence — the vocabulary for assessing whether an agent is
ready for an intended outcome under a Geography / Domain / Intended-Outcome +
Readiness policy context:

    PreROIReadiness = f(Intelligence, Capabilities, Adoption
                        | Geography, Domain, IntendedOutcome)

Intelligence, Capability, and Adoption are **leading indicators**, never money,
benefit, realized value, or ROI.

The package holds the contract shapes (GV-3R-a, M-3R.1), the deterministic
readiness-determination evaluator (GV-3R-b, M-3R.2), and the trusted
trusted orchestration boundary around that evaluator — see ADR
``docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`` (§5–§10,
§19, §20, §23) and ``docs/architecture/ADR_UGENCE_POLICY_AUTHORITY.md`` (§5,
§10.4). The evaluator selects one advisory classification from a complete
applicable gate set at an explicit, caller-supplied ``evaluation_time``; it never
reads the system clock. The orchestrator resolves the exact ``ReadinessPolicy``
through the **shared Ugence Policy Authority's public** resolution service,
admits only independently verified gate results and conditions, and calls that
one evaluator exactly once — it adds no second classification algorithm.

It remains **advisory, non-financial and fail-closed**. It is not a deployment
authorization, not a Policy Authority, and it performs no evidence admission or
verification, no benchmark resolution, no metric-to-threshold comparison, no
causal attribution, no condition enforcement, no forecasting, no financial
valuation, and no ``governed-value`` integration. Used **standalone**, the
evaluator still treats gate statuses, policies and condition approvals as
structurally supplied, authority-unverified caller artifacts; used through
``assess_readiness``, each of those becomes the responsibility of a configured
trust boundary that denies by default.

Import the curated surface from :mod:`ugence_agent_value_readiness.api`.
"""

from __future__ import annotations

__version__ = "0.4.0"

from .contracts import (  # noqa: E402
    AdoptionDimension,
    AdoptionReadinessCatalog,
    AdoptionReadinessIndicatorDefinition,
    AdoptionReadinessResult,
    AdvisoryComposite,
    AssessedSystemBinding,
    AgentValueReadinessDetermination,
    CapabilityDemonstration,
    CapabilityDimension,
    CapabilityReadinessCatalog,
    CapabilityReadinessIndicatorDefinition,
    CapabilityReadinessResult,
    ConditionSet,
    ConditionStatus,
    GateResult,
    GateStatus,
    IntelligenceDimension,
    IntelligenceFitnessCatalog,
    IntelligenceFitnessIndicatorDefinition,
    IntelligenceFitnessResult,
    ReadinessClassification,
    ReadinessContractError,
    ReadinessIndicatorCatalogSet,
    ReadinessIndicatorClass,
    SystemBindingAuthenticityStatus,
)
from .evaluation import (  # noqa: E402
    ConditionDecision,
    ConditionDecisionCode,
    ReadinessAdvisoryCode,
    ReadinessEvaluationCase,
    ReadinessEvaluationError,
    ReadinessEvaluationResult,
    ReadinessEvaluationTrace,
    ReadinessReasonCode,
    ReadinessRuleId,
    evaluate_readiness,
)

from .orchestration import (  # noqa: E402
    READINESS_ORCHESTRATOR_VERSION,
    SYSTEM_BINDING_AUTHENTICITY_ADVISORY,
    ConditionSetVerification,
    ConditionSetVerifier,
    ConditionVerificationRequest,
    ConditionVerificationSummary,
    DenyAllConditionSetVerifier,
    DenyAllGateResultVerifier,
    DenyAllReadinessPolicyResolver,
    GateResultVerification,
    GateResultVerifier,
    GateVerificationRequest,
    GateVerificationSummary,
    IndicatorAdmissionSummary,
    PolicyAuthorityReadinessPolicyResolver,
    ReadinessAssessmentDisposition,
    ReadinessAssessmentError,
    ReadinessAssessmentOutcome,
    ReadinessAssessmentRequest,
    ReadinessAssessmentStatus,
    ReadinessAssessmentTrace,
    ReadinessIndicatorAdmissionStatus,
    ReadinessInputVerificationStatus,
    ReadinessPolicyResolver,
    ReadinessTrustAdvisoryState,
    ReadinessTrustGapCode,
    assess_readiness,
)

from . import api  # noqa: E402,F401

__all__ = [
    "__version__",
    "ReadinessContractError",
    "ReadinessClassification",
    "GateStatus",
    "ConditionStatus",
    "ReadinessIndicatorClass",
    "CapabilityDemonstration",
    "IntelligenceDimension",
    "CapabilityDimension",
    "AdoptionDimension",
    "SystemBindingAuthenticityStatus",
    "IntelligenceFitnessResult",
    "CapabilityReadinessResult",
    "AdoptionReadinessResult",
    "GateResult",
    "ConditionSet",
    "AdvisoryComposite",
    "AgentValueReadinessDetermination",
    # ---- M-3R.3: indicator catalogs + assessed-system binding ------------ #
    "AssessedSystemBinding",
    "IntelligenceFitnessIndicatorDefinition",
    "CapabilityReadinessIndicatorDefinition",
    "AdoptionReadinessIndicatorDefinition",
    "IntelligenceFitnessCatalog",
    "CapabilityReadinessCatalog",
    "AdoptionReadinessCatalog",
    "ReadinessIndicatorCatalogSet",
    # GV-3R-b evaluator
    "ReadinessEvaluationError",
    "ReadinessEvaluationCase",
    "ReadinessEvaluationTrace",
    "ReadinessEvaluationResult",
    "ConditionDecision",
    "ReadinessRuleId",
    "ReadinessReasonCode",
    "ReadinessAdvisoryCode",
    "ConditionDecisionCode",
    "evaluate_readiness",
    # Trusted Readiness Orchestration
    "READINESS_ORCHESTRATOR_VERSION",
    "SYSTEM_BINDING_AUTHENTICITY_ADVISORY",
    "ReadinessAssessmentError",
    "ReadinessAssessmentStatus",
    "ReadinessIndicatorAdmissionStatus",
    "ReadinessInputVerificationStatus",
    "ReadinessTrustAdvisoryState",
    "ReadinessTrustGapCode",
    "ReadinessAssessmentRequest",
    "GateVerificationRequest",
    "GateResultVerification",
    "ConditionVerificationRequest",
    "ConditionSetVerification",
    "GateVerificationSummary",
    "ConditionVerificationSummary",
    "IndicatorAdmissionSummary",
    "ReadinessAssessmentDisposition",
    "ReadinessAssessmentTrace",
    "ReadinessAssessmentOutcome",
    "ReadinessPolicyResolver",
    "GateResultVerifier",
    "ConditionSetVerifier",
    "DenyAllReadinessPolicyResolver",
    "DenyAllGateResultVerifier",
    "DenyAllConditionSetVerifier",
    "PolicyAuthorityReadinessPolicyResolver",
    "assess_readiness",
    "api",
]
