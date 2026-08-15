"""Canonical public API for Ugence Agent Value Readiness.

The deliberately small, supported public surface: the **contract shapes**
(GV-3R-a) and the single canonical **determination evaluator** (GV-3R-b). The
readiness result/enum vocabulary is defined in this package; the target and
requirement-class enums are **reused** (not redefined) from
``ugence_uvi_policy_contracts`` and re-exported here for caller convenience —
they remain canonically owned by that package.

:func:`evaluate_readiness` is the **only** classification path. Nothing else in
this package selects a readiness tier, so there is no second calculation route
that could diverge from the ratified precedence.
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
]
