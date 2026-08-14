"""UVI policy & assessment-context contract shapes.

Immutable, frozen dataclasses + enums with structural invariants only. No
authority, evaluator, registry, or calculator lives here.
"""

from __future__ import annotations

from .context import AssessmentContext
from .enums import (
    AssessmentPurpose,
    ComparisonOperator,
    GateCategory,
    HeadlineClassificationPolicy,
    MissingComponentBehavior,
    PolicyFamily,
    PolicyLifecycleState,
    PolicyScope,
    ReadinessTarget,
    RequirementClass,
    ValueComponent,
)
from .errors import PolicyContractError
from .metadata import PolicyArtifactMetadata, PolicyReference
from .policies import (
    ComponentEvidenceRequirement,
    DomainPolicy,
    GeographyPolicy,
    IntendedOutcomePolicy,
    ReadinessPolicy,
    ValuationPolicy,
)
from .thresholds import GovernedThreshold, PolicyGate

__all__ = [
    # errors
    "PolicyContractError",
    # enums
    "PolicyFamily",
    "PolicyScope",
    "PolicyLifecycleState",
    "RequirementClass",
    "ComparisonOperator",
    "GateCategory",
    "ReadinessTarget",
    "ValueComponent",
    "HeadlineClassificationPolicy",
    "MissingComponentBehavior",
    "AssessmentPurpose",
    # identity / references
    "PolicyReference",
    "PolicyArtifactMetadata",
    # thresholds / gates
    "GovernedThreshold",
    "PolicyGate",
    # policies
    "GeographyPolicy",
    "DomainPolicy",
    "IntendedOutcomePolicy",
    "ValuationPolicy",
    "ReadinessPolicy",
    "ComponentEvidenceRequirement",
    # assessment context
    "AssessmentContext",
]
