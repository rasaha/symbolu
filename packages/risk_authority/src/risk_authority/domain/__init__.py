"""Immutable typed domain artifacts for the risk-authority kernel."""

from __future__ import annotations

from .actions import ActionAuthorization, CanonicalAction, action_digest
from .authority import AuthorityGrant, AuthorityPrincipal, authority_violations
from .authority_signal import (
    AUTHORITY_SIGNAL_SCHEMA_VERSION,
    SUPPORTED_SIGNAL_SCHEMA_VERSIONS,
    AuthorityReassessmentSignal,
    SignalChangeType,
    SignalTarget,
    SignalTargetType,
)
from .binding import (
    AdmittedContext,
    CaseBindingContext,
    binding_violations,
    usable_control_results,
)
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
    ArtifactBinding,
    EnvelopeBindings,
    EnvelopeConditions,
    RiskAuthorizationEnvelope,
)
from .errors import (
    AuthorityDeniedError,
    IllegalTransitionError,
    SnapshotIntegrityError,
    MonotonicityViolationError,
    RiskAuthorityError,
)
from .events import GovernanceEvent, make_event
from .evidence import (
    EVIDENCE_SCHEMA_VERSION,
    SUPPORTED_EVIDENCE_SCHEMA_VERSIONS,
    ControlEvidenceRecord,
    EvidenceAdmission,
    evidence_integrity_digest,
)
from .risk_case import (
    ALLOWED_TRANSITIONS,
    RequestedCapabilities,
    RiskCaseSnapshot,
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
    # RA-6 reassessment signal (neutral; carries no authority)
    "AuthorityReassessmentSignal",
    "SignalChangeType",
    "SignalTarget",
    "SignalTargetType",
    "AUTHORITY_SIGNAL_SCHEMA_VERSION",
    "SUPPORTED_SIGNAL_SCHEMA_VERSIONS",
    # controls / evidence
    "ControlResult",
    "required_controls_satisfied",
    "unsatisfied_controls",
    "ControlEvidenceRecord",
    "EvidenceAdmission",
    "EVIDENCE_SCHEMA_VERSION",
    "SUPPORTED_EVIDENCE_SCHEMA_VERSIONS",
    "evidence_integrity_digest",
    # trust binding (RA-5 §8)
    "CaseBindingContext",
    "AdmittedContext",
    "binding_violations",
    "usable_control_results",
    # decision / envelope / actions
    "RiskDecision",
    "RiskAuthorizationEnvelope",
    "ArtifactBinding",
    "EnvelopeConditions",
    "EnvelopeBindings",
    "CanonicalAction",
    "ActionAuthorization",
    "action_digest",
    # case
    "RiskDecisionCase",
    "RiskCaseSnapshot",
    "RequestedCapabilities",
    "ALLOWED_TRANSITIONS",
    # events
    "GovernanceEvent",
    "make_event",
    # errors
    "RiskAuthorityError",
    "IllegalTransitionError",
    "SnapshotIntegrityError",
    "AuthorityDeniedError",
    "MonotonicityViolationError",
]
