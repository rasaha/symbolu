"""Governed action requests and CER binding (Phase 4B).

Converts an authorized ``DecisionRecord`` into a governed ``ActionRequest``, binds
the minimum runtime context as a ``ContextEnvelopeRecord`` (CER), and submits it
through a provider-neutral control-plane port for authorization.

Phase 4B prepares and authorizes a proposed action. **It does not execute the
action** and does not claim that authorization produced an external-world result.
"""

from __future__ import annotations

from .action_mapping import ActionMapping, ParameterSchema
from .action_request import ActionRequest
from .authorization import ActionAuthorizationResponse
from .cer import (
    AuthoritySummary,
    ContextEnvelopeRecord,
    DecisionContext,
    PolicyContext,
    SubjectContext,
)
from .control_plane import ActionControlPlanePort, OfflineDeterministicControlPlane
from .lifecycle import ALLOWED_TRANSITIONS, is_legal_transition
from .status import (
    ActionMappingStatus,
    ActionRequestStatus,
    AUTHORIZED_STATUSES,
    AuthorizationOutcome,
    OUTCOME_TO_STATUS,
    RETRYABLE_STATUSES,
    TERMINAL_REQUEST_STATUSES,
)
from .validation import (
    ActionRequestValidationIssue,
    ActionRequestValidationResult,
)

__all__ = [
    # contracts
    "ActionRequest",
    "ActionMapping",
    "ParameterSchema",
    "ContextEnvelopeRecord",
    "SubjectContext",
    "AuthoritySummary",
    "PolicyContext",
    "DecisionContext",
    "ActionAuthorizationResponse",
    # control plane
    "ActionControlPlanePort",
    "OfflineDeterministicControlPlane",
    # vocabularies
    "ActionRequestStatus",
    "AuthorizationOutcome",
    "ActionMappingStatus",
    "OUTCOME_TO_STATUS",
    "TERMINAL_REQUEST_STATUSES",
    "AUTHORIZED_STATUSES",
    "RETRYABLE_STATUSES",
    # lifecycle + validation
    "ALLOWED_TRANSITIONS",
    "is_legal_transition",
    "ActionRequestValidationIssue",
    "ActionRequestValidationResult",
]
