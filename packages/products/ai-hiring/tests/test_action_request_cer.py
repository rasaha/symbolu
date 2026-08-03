"""CER construction: minimum-necessary context, data minimization, expiry, hashing."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ugence_ai_hiring.action_requests import ActionRequestStatus
from ugence_ai_hiring.common import utc_now
from ugence_ai_hiring.errors import ActionRequestNotReadyError, ProhibitedActionParameterError

from .conftest import OPS, TENANT, decided_case, published_mapping


def _ready_request(platform, *, params=None):
    _, decision = decided_case(platform)
    published_mapping(platform)
    req = platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS,
        requested_parameters=params or {"stage": "interview"})
    platform.action_request_service.validate_action_request(
        request_id=req.action_request_id, actor=OPS)
    return req, decision


def test_cer_contains_minimum_required_context(action_platform):
    req, decision = _ready_request(action_platform)
    cer = action_platform.cer_binding_service.bind_cer(
        request_id=req.action_request_id, actor=OPS)
    assert cer.tenant_id == TENANT
    assert cer.subject_context.subject_refs
    assert cer.authority_context.authority_type is decision.authority_type
    assert cer.decision_context.decision_id == decision.decision_id
    assert cer.action_type == "ADVANCE_WORKFLOW_STAGE"
    assert cer.target_system == "ATS"
    # request advanced to CER_BOUND
    assert action_platform.action_request_service.get_action_request(
        req.action_request_id).status is ActionRequestStatus.CER_BOUND


def test_cer_excludes_raw_evidence_and_free_text_fields(action_platform):
    req, _ = _ready_request(action_platform)
    cer = action_platform.cer_binding_service.bind_cer(
        request_id=req.action_request_id, actor=OPS)
    fields = set(type(cer).model_fields.keys())
    forbidden = {"resume_text", "raw_text", "interview_transcript", "evidence",
                 "chain_of_thought", "credentials", "access_token", "model_secret"}
    assert forbidden.isdisjoint(fields)


def test_cer_preserves_authority_and_decision_references(action_platform):
    """The CER carries the exact authority type + deciding actor and decision ref."""
    req, decision = _ready_request(action_platform)
    cer = action_platform.cer_binding_service.bind_cer(
        request_id=req.action_request_id, actor=OPS)
    assert cer.authority_context.authority_type is decision.authority_type
    assert cer.authority_context.authority_id == decision.decided_by
    assert cer.decision_context.decision_id == decision.decision_id
    assert cer.decision_context.decision_outcome is decision.outcome


def test_cer_hash_stable_for_identical_input(action_platform):
    req, _ = _ready_request(action_platform)
    cer = action_platform.cer_binding_service.bind_cer(
        request_id=req.action_request_id, actor=OPS)
    assert cer.content_hash == cer.compute_hash()


def test_cer_expiration_is_enforced(action_platform):
    """A CER valid at bind time but expired at submit time fails closed."""
    from datetime import datetime, timezone
    from ugence_ai_hiring.errors import CERExpiredError
    from ugence_ai_hiring.services.cer_binding_service import CERBindingService
    from ugence_ai_hiring.services.action_authorization_service import ActionAuthorizationService

    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 1, 1, 14, 0, 0, tzinfo=timezone.utc)  # 2h later

    req, _ = _ready_request(action_platform)
    # Binder issues a CER valid for one minute, anchored at t0.
    binder = CERBindingService(
        action_platform.action_request_repo, action_platform.decision_case_repo,
        action_platform.audit_service, action_platform.identity_provider,
        action_platform.evidence_access_policy,
        default_validity=timedelta(minutes=1), clock=lambda: t0)
    cer = binder.bind_cer(request_id=req.action_request_id, actor=OPS)
    assert not cer.is_expired(t0) and cer.is_expired(t_late)
    # Authorization service sees a much later "now" → the CER is expired.
    late_authz = ActionAuthorizationService(
        action_platform.action_request_repo, action_platform.control_plane,
        action_platform.audit_service, action_platform.identity_provider,
        action_platform.evidence_access_policy, clock=lambda: t_late)
    with pytest.raises(CERExpiredError):
        late_authz.submit_for_authorization(request_id=req.action_request_id, actor=OPS)


def test_binding_rejects_credential_like_parameters(action_platform):
    # Publish a mapping that permits an 'auth' optional field, then try to smuggle
    # a credential-like key through it. The binder rejects it defensively even if
    # the schema somehow allowed it.
    _, decision = decided_case(action_platform)
    published_mapping(action_platform, optional_fields=("note",))
    req = action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})
    action_platform.action_request_service.validate_action_request(
        request_id=req.action_request_id, actor=OPS)
    # Manually craft a snapshot carrying a credential-like param to exercise the
    # binder's defense in depth.
    tampered = action_platform.action_request_service.get_action_request(
        req.action_request_id).evolve(
        request_version_id="rv-x",
        requested_parameters={"stage": "x", "access_token": "abc"})
    action_platform.action_request_repo.save_action_request_snapshot(tampered)
    with pytest.raises(ProhibitedActionParameterError):
        action_platform.cer_binding_service.bind_cer(
            request_id=req.action_request_id, actor=OPS)


def test_bind_requires_ready_for_binding_status(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    req = action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})
    # Still DRAFT (not validated) → binding is refused.
    with pytest.raises(ActionRequestNotReadyError):
        action_platform.cer_binding_service.bind_cer(
            request_id=req.action_request_id, actor=OPS)
