"""Enumerations for the UVI policy & assessment-context contracts.

Every enum is a ``str``-valued ``Enum`` with UPPERCASE values, so canonical
serialization is stable and human-readable. None of these enums encodes a
numeric maturity score or a caller-tunable multiplier — policy strength is
expressed through explicit, authority-governed classifications, never a scalar
knob a caller can turn (ADR §23 anti-gaming invariants).
"""

from __future__ import annotations

from enum import Enum

__all__ = [
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
]


class PolicyFamily(str, Enum):
    """The five first-class UVI policy families (ADR §15, D-2, D-13)."""

    GEOGRAPHY = "GEOGRAPHY"
    DOMAIN = "DOMAIN"
    INTENDED_OUTCOME = "INTENDED_OUTCOME"
    VALUATION = "VALUATION"
    READINESS = "READINESS"


class PolicyScope(str, Enum):
    """Organizational reach a policy artifact was issued for.

    ``GLOBAL`` artifacts carry no ``tenant_id``; ``TENANT`` artifacts are bound
    to exactly one tenant and may only be bound into that tenant's assessment
    context (cross-tenant binding is rejected).
    """

    GLOBAL = "GLOBAL"
    TENANT = "TENANT"


class PolicyLifecycleState(str, Enum):
    """The lifecycle state an artifact *asserts* about itself.

    Carried for audit and for the fail-closed binder — the contract never
    *verifies* this state (that is Policy-Authority work). Only
    ``APPROVED_ACTIVE`` artifacts may be strictly bound into an active
    assessment context; ``DRAFT``/``EXPIRED``/``REVOKED``/``SUPERSEDED``
    artifacts are constructible (for audit) but fail closed on binding.
    """

    DRAFT = "DRAFT"
    APPROVED_ACTIVE = "APPROVED_ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"


class RequirementClass(str, Enum):
    """How a gate/component participates in a determination (ADR D-5, D-6).

    ``MANDATORY`` gates are non-compensatory and non-waivable — a mandatory
    failure can never be converted into readiness by any control, waiver, ROI,
    composite, forecast, or preference. Only ``CONDITIONAL`` concerns may ever
    be governed through a compensating control. ``ADVISORY`` concerns never
    block.
    """

    MANDATORY = "MANDATORY"
    CONDITIONAL = "CONDITIONAL"
    ADVISORY = "ADVISORY"


class ComparisonOperator(str, Enum):
    """Direction of a threshold comparison (metric ⋈ threshold).

    A declared comparison direction only — this contract performs no evaluation.
    """

    GTE = "GTE"
    GT = "GT"
    LTE = "LTE"
    LT = "LT"
    EQ = "EQ"
    NEQ = "NEQ"


class GateCategory(str, Enum):
    """What concern a gate governs (ADR §15 mandatory gate classes)."""

    SAFETY = "SAFETY"
    FAIRNESS = "FAIRNESS"
    QUALITY = "QUALITY"
    COMPLIANCE = "COMPLIANCE"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    OTHER = "OTHER"


class ReadinessTarget(str, Enum):
    """Deployment target a readiness gate/policy applies to (ADR §5, §6)."""

    PILOT = "PILOT"
    PRODUCTION = "PRODUCTION"


class ValueComponent(str, Enum):
    """A financial-valuation input class (ADR §18 manifest components).

    Declared here only so a :class:`ValuationPolicy` can state *which* components
    it requires and to what evidential standard — the financial calculation and
    the evidence manifest themselves belong to ``governed-value`` (D-11, D-12),
    which this package does not depend on or implement.
    """

    GROSS_BENEFIT = "GROSS_BENEFIT"
    AVOIDED_LOSS = "AVOIDED_LOSS"
    ACTUAL_LOSS = "ACTUAL_LOSS"
    RESIDUAL_EXPECTED_LOSS = "RESIDUAL_EXPECTED_LOSS"
    OPERATING_COST = "OPERATING_COST"
    INVESTMENT = "INVESTMENT"
    NORMALIZATION_UNIT = "NORMALIZATION_UNIT"
    COUNTERFACTUAL_INPUT = "COUNTERFACTUAL_INPUT"
    ATTRIBUTION_INPUT = "ATTRIBUTION_INPUT"


class HeadlineClassificationPolicy(str, Enum):
    """The permitted headline-classification rule for a valuation (ADR §18/D-12).

    Only the conservative rule is admissible: the headline classification of a
    result is the **weakest classification among its policy-required
    components** — a verified component never elevates a weaker required one.
    Encoded as a single-value enum so a policy cannot declare a non-conservative
    (e.g. best-component or averaged) headline rule.
    """

    WEAKEST_REQUIRED_COMPONENT = "WEAKEST_REQUIRED_COMPONENT"


class MissingComponentBehavior(str, Enum):
    """How a valuation should treat a missing/degraded *required* component.

    A policy *declaration* only (no execution here). ``FAIL_CLOSED`` (the
    default) blocks a headline classification when a required component is
    absent or degraded; ``DEGRADE`` permits a lower, explicitly-degraded
    classification.
    """

    FAIL_CLOSED = "FAIL_CLOSED"
    DEGRADE = "DEGRADE"


class AssessmentPurpose(str, Enum):
    """What an :class:`AssessmentContext` is bound for.

    Mirrors the honest stage separation of the ``governed-value`` kernel's
    ``AssessmentStage`` (pre-ROI readiness vs forecast vs post-deployment
    value) without importing it — this package does not depend on
    ``governed-value``. It records *intent*; it grants no stage and mints no
    authority.
    """

    PRE_ROI_READINESS = "PRE_ROI_READINESS"
    FORECAST = "FORECAST"
    POST_DEPLOYMENT_VALUE = "POST_DEPLOYMENT_VALUE"
