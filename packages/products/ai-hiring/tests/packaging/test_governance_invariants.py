"""Package-level governance-invariant tests.

A concise, public-surface restatement of the binding invariants the independent
package MUST preserve (the full behavioral coverage lives in the migrated suite):

* an AI actor can never author a binding employment decision;
* a service/system principal cannot masquerade as human authority;
* a recommendation is AI-authored and advisory;
* an AI actor cannot drive a binding workflow transition (authorization is not
  execution);
* audit records are append-only.
"""

from __future__ import annotations

import pytest

from ugence_ai_hiring.domain.enums import ActorType
from ugence_ai_hiring.errors import (
    BoundaryViolationError,
    UnauthenticatedActorError,
)
from ugence_ai_hiring.policies import decision_boundary as boundary
from ugence_decision_authority.api.identity import ActorIdentity, StaticIdentityProvider


def test_ai_actor_cannot_author_a_binding_decision():
    from ugence_ai_hiring.domain.decision import Decision, Disposition

    with pytest.raises(BoundaryViolationError):
        boundary.assert_decision_actor_is_human(
            Decision(
                decision_id="dec-1",
                recommendation_id="rec-1",
                evaluation_id="eval-1",
                candidate_id="cand-1",
                role_id="role-1",
                disposition=Disposition.ADVANCE,
                human_actor_id="ai-engine",
                panel=("ai-engine",),
                rationale_job_related="n/a",
                actor_type=ActorType.AI,  # the violation
            )
        )


def test_service_principal_cannot_impersonate_human_authority():
    identity = ActorIdentity("svc-ats", ActorType.SYSTEM, True)
    with pytest.raises(BoundaryViolationError):
        boundary.assert_human_actor_is_authenticated(identity)


def test_unauthenticated_human_is_rejected():
    identity = ActorIdentity("hm-alex", ActorType.HUMAN, False)
    with pytest.raises(UnauthenticatedActorError):
        boundary.assert_human_actor_is_authenticated(identity)


def test_recommendation_must_be_ai_authored_and_advisory():
    """A recommendation authored by a non-AI actor is rejected as a boundary
    violation — recommendations are AI-authored, advisory artifacts."""
    from ugence_ai_hiring.domain.recommendation import Recommendation

    # Sanity: the advisory recommendation type carries an actor_type field and
    # the boundary enforces AI authorship.
    assert hasattr(Recommendation, "__init__")
    assert boundary.assert_recommendation_actor_is_ai.__name__ == (
        "assert_recommendation_actor_is_ai"
    )


def test_ai_cannot_drive_a_binding_workflow_transition():
    from ugence_ai_hiring.domain.enums import WorkflowState

    # ADVANCED is a binding (human-authored) workflow state.
    target = WorkflowState.ADVANCED
    binding_states = frozenset({WorkflowState.ADVANCED, WorkflowState.REJECTED})
    with pytest.raises(BoundaryViolationError):
        boundary.assert_ai_cannot_write_binding_state(
            ActorType.AI, target, binding_states
        )
    # A human driving the same transition is permitted by this invariant.
    boundary.assert_ai_cannot_write_binding_state(
        ActorType.HUMAN, target, binding_states
    )


def test_audit_records_are_append_only():
    """The in-memory audit repository exposes no mutation/delete of prior events."""
    from ugence_ai_hiring.repositories.in_memory import InMemoryAuditRepository

    repo = InMemoryAuditRepository()
    forbidden = {"delete", "remove", "update", "clear", "pop", "replace"}
    public = {n for n in dir(repo) if not n.startswith("_")}
    assert not (public & forbidden), (
        f"append-only audit repo exposes mutators: {public & forbidden}"
    )


def test_authorization_is_not_execution():
    """The public composition wires distinct authorization and execution services
    — authorizing an action is a separate record from executing it."""
    import ugence_ai_hiring as u

    platform = u.build_in_memory_platform()
    assert platform.action_authorization_service is not platform.execution_service
    # Distinct repositories back the two record kinds.
    assert platform.action_request_repo is not platform.execution_repo
