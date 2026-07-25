"""Deterministic vocabularies for the DecisionCase aggregate (Phase 4A).

These enums name states and kinds only. They carry no scoring, ranking, or
execution semantics. Critically, no *binding authority* type is an AI model, and
no lifecycle state means "executed" — Phase 4A stops at ``DECIDED``.
"""

from __future__ import annotations

from enum import Enum


class CaseStatus(str, Enum):
    """The lifecycle state of a decision case."""

    CREATED = "CREATED"
    EVIDENCE_ASSEMBLY = "EVIDENCE_ASSEMBLY"
    ASSESSMENT_IN_PROGRESS = "ASSESSMENT_IN_PROGRESS"
    READY_FOR_RECOMMENDATION = "READY_FOR_RECOMMENDATION"
    RECOMMENDATION_AVAILABLE = "RECOMMENDATION_AVAILABLE"
    UNDER_REVIEW = "UNDER_REVIEW"
    READY_FOR_DECISION = "READY_FOR_DECISION"
    DECIDED = "DECIDED"
    SUPERSEDED = "SUPERSEDED"
    CANCELLED = "CANCELLED"
    CLOSED = "CLOSED"


#: States after which a case snapshot is finalized and never mutated in place.
TERMINAL_CASE_STATUSES = frozenset(
    {CaseStatus.SUPERSEDED, CaseStatus.CANCELLED, CaseStatus.CLOSED})


class OperatingMode(str, Enum):
    """How the case reaches a decision. None of these is autonomous AI discretion."""

    DELIBERATIVE = "DELIBERATIVE"           # a human reviews and decides
    DELEGATED_POLICY = "DELEGATED_POLICY"   # a bounded, published policy decides
    REAL_TIME_PREPARATION = "REAL_TIME_PREPARATION"  # prepares a request; no action


class ProposedOutcome(str, Enum):
    """What a recommendation proposes. Advisory only — it never binds the case."""

    ADVANCE = "ADVANCE"
    HOLD = "HOLD"
    REJECT = "REJECT"
    REQUEST_ADDITIONAL_EVIDENCE = "REQUEST_ADDITIONAL_EVIDENCE"
    NO_RECOMMENDATION = "NO_RECOMMENDATION"


class GeneratorType(str, Enum):
    """Who produced a recommendation. AI-assisted is permitted; AI cannot *decide*."""

    HUMAN = "HUMAN"
    DETERMINISTIC_POLICY = "DETERMINISTIC_POLICY"
    AI_ASSISTED = "AI_ASSISTED"
    IMPORTED_APPROVED_SOURCE = "IMPORTED_APPROVED_SOURCE"


class RecommendationStatus(str, Enum):
    PROPOSED = "PROPOSED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class DecisionOutcome(str, Enum):
    """The substantive result an authorized actor records. Not an execution."""

    ADVANCE = "ADVANCE"
    HOLD = "HOLD"
    REJECT = "REJECT"
    DEFER = "DEFER"


class AuthorityType(str, Enum):
    """Who may bind a decision. Deliberately excludes any AI model."""

    HUMAN_REVIEWER = "HUMAN_REVIEWER"
    HUMAN_APPROVER = "HUMAN_APPROVER"
    DELEGATED_POLICY = "DELEGATED_POLICY"
    COMMITTEE = "COMMITTEE"
    EXTERNAL_AUTHORITY = "EXTERNAL_AUTHORITY"


#: Authority types that require an authenticated *human* actor.
HUMAN_AUTHORITIES = frozenset(
    {AuthorityType.HUMAN_REVIEWER, AuthorityType.HUMAN_APPROVER,
     AuthorityType.COMMITTEE})


class EffectiveStatus(str, Enum):
    """Whether a recorded decision is currently in effect."""

    EFFECTIVE = "EFFECTIVE"
    SUPERSEDED = "SUPERSEDED"
    VOID = "VOID"


class ReviewTaskType(str, Enum):
    REQUIRED_REVIEW = "REQUIRED_REVIEW"
    SECONDARY_APPROVAL = "SECONDARY_APPROVAL"
    CONFLICT_REVIEW = "CONFLICT_REVIEW"
    EVIDENCE_GAP_REVIEW = "EVIDENCE_GAP_REVIEW"
    RECOMMENDATION_REVIEW = "RECOMMENDATION_REVIEW"
    DECISION_REVIEW = "DECISION_REVIEW"


class ReviewTaskStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    WAIVED = "WAIVED"
    CANCELLED = "CANCELLED"
