"""Agent Value Readiness contract shapes (GV-3R-a).

Immutable, frozen dataclasses + enums with structural invariants only. No
readiness evaluator, tier selector, deployment authority, or financial value.
"""

from __future__ import annotations

from .composite import AdvisoryComposite
from .conditions import ConditionSet
from .determination import AgentValueReadinessDetermination
from .enums import (
    AdoptionDimension,
    CapabilityDemonstration,
    CapabilityDimension,
    ConditionStatus,
    GateStatus,
    IntelligenceDimension,
    ReadinessClassification,
    ReadinessIndicatorClass,
)
from .errors import ReadinessContractError
from .evaluation import (
    EvaluationTrace,
    ReadinessEvaluationCase,
    ReadinessEvaluationError,
    ReadinessEvaluationResult,
    ReadinessReasonCode,
    ReadinessRule,
)
from .gates import GateResult
from .indicators import (
    AdoptionReadinessResult,
    CapabilityReadinessResult,
    IntelligenceFitnessResult,
)

__all__ = [
    "ReadinessContractError",
    "ReadinessEvaluationError",
    "ReadinessRule",
    "ReadinessReasonCode",
    "ReadinessEvaluationCase",
    "EvaluationTrace",
    "ReadinessEvaluationResult",
    # enums
    "ReadinessClassification",
    "GateStatus",
    "ConditionStatus",
    "ReadinessIndicatorClass",
    "CapabilityDemonstration",
    "IntelligenceDimension",
    "CapabilityDimension",
    "AdoptionDimension",
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
]
