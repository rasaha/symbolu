"""Canonical public API for the Ugence UVI Policy & Assessment-Context Contracts.

The deliberately small, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_uvi_policy_contracts`). Every symbol
below is a stable contract shape; ``public_api.json`` snapshots this surface and
``tests/packaging/test_public_api.py`` asserts they agree.
"""

from __future__ import annotations

from . import __version__
from .contracts import (
    AssessmentContext,
    AssessmentPurpose,
    ComparisonOperator,
    ComponentEvidenceRequirement,
    DomainPolicy,
    GateCategory,
    GeographyPolicy,
    GovernedThreshold,
    HeadlineClassificationPolicy,
    IntendedOutcomePolicy,
    MissingComponentBehavior,
    PolicyArtifactMetadata,
    PolicyContractError,
    PolicyFamily,
    PolicyGate,
    PolicyLifecycleState,
    PolicyReference,
    PolicyScope,
    ReadinessPolicy,
    ReadinessTarget,
    RequirementClass,
    ValuationPolicy,
    ValueComponent,
)

__all__ = [
    "__version__",
    "PolicyContractError",
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
    "PolicyReference",
    "PolicyArtifactMetadata",
    "GovernedThreshold",
    "PolicyGate",
    "GeographyPolicy",
    "DomainPolicy",
    "IntendedOutcomePolicy",
    "ValuationPolicy",
    "ReadinessPolicy",
    "ComponentEvidenceRequirement",
    "AssessmentContext",
]
