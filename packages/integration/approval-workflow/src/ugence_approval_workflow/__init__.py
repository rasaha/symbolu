"""Ugence Approval Workflow — the canonical human approval and exception queue.

    THIS PACKAGE RECORDS AND REPORTS AN APPROVAL.
    IT NEVER APPROVES, AUTHENTICATES, MINTS AUTHORITY, OR EXECUTES.

Approval state lives in Ugence (gap-sequencing ADR decision D-2). This package owns
the queue, the state machine, expiry and the bounded exception path; it owns neither
approval *authority* — reserved to Decision Authority — nor the policy-pack review
flow reserved to the Policy Workflow Compiler.

Scoped and ratified by ``docs/architecture/ADR_UGENCE_APPROVAL_WORKFLOW_SCOPING.md``.
A ``GRANTED`` approval is an input to a governed decision, not a decision.
"""

from __future__ import annotations

from .consumption import (
    APPROVAL_KEY_PREFIX,
    CONSUMPTION_ID_PREFIX,
    ConsumeOutcome,
    ConsumptionKey,
    ConsumptionResult,
    consumption_id_for,
    validate_for_consumption,
)
from .eligibility import (
    ELIGIBLE_APPROVER_KINDS,
    ApproverEligibilityPort,
    ApproverKind,
    ApproverRef,
    EligibilityDecision,
    StaticApproverEligibility,
    structural_refusals,
)
from .errors import (
    ApprovalAlreadyExistsError,
    ApprovalNotFoundError,
    ApprovalWorkflowError,
    ArtifactIntegrityError,
    ContractViolation,
    EligibilityRefused,
    IllegalTransitionError,
    ProductionModeRefused,
    StoreUnavailableError,
)
from .memory import InMemoryApprovalWorkflowStore
from .ports import ApprovalWorkflowPort
from .records import ApprovalEvent, ApprovalRecord
from .sqlite import SCHEMA_VERSION, SqliteApprovalWorkflowStore
from .states import (
    CONSUMABLE_STATES,
    EXPIRABLE_STATES,
    LEGAL_TRANSITIONS,
    OPEN_STATES,
    STATE_RANK,
    TERMINAL_STATES,
    ApprovalState,
    ReviewDecision,
    is_legal_transition,
    require_transition,
    state_for_decision,
)
from .subject import APPROVAL_ID_PREFIX, ApprovalSubject, approval_id_for
from .version import CONTRACT_VERSION, ENFORCEMENT_ENABLED, MATURITY, __version__
from .workflow import (
    build_request,
    next_on_consume,
    next_on_decide,
    next_on_exception_decision,
    next_on_exception_request,
    next_on_present,
    next_on_withdraw,
    superseding_refusal,
)

__all__ = [
    "__version__", "CONTRACT_VERSION", "MATURITY", "ENFORCEMENT_ENABLED", "SCHEMA_VERSION",
    # subject
    "ApprovalSubject", "approval_id_for", "APPROVAL_ID_PREFIX",
    # state machine
    "ApprovalState", "ReviewDecision", "LEGAL_TRANSITIONS", "STATE_RANK", "TERMINAL_STATES",
    "EXPIRABLE_STATES", "CONSUMABLE_STATES", "OPEN_STATES", "is_legal_transition",
    "require_transition", "state_for_decision",
    # artifact
    "ApprovalRecord", "ApprovalEvent",
    # eligibility (a port, never an identity check)
    "ApproverEligibilityPort", "ApproverKind", "ApproverRef", "EligibilityDecision",
    "ELIGIBLE_APPROVER_KINDS", "StaticApproverEligibility", "structural_refusals",
    # transition rules
    "build_request", "next_on_present", "next_on_decide", "next_on_exception_request",
    "next_on_exception_decision", "next_on_withdraw", "next_on_consume", "superseding_refusal",
    # once-only consumption
    "ConsumptionKey", "ConsumptionResult", "ConsumeOutcome", "consumption_id_for",
    "validate_for_consumption", "APPROVAL_KEY_PREFIX", "CONSUMPTION_ID_PREFIX",
    # ports and adapters
    "ApprovalWorkflowPort", "InMemoryApprovalWorkflowStore", "SqliteApprovalWorkflowStore",
    # errors
    "ApprovalWorkflowError", "ContractViolation", "ApprovalNotFoundError",
    "ApprovalAlreadyExistsError", "IllegalTransitionError", "EligibilityRefused",
    "ArtifactIntegrityError", "StoreUnavailableError", "ProductionModeRefused",
]
