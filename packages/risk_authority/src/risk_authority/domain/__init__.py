"""Immutable typed domain artifacts for the risk-authority kernel."""

from __future__ import annotations

from .actions import ActionAuthorization, CanonicalAction, action_digest
from .authority import AuthorityGrant, AuthorityPrincipal, authority_violations
from .controls import (
    ControlResult,
    required_controls_satisfied,
    unsatisfied_controls,
)
from .decision import RiskDecision
from .enums import (
    ActionGateDecision,
    AuthorityType,
    ControlStatus,
    EvidenceState,
    GovernanceEventType,
    PredicateOp,
    RiskCaseState,
    RiskClass,
    RiskOutcome,
    RiskRecommendation,
    RuleEffect,
    WorkflowStatus,
)
from .envelope import (
    EnvelopeBindings,
    EnvelopeConditions,
    RiskAuthorizationEnvelope,
)
from .errors import (
    AuthorityDeniedError,
    IllegalTransitionError,
    MonotonicityViolationError,
    RiskAuthorityError,
)
from .events import GovernanceEvent, make_event
from .evidence import ControlEvidenceRecord, EvidenceAdmission
from .risk_case import (
    ALLOWED_TRANSITIONS,
    RequestedCapabilities,
    RiskDecisionCase,
)
from .scope import Scope, subset_violations
from .workflow_ir import Predicate, WorkflowIR, WorkflowRule

__all__ = [
    # enums
    "ActionGateDecision",
    "AuthorityType",
    "ControlStatus",
    "EvidenceState",
    "GovernanceEventType",
    "PredicateOp",
    "RiskCaseState",
    "RiskClass",
    "RiskOutcome",
    "RiskRecommendation",
    "RuleEffect",
    "WorkflowStatus",
    # workflow
    "Predicate",
    "WorkflowIR",
    "WorkflowRule",
    # scope / authority
    "Scope",
    "subset_violations",
    "AuthorityGrant",
    "AuthorityPrincipal",
    "authority_violations",
    # controls / evidence
    "ControlResult",
    "required_controls_satisfied",
    "unsatisfied_controls",
    "ControlEvidenceRecord",
    "EvidenceAdmission",
    # decision / envelope / actions
    "RiskDecision",
    "RiskAuthorizationEnvelope",
    "EnvelopeConditions",
    "EnvelopeBindings",
    "CanonicalAction",
    "ActionAuthorization",
    "action_digest",
    # case
    "RiskDecisionCase",
    "RequestedCapabilities",
    "ALLOWED_TRANSITIONS",
    # events
    "GovernanceEvent",
    "make_event",
    # errors
    "RiskAuthorityError",
    "IllegalTransitionError",
    "AuthorityDeniedError",
    "MonotonicityViolationError",
]
