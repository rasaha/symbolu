"""Bounded enumerations for the risk-authority domain.

Every state space in the package is closed and small on purpose (spec §28
"Decision Semantics", §2 policy determinism). Runtime enforcement branches on
these values, never on free text.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "WorkflowStatus",
    "PredicateOp",
    "RuleEffect",
    "RiskClass",
    "RiskCaseState",
    "ControlStatus",
    "EvidenceState",
    "RiskRecommendation",
    "RiskOutcome",
    "ActionGateDecision",
    "AuthorityType",
    "GovernanceEventType",
]


class WorkflowStatus(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"


class PredicateOp(str, Enum):
    """The bounded predicate language (spec §2, user brief §2).

    No arbitrary Python execution is permitted inside a WorkflowIR; a rule
    condition is one of these deterministic operators over case facts.
    """

    EQ = "EQ"
    NE = "NE"
    GT = "GT"
    GTE = "GTE"
    LT = "LT"
    LTE = "LTE"
    IN = "IN"
    NOT_IN = "NOT_IN"
    SUBSET_OF = "SUBSET_OF"
    EXISTS = "EXISTS"
    ALL_OF = "ALL_OF"
    ANY_OF = "ANY_OF"


class RuleEffect(str, Enum):
    """What a rule asserts about its required controls."""

    # Deny unless every required control is satisfied (the default high-impact
    # posture; spec §7.4 ``DENY_UNLESS_ALL``).
    DENY_UNLESS_ALL = "DENY_UNLESS_ALL"
    # Allow only if every required control is satisfied, else escalate.
    ALLOW_IF_ALL = "ALLOW_IF_ALL"


class RiskClass(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskCaseState(str, Enum):
    """RiskDecisionCase lifecycle (spec §8.3)."""

    CREATED = "CREATED"
    CLASSIFIED = "CLASSIFIED"
    CONTROLS_RESOLVED = "CONTROLS_RESOLVED"
    EVIDENCE_PENDING = "EVIDENCE_PENDING"
    EVIDENCE_COMPLETE = "EVIDENCE_COMPLETE"
    CONTROL_EVALUATED = "CONTROL_EVALUATED"
    AUTHORITY_REVIEW = "AUTHORITY_REVIEW"
    APPROVED = "APPROVED"
    CONDITIONAL = "CONDITIONAL"
    DENIED = "DENIED"
    ENVELOPE_ISSUED = "ENVELOPE_ISSUED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"


class ControlStatus(str, Enum):
    """Control-assurance result states (spec §10).

    Non-compensatory: only ``PASS`` (or ``NOT_APPLICABLE``) can contribute to
    an approval. ``UNKNOWN`` / ``MISSING`` / ``STALE`` must never be silently
    coerced to ``PASS``.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    MISSING = "MISSING"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceState(str, Enum):
    """Evidence admission states (spec §9)."""

    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    STALE = "STALE"
    UNVERIFIABLE = "UNVERIFIABLE"
    CONFLICTING = "CONFLICTING"


class RiskRecommendation(str, Enum):
    """What the Risk Engine (an evaluator) recommends — advisory only."""

    ALLOW = "ALLOW"
    ALLOW_WITH_CONDITIONS = "ALLOW_WITH_CONDITIONS"
    ESCALATE = "ESCALATE"
    DENY = "DENY"


class RiskOutcome(str, Enum):
    """The binding outcome issued by Decision Authority (spec §11.1)."""

    ALLOW = "ALLOW"
    ALLOW_WITH_CONDITIONS = "ALLOW_WITH_CONDITIONS"
    ESCALATE = "ESCALATE"
    DENY = "DENY"


class ActionGateDecision(str, Enum):
    """ActionGate runtime decision (spec §28)."""

    AUTHORIZED = "AUTHORIZED"
    DENIED = "DENIED"
    RETRY_STATE_CHANGED = "RETRY_STATE_CHANGED"


class AuthorityType(str, Enum):
    RISK_APPROVAL = "RISK_APPROVAL"
    RISK_DELEGATION = "RISK_DELEGATION"
    ADMIN_OVERRIDE = "ADMIN_OVERRIDE"


class GovernanceEventType(str, Enum):
    """Append-only audit event types (spec §23)."""

    CASE_CREATED = "CASE_CREATED"
    RISK_CLASSIFIED = "RISK_CLASSIFIED"
    CONTROL_REQUIRED = "CONTROL_REQUIRED"
    CONTROL_EVALUATED = "CONTROL_EVALUATED"
    CONTROL_PASSED = "CONTROL_PASSED"
    CONTROL_FAILED = "CONTROL_FAILED"
    CASE_STATE_CHANGED = "CASE_STATE_CHANGED"
    RISK_EVALUATED = "RISK_EVALUATED"
    RISK_APPROVED = "RISK_APPROVED"
    RISK_DENIED = "RISK_DENIED"
    DECISION_ISSUED = "DECISION_ISSUED"
    ENVELOPE_ISSUED = "ENVELOPE_ISSUED"
    ENVELOPE_REVOKED = "ENVELOPE_REVOKED"
    AUTHORITY_EPOCH_ADVANCED = "AUTHORITY_EPOCH_ADVANCED"
    ACTION_REQUESTED = "ACTION_REQUESTED"
    ACTION_AUTHORIZED = "ACTION_AUTHORIZED"
    ACTION_DENIED = "ACTION_DENIED"
