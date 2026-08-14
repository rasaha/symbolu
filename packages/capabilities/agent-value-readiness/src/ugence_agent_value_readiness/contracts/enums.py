"""Enumerations for the Agent Value Readiness contracts.

Every enum is a ``str``-valued ``Enum`` with UPPERCASE values. None encodes a
numeric maturity score or a financial quantity — readiness is non-financial and
target-relative, expressed through explicit classifications, never a scalar.

``ReadinessTarget``, ``RequirementClass``, ``GateCategory`` are **reused** from
``ugence_uvi_policy_contracts`` (they are canonically owned there since GV-2C-a)
and are re-exported from this package's API for convenience — not redefined here.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "ReadinessClassification",
    "GateStatus",
    "ConditionStatus",
    "ReadinessIndicatorClass",
    "CapabilityDemonstration",
    "IntelligenceDimension",
    "CapabilityDimension",
    "AdoptionDimension",
]


class ReadinessClassification(str, Enum):
    """The mandatory non-financial readiness classification (ADR §6).

    Target-relative: ``PILOT_READY`` applies only to a PILOT target;
    ``READY_WITH_CONDITIONS`` and ``DEPLOYMENT_READY`` apply only to PRODUCTION;
    ``NOT_READY`` / ``NOT_ASSESSABLE`` may apply to either. This is an **advisory
    readiness determination** consumed by a separate human/deployment-governance
    process — it is **never** an authorization to deploy.
    """

    NOT_ASSESSABLE = "NOT_ASSESSABLE"
    NOT_READY = "NOT_READY"
    PILOT_READY = "PILOT_READY"
    READY_WITH_CONDITIONS = "READY_WITH_CONDITIONS"
    DEPLOYMENT_READY = "DEPLOYMENT_READY"


class GateStatus(str, Enum):
    """The recorded status of a gate evaluation (ADR §7).

    A *recorded* outcome supplied by an upstream evaluator — these contracts do
    not compute it. ``FAIL`` dominates an unrelated ``INDETERMINATE`` in the
    ratified precedence, but that precedence calculus belongs to GV-3R-b.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"


class ConditionStatus(str, Enum):
    """Lifecycle status of a compensating control / condition (ADR §9, D-7).

    A caller-asserted label — it is **not** proof that a real authority approved,
    or that time has expired/revoked it. GV-3R-b resolves and validates authority
    and time; a constructor only checks structural completeness for the label.
    """

    PROPOSED = "PROPOSED"
    APPROVED_ACTIVE = "APPROVED_ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SATISFIED = "SATISFIED"


class ReadinessIndicatorClass(str, Enum):
    """Which leading-indicator family a readiness result belongs to (ADR §10).

    Intelligence, Capability, and Adoption are **distinct** non-financial
    families — never merged into one score.
    """

    INTELLIGENCE = "INTELLIGENCE"
    CAPABILITY = "CAPABILITY"
    ADOPTION = "ADOPTION"


class CapabilityDemonstration(str, Enum):
    """How far a capability has been demonstrated (ADR §9).

    Distinguishes *exists* from *tested* from *met the policy threshold* — so a
    capability that is present but untested is never conflated with one that met
    its bar. Orthogonal to whether the evidence was sufficient and to whether the
    capability is mandatory for the requested target.
    """

    NOT_PRESENT = "NOT_PRESENT"
    PRESENT_UNTESTED = "PRESENT_UNTESTED"
    TESTED = "TESTED"
    MET_THRESHOLD = "MET_THRESHOLD"


class IntelligenceDimension(str, Enum):
    """Task/outcome-specific Intelligence-fitness dimensions (ADR §10)."""

    REASONING_QUALITY = "REASONING_QUALITY"
    DECISION_QUALITY = "DECISION_QUALITY"
    ACCURACY = "ACCURACY"
    RELIABILITY = "RELIABILITY"
    CONSISTENCY = "CONSISTENCY"
    CONFIDENCE_CALIBRATION = "CONFIDENCE_CALIBRATION"
    EXCEPTION_HANDLING = "EXCEPTION_HANDLING"
    UNCERTAINTY_RECOGNITION = "UNCERTAINTY_RECOGNITION"
    POPULATION_PERFORMANCE = "POPULATION_PERFORMANCE"
    LANGUAGE_PERFORMANCE = "LANGUAGE_PERFORMANCE"
    REGIONAL_PERFORMANCE = "REGIONAL_PERFORMANCE"


class CapabilityDimension(str, Enum):
    """Capability-readiness dimensions (ADR §10)."""

    FUNCTIONAL_COVERAGE = "FUNCTIONAL_COVERAGE"
    TOOL_READINESS = "TOOL_READINESS"
    INTEGRATION_READINESS = "INTEGRATION_READINESS"
    WORKFLOW_COMPLETION = "WORKFLOW_COMPLETION"
    EXECUTION_RELIABILITY = "EXECUTION_RELIABILITY"
    AUTONOMY_BOUNDARIES = "AUTONOMY_BOUNDARIES"
    SECURITY_READINESS = "SECURITY_READINESS"
    GOVERNANCE_READINESS = "GOVERNANCE_READINESS"
    OBSERVABILITY = "OBSERVABILITY"
    AUDITABILITY = "AUDITABILITY"
    ESCALATION_READINESS = "ESCALATION_READINESS"
    HUMAN_FALLBACK_READINESS = "HUMAN_FALLBACK_READINESS"


class AdoptionDimension(str, Enum):
    """Pre-deployment Adoption-readiness dimensions (ADR §10).

    These are **predicted, pre-deployment** indicators — distinct from
    post-deployment ``ObservedAdoption`` (a later GV-3+ evidence class not
    defined here). They are never money or realized value.
    """

    ELIGIBLE_POPULATION_COVERAGE = "ELIGIBLE_POPULATION_COVERAGE"
    ELIGIBLE_WORKFLOW_COVERAGE = "ELIGIBLE_WORKFLOW_COVERAGE"
    EXPECTED_UTILIZATION = "EXPECTED_UTILIZATION"
    WORKFLOW_SUITABILITY = "WORKFLOW_SUITABILITY"
    USER_ACCEPTANCE_READINESS = "USER_ACCEPTANCE_READINESS"
    TRUST_READINESS = "TRUST_READINESS"
    TRAINING_READINESS = "TRAINING_READINESS"
    CHANGE_MANAGEMENT_READINESS = "CHANGE_MANAGEMENT_READINESS"
    EXPECTED_OVERRIDE_RATE = "EXPECTED_OVERRIDE_RATE"
    EXPECTED_REJECTION_RATE = "EXPECTED_REJECTION_RATE"
    EXPECTED_ABANDONMENT_RATE = "EXPECTED_ABANDONMENT_RATE"
    SUSTAINED_USAGE_CONDITIONS = "SUSTAINED_USAGE_CONDITIONS"
