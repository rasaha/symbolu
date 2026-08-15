"""Ugence Agent Value Readiness Contracts (GV-3R-a).

A narrow **internal technical leaf** (not a customer-facing module) holding the
**non-financial** contract *shapes* for the Agent Value Readiness engine of
Ugence Value Intelligence — the vocabulary for assessing whether an agent is
ready for an intended outcome under a Geography / Domain / Intended-Outcome +
Readiness policy context:

    PreROIReadiness = f(Intelligence, Capabilities, Adoption
                        | Geography, Domain, IntendedOutcome)

Intelligence, Capability, and Adoption are **leading indicators**, never money,
benefit, realized value, or ROI. This package implements **contracts only**: no
readiness evaluator, no precedence/tier selector, no deployment authority, no
Policy Authority, no evidence admission, no forecasting, no financial valuation,
and no ``governed-value`` integration. A determination it carries is an
**advisory** readiness result consumed by a separate human/deployment-governance
process — never an authorization to deploy. See ADR
``docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`` (§5–§10,
§20, milestone M-3R.1). Evaluation is GV-3R-b (M-3R.2).

Import the curated surface from :mod:`ugence_agent_value_readiness.api`.
"""

from __future__ import annotations

__version__ = "0.1.0"

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
    "api",
]
