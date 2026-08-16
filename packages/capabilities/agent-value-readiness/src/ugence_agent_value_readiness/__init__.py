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

The package holds the contract shapes (GV-3R-a, M-3R.1) **and** the deterministic
readiness-determination evaluator (GV-3R-b, M-3R.2) — see ADR
``docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`` (§5–§10,
§20). The evaluator selects one advisory classification from a complete
applicable gate set at an explicit, caller-supplied ``evaluation_time``; it never
reads the system clock.

It remains **advisory, non-financial and fail-closed**. It is not a deployment
authorization, not a Policy Authority, and it performs no evidence admission or
verification, no benchmark resolution, no metric-to-threshold comparison, no
causal attribution, no forecasting, no financial valuation, and no
``governed-value`` integration. Gate statuses, policies and condition approvals
remain **structurally supplied, authority-unverified** caller artifacts.

Import the curated surface from :mod:`ugence_agent_value_readiness.api`.
"""

from __future__ import annotations

__version__ = "0.2.0"

from .contracts import (  # noqa: E402
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
    "IntelligenceFitnessResult",
    "CapabilityReadinessResult",
    "AdoptionReadinessResult",
    "GateResult",
    "ConditionSet",
    "AdvisoryComposite",
    "AgentValueReadinessDetermination",
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
    "api",
]
