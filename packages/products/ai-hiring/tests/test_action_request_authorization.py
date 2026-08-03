"""Control-plane authorization: distinct outcomes, constraints, retries, no execution."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.action_requests import (
    ActionRequestStatus,
    AuthorizationOutcome,
    OfflineDeterministicControlPlane,
)
from ugence_ai_hiring.errors import (
    ActionRequestAlreadyAuthorizedError,
    AuthorizationResponseMismatchError,
    AuthorizationSubmissionError,
)
from ugence_ai_hiring.services.action_authorization_service import ActionAuthorizationService

from .conftest import OPS, decided_case, published_mapping


def _cer_bound_request(platform, *, action_type="ADVANCE_WORKFLOW_STAGE",
                       mapping_action="ADVANCE_WORKFLOW_STAGE"):
    _, decision = decided_case(platform)
    published_mapping(platform, action_type=mapping_action)
    req = platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "interview"})
    platform.action_request_service.validate_action_request(
        request_id=req.action_request_id, actor=OPS)
    platform.cer_binding_service.bind_cer(request_id=req.action_request_id, actor=OPS)
    return req


def _authz_with(platform, cp) -> ActionAuthorizationService:
    return ActionAuthorizationService(
        platform.action_request_repo, cp, platform.audit_service,
        platform.identity_provider, platform.evidence_access_policy)


def test_deterministic_authorization_succeeds(action_platform):
    req = _cer_bound_request(action_platform)
    resp = action_platform.action_authorization_service.submit_for_authorization(
        request_id=req.action_request_id, actor=OPS)
    assert resp.outcome is AuthorizationOutcome.AUTHORIZED
    status = action_platform.action_request_service.get_action_request(
        req.action_request_id).status
    assert status is ActionRequestStatus.AUTHORIZED


def test_authorized_request_remains_unexecuted(action_platform):
    req = _cer_bound_request(action_platform)
    action_platform.action_authorization_service.submit_for_authorization(
        request_id=req.action_request_id, actor=OPS)
    final = action_platform.action_request_service.get_action_request(
        req.action_request_id)
    # There is no executed/succeeded status and no execution field to set.
    assert final.status is ActionRequestStatus.AUTHORIZED
    assert "EXECUTED" not in {s.value for s in ActionRequestStatus}


def test_constrained_authorization_preserves_constraints(action_platform):
    req = _cer_bound_request(action_platform, mapping_action="SEND_FOR_BACKGROUND_CHECK")
    cp = OfflineDeterministicControlPlane(
        constrained_action_types=frozenset({"SEND_FOR_BACKGROUND_CHECK"}),
        constraints=("consent_required", "region:EU"), obligations=("notify_subject",))
    resp = _authz_with(action_platform, cp).submit_for_authorization(
        request_id=req.action_request_id, actor=OPS)
    assert resp.outcome is AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS
    assert "consent_required" in resp.constraints
    assert action_platform.action_request_service.get_action_request(
        req.action_request_id).status is ActionRequestStatus.AUTHORIZED_WITH_CONSTRAINTS


def test_denial_is_preserved_and_distinct(action_platform):
    req = _cer_bound_request(action_platform, mapping_action="CLOSE_CANDIDATE_WORKFLOW")
    cp = OfflineDeterministicControlPlane(
        denied_action_types=frozenset({"CLOSE_CANDIDATE_WORKFLOW"}))
    resp = _authz_with(action_platform, cp).submit_for_authorization(
        request_id=req.action_request_id, actor=OPS)
    assert resp.outcome is AuthorizationOutcome.DENIED
    assert action_platform.action_request_service.get_action_request(
        req.action_request_id).status is ActionRequestStatus.DENIED


def test_indeterminate_is_not_approval(action_platform):
    req = _cer_bound_request(action_platform, mapping_action="REQUEST_ADDITIONAL_REVIEW")
    cp = OfflineDeterministicControlPlane(
        indeterminate_action_types=frozenset({"REQUEST_ADDITIONAL_REVIEW"}))
    resp = _authz_with(action_platform, cp).submit_for_authorization(
        request_id=req.action_request_id, actor=OPS)
    assert resp.outcome is AuthorizationOutcome.INDETERMINATE
    status = action_platform.action_request_service.get_action_request(
        req.action_request_id).status
    assert status is ActionRequestStatus.INDETERMINATE
    assert status not in (ActionRequestStatus.AUTHORIZED,
                          ActionRequestStatus.AUTHORIZED_WITH_CONSTRAINTS)


def test_malformed_response_is_rejected(action_platform):
    class BadControlPlane:
        def authorize(self, action_request, cer):
            from ugence_ai_hiring.action_requests import ActionAuthorizationResponse
            return ActionAuthorizationResponse(
                authorization_id="az-bad", action_request_id="WRONG-ID",
                cer_id=cer.cer_id, outcome=AuthorizationOutcome.AUTHORIZED)

    req = _cer_bound_request(action_platform)
    with pytest.raises(AuthorizationResponseMismatchError):
        _authz_with(action_platform, BadControlPlane()).submit_for_authorization(
            request_id=req.action_request_id, actor=OPS)


def test_provider_error_is_not_authorization(action_platform):
    class ExplodingControlPlane:
        def authorize(self, action_request, cer):
            raise RuntimeError("provider unreachable")

    req = _cer_bound_request(action_platform)
    with pytest.raises(AuthorizationSubmissionError):
        _authz_with(action_platform, ExplodingControlPlane()).submit_for_authorization(
            request_id=req.action_request_id, actor=OPS)


def test_retry_after_indeterminate_appends_a_new_attempt(action_platform):
    req = _cer_bound_request(action_platform, mapping_action="REQUEST_ADDITIONAL_REVIEW")
    cp = OfflineDeterministicControlPlane(
        indeterminate_action_types=frozenset({"REQUEST_ADDITIONAL_REVIEW"}))
    authz = _authz_with(action_platform, cp)
    authz.submit_for_authorization(request_id=req.action_request_id, actor=OPS)
    # Resubmit — a fresh attempt is appended (INDETERMINATE is retryable).
    authz.submit_for_authorization(request_id=req.action_request_id, actor=OPS)
    history = authz.get_authorization_history(req.action_request_id)
    assert len(history) == 2
    assert [h.attempt for h in history] == [1, 2]


def test_already_authorized_request_cannot_be_resubmitted(action_platform):
    req = _cer_bound_request(action_platform)
    action_platform.action_authorization_service.submit_for_authorization(
        request_id=req.action_request_id, actor=OPS)
    with pytest.raises(ActionRequestAlreadyAuthorizedError):
        action_platform.action_authorization_service.submit_for_authorization(
            request_id=req.action_request_id, actor=OPS)
