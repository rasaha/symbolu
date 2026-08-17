"""Canonical public API for Ugence Agent Value Readiness.

The deliberately small, supported public surface: the **contract shapes**
(GV-3R-a), the single canonical **determination evaluator** (GV-3R-b), and the
single canonical **trusted orchestration boundary** around it. The
readiness result/enum vocabulary is defined in this package; the target and
requirement-class enums are **reused** (not redefined) from
``ugence_uvi_policy_contracts`` and re-exported here for caller convenience —
they remain canonically owned by that package.

:func:`evaluate_readiness` is the **only** classification path. Nothing else in
this package selects a readiness tier, so there is no second calculation route
that could diverge from the ratified precedence — :func:`assess_readiness` adds
a fail-closed trust boundary *around* it and calls it exactly once.

Note what is **not** exported, in either service: no allow-all policy resolver,
no allow-all or "testing" gate/condition verifier, no way to hand either service
a readiness classification, and no deployment authorization. Those absences are
the boundary, not gaps to be filled in later.
"""

from __future__ import annotations

# Reused policy vocabulary (canonically owned by ugence-uvi-policy-contracts).
from ugence_uvi_policy_contracts.api import ReadinessTarget, RequirementClass

from . import __version__
from .contracts import (
    AdoptionDimension,
    AdoptionReadinessResult,
    AdvisoryComposite,
    AgentValueReadinessDetermination,
    CapabilityDemonstration,
    CapabilityDimension,
    CapabilityReadinessResult,
    ConditionSet,
    ConditionStatus,
    GateResult,
    GateStatus,
    IntelligenceDimension,
    IntelligenceFitnessResult,
    ReadinessClassification,
    ReadinessContractError,
    ReadinessIndicatorClass,
)
from .evaluation import (
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
from .orchestration import (
    READINESS_ORCHESTRATOR_VERSION,
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
    PolicyAuthorityReadinessPolicyResolver,
    ReadinessAssessmentDisposition,
    ReadinessAssessmentError,
    ReadinessAssessmentOutcome,
    ReadinessAssessmentRequest,
    ReadinessAssessmentStatus,
    ReadinessAssessmentTrace,
    ReadinessInputVerificationStatus,
    ReadinessPolicyResolver,
    ReadinessTrustAdvisoryState,
    ReadinessTrustGapCode,
    assess_readiness,
)

__all__ = [
    "__version__",
    "ReadinessContractError",
    # readiness enums (defined here)
    "ReadinessClassification",
    "GateStatus",
    "ConditionStatus",
    "ReadinessIndicatorClass",
    "CapabilityDemonstration",
    "IntelligenceDimension",
    "CapabilityDimension",
    "AdoptionDimension",
    # reused policy enums (owned by uvi-policy-contracts, re-exported)
    "ReadinessTarget",
    "RequirementClass",
    # indicator results
    "IntelligenceFitnessResult",
    "CapabilityReadinessResult",
    "AdoptionReadinessResult",
    # gate / condition / composite
    "GateResult",
    "ConditionSet",
    "AdvisoryComposite",
    # determination envelope
    "AgentValueReadinessDetermination",
    # ---- GV-3R-b: the deterministic determination evaluator ---------------- #
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
    # ---- Trusted Readiness Orchestration (additive integration) ---------- #
    "READINESS_ORCHESTRATOR_VERSION",
    "ReadinessAssessmentError",
    "ReadinessAssessmentStatus",
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
]
