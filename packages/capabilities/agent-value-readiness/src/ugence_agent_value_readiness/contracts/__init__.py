"""Agent Value Readiness contract shapes (GV-3R-a).

Immutable, frozen dataclasses + enums with structural invariants only. No
readiness evaluator, tier selector, deployment authority, or financial value.
"""

from __future__ import annotations

from .binding import AssessedSystemBinding
from .catalogs import (
    AdoptionReadinessCatalog,
    AdoptionReadinessIndicatorDefinition,
    CapabilityReadinessCatalog,
    CapabilityReadinessIndicatorDefinition,
    IntelligenceFitnessCatalog,
    IntelligenceFitnessIndicatorDefinition,
    ReadinessIndicatorCatalogSet,
)
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
    SystemBindingAuthenticityStatus,
)
from .errors import ReadinessContractError
from .gates import GateResult
from .indicators import (
    AdoptionReadinessResult,
    CapabilityReadinessResult,
    IntelligenceFitnessResult,
)

__all__ = [
    "ReadinessContractError",
    # enums
    "ReadinessClassification",
    "GateStatus",
    "ConditionStatus",
    "ReadinessIndicatorClass",
    "CapabilityDemonstration",
    "IntelligenceDimension",
    "CapabilityDimension",
    "AdoptionDimension",
    "SystemBindingAuthenticityStatus",
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
    # ---- M-3R.3: indicator catalogs + assessed-system binding ---------- #
    "AssessedSystemBinding",
    "IntelligenceFitnessIndicatorDefinition",
    "CapabilityReadinessIndicatorDefinition",
    "AdoptionReadinessIndicatorDefinition",
    "IntelligenceFitnessCatalog",
    "CapabilityReadinessCatalog",
    "AdoptionReadinessCatalog",
    "ReadinessIndicatorCatalogSet",
]
