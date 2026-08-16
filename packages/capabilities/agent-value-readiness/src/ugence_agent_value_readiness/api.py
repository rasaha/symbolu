"""Canonical public API for the Ugence Agent Value Readiness Contracts.

The deliberately small, supported public surface. The readiness result/enum
vocabulary is defined in this package; the target and requirement-class enums are
**reused** (not redefined) from ``ugence_uvi_policy_contracts`` and re-exported
here for caller convenience — they remain canonically owned by that package.
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
    EvaluationTrace,
    GateResult,
    GateStatus,
    IntelligenceDimension,
    IntelligenceFitnessResult,
    ReadinessClassification,
    ReadinessContractError,
    ReadinessEvaluationCase,
    ReadinessEvaluationError,
    ReadinessEvaluationResult,
    ReadinessIndicatorClass,
    ReadinessReasonCode,
    ReadinessRule,
)
from .services import EVALUATOR_VERSION, evaluate_readiness

__all__ = [
    "__version__",
    "ReadinessContractError",
    "ReadinessEvaluationError",
    # readiness enums (defined here)
    "ReadinessClassification",
    "GateStatus",
    "ConditionStatus",
    "ReadinessIndicatorClass",
    "CapabilityDemonstration",
    "IntelligenceDimension",
    "CapabilityDimension",
    "AdoptionDimension",
    "ReadinessRule",
    "ReadinessReasonCode",
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
    # GV-3R-b evaluator (case / trace / result / entry point)
    "ReadinessEvaluationCase",
    "EvaluationTrace",
    "ReadinessEvaluationResult",
    "evaluate_readiness",
    "EVALUATOR_VERSION",
]
