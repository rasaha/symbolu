"""Ugence UVI Policy & Assessment-Context Contracts.

A narrow **internal technical package** (not a customer-facing module) holding
the immutable contract *shapes* for UVI governed assessment context and policy
artifacts:

* the five first-class policy families — ``GeographyPolicy``, ``DomainPolicy``,
  ``IntendedOutcomePolicy``, ``ValuationPolicy``, ``ReadinessPolicy``;
* the identity/envelope (``PolicyArtifactMetadata``) and immutable digest-bound
  ``PolicyReference``;
* governed thresholds (``GovernedThreshold`` — an immutable literal **or** a
  benchmark reference) and declared gates (``PolicyGate``);
* the governed ``AssessmentContext`` binding seam (mandatory Geography/Domain/
  Intended-Outcome references, cross-tenant rejection, fail-closed binder).

It depends only on the Python standard library and the neutral
``ugence-governance-contracts`` leaf (reusing its ``BenchmarkReference``,
``AssessmentWindow``, and evidence axes). It mints **no** authority and
implements **no** Policy Authority, benchmark registry, readiness evaluator,
forecasting, attribution/verification engine, or financial calculator. These are
contract shapes with structural invariants — selecting a value never creates
authority. See ADR
``docs/architecture/ADR_UGENCE_VALUE_INTELLIGENCE_GV2C_GV2E_GV3R.md`` (D-2,
D-13, D-15, §15, §20, milestone M-2C.1).

Import the curated surface from :mod:`ugence_uvi_policy_contracts.api`.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .contracts import (  # noqa: E402
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

from . import api  # noqa: E402,F401

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
    "api",
]
