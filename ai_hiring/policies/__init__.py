"""Policy layer: boundary enforcement and transition rules.

Business rules that guard the AI/human boundary and workflow legality live here
as reusable, testable functions — not inline in services or route handlers.
"""

from __future__ import annotations

from . import decision_boundary, transition_policy
from .decision_boundary import (
    ActorIdentity,
    IdentityProvider,
    StaticIdentityProvider,
    assert_ai_cannot_write_binding_state,
    assert_blocked_evaluation_cannot_be_decided,
    assert_decision_actor_is_human,
    assert_decision_has_job_related_rationale,
    assert_human_actor_is_authenticated,
    assert_override_present_when_required,
    assert_recommendation_actor_is_ai,
)
from .transition_policy import (
    ALLOWED_TRANSITIONS,
    HUMAN_DECISION_STATES,
    authorize_actor_for_target,
    disposition_to_state,
    is_binding_state,
    requires_human_decision,
    validate_transition,
)

__all__ = [
    "decision_boundary",
    "transition_policy",
    "ActorIdentity",
    "IdentityProvider",
    "StaticIdentityProvider",
    "assert_recommendation_actor_is_ai",
    "assert_decision_actor_is_human",
    "assert_human_actor_is_authenticated",
    "assert_decision_has_job_related_rationale",
    "assert_override_present_when_required",
    "assert_ai_cannot_write_binding_state",
    "assert_blocked_evaluation_cannot_be_decided",
    "ALLOWED_TRANSITIONS",
    "HUMAN_DECISION_STATES",
    "authorize_actor_for_target",
    "disposition_to_state",
    "is_binding_state",
    "requires_human_decision",
    "validate_transition",
]
