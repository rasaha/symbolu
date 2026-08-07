"""Vocabulary for the hiring decision plane.

Reuses the policy-plane vocabulary (:mod:`ugence_ai_hiring.hiring_policy.enums`)
for gate types, evidence classes, and runtime-assurance checks; adds the
decision-lifecycle enums. Matches the normative schemas under ``docs/schemas/``.
"""

from __future__ import annotations

from enum import Enum


class GateState(str, Enum):
    """Deterministic mandatory-gate evaluation state.

    ``INDETERMINATE`` is fail-closed: missing or unadmitted deciding evidence
    yields INDETERMINATE, which blocks eligibility exactly as FAILED does.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"


class EligibilityStatus(str, Enum):
    ELIGIBLE = "ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    ELIGIBILITY_PENDING = "ELIGIBILITY_PENDING"


class RecommendationDisposition(str, Enum):
    ADVANCE = "ADVANCE"
    HOLD = "HOLD"
    DECLINE = "DECLINE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"


class DecisionDisposition(str, Enum):
    """A binding human decision outcome (never NOT_ELIGIBLE — that is a gate fact)."""

    ADVANCE = "ADVANCE"
    HOLD = "HOLD"
    DECLINE = "DECLINE"


class AssessmentOutcome(str, Enum):
    SCORED = "SCORED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    EVIDENCE_ADMITTED = "EVIDENCE_ADMITTED"
    ASSESSED = "ASSESSED"
    AUTHORITY_EVALUATED = "AUTHORITY_EVALUATED"
    RECOMMENDED = "RECOMMENDED"
    DECIDED = "DECIDED"
    ACTION_REQUESTED = "ACTION_REQUESTED"
    IN_LIFECYCLE_REVIEW = "IN_LIFECYCLE_REVIEW"
    RECONCILED = "RECONCILED"


class EmploymentType(str, Enum):
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    INTERN = "INTERN"
    TEMPORARY = "TEMPORARY"


class FitRange(str, Enum):
    """Analytics-only range label. Never enters gate/eligibility/policy code."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ReviewCheckpoint(str, Enum):
    ONE_MONTH = "ONE_MONTH"
    THREE_MONTH = "THREE_MONTH"
    SIX_MONTH = "SIX_MONTH"
    TWELVE_MONTH = "TWELVE_MONTH"


class OutcomeEvidenceType(str, Enum):
    """Post-hire outcome evidence. No psychological inference."""

    ONBOARDING = "ONBOARDING"
    MANAGER_REVIEW = "MANAGER_REVIEW"
    PERFORMANCE_GOAL = "PERFORMANCE_GOAL"
    COLLABORATION = "COLLABORATION"
    DELIVERY = "DELIVERY"
    RETENTION = "RETENTION"


class Trajectory(str, Enum):
    ON_TRACK = "ON_TRACK"
    OUTPERFORMING = "OUTPERFORMING"
    UNDERPERFORMING = "UNDERPERFORMING"
    AT_RISK = "AT_RISK"
    EXITED = "EXITED"


class CalibrationTarget(str, Enum):
    DIMENSION_WEIGHTS = "DIMENSION_WEIGHTS"
    CONFIDENCE_THRESHOLDS = "CONFIDENCE_THRESHOLDS"
    EVIDENCE_REQUIREMENTS = "EVIDENCE_REQUIREMENTS"
    MANDATORY_GATES = "MANDATORY_GATES"
    ACTION_CONSTRAINTS = "ACTION_CONSTRAINTS"


class ActionAuthorizationVerdict(str, Enum):
    AUTHORIZED = "AUTHORIZED"
    AUTHORIZED_WITH_CONSTRAINTS = "AUTHORIZED_WITH_CONSTRAINTS"
    DENIED = "DENIED"
    INDETERMINATE = "INDETERMINATE"


class AssuranceResult(str, Enum):
    ASSURED = "ASSURED"
    BLOCKED = "BLOCKED"
