"""Binding an ExecutionIntent to an authorized, unexpired ActionRequest."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ai_hiring.action_requests import AuthorizationOutcome, OfflineDeterministicControlPlane
from ai_hiring.errors import (
    ActionRequestNotExecutableError,
    AuthorizationExpiredError,
    CERExpiredForExecutionError,
    ExecutionParameterMismatchError,
)
from ai_hiring.executions import ExecutionStatus
from ai_hiring.services.action_authorization_service import ActionAuthorizationService

from .conftest import EXECUTOR, OPS, TENANT, authorized_request, decided_case, published_mapping


def test_only_authorized_request_creates_intent(execution_platform):
    req = authorized_request(execution_platform)
    intent = execution_platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR)
    assert intent.status is ExecutionStatus.INTENT_CREATED
    assert intent.action_request_id == req.action_request_id
    assert intent.action_request_version == req.version
    assert intent.action_type == req.action_type
    assert intent.target_system == req.target_system


def test_unauthorized_request_cannot_create_intent(execution_platform):
    """A request that was only CER-bound (never submitted) is not executable."""
    _, decision = decided_case(execution_platform)
    published_mapping(execution_platform)
    req = execution_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})
    execution_platform.action_request_service.validate_action_request(
        request_id=req.action_request_id, actor=OPS)
    execution_platform.cer_binding_service.bind_cer(
        request_id=req.action_request_id, actor=OPS)
    with pytest.raises(ActionRequestNotExecutableError):
        execution_platform.execution_service.create_execution_intent(
            action_request_id=req.action_request_id, created_by=EXECUTOR)


def test_constrained_authorization_is_reflected_in_intent(execution_platform):
    """AUTHORIZED_WITH_CONSTRAINTS carries its constraints/obligations into the intent."""
    _, decision = decided_case(execution_platform)
    published_mapping(execution_platform, action_type="SEND_FOR_BACKGROUND_CHECK")
    req = execution_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "bg"})
    execution_platform.action_request_service.validate_action_request(
        request_id=req.action_request_id, actor=OPS)
    execution_platform.cer_binding_service.bind_cer(
        request_id=req.action_request_id, actor=OPS)
    constrained_cp = OfflineDeterministicControlPlane(
        constrained_action_types=frozenset({"SEND_FOR_BACKGROUND_CHECK"}),
        constraints=("consent_required",), obligations=("notify_subject",))
    authz = ActionAuthorizationService(
        execution_platform.action_request_repo, constrained_cp,
        execution_platform.audit_service, execution_platform.identity_provider,
        execution_platform.evidence_access_policy)
    resp = authz.submit_for_authorization(request_id=req.action_request_id, actor=OPS)
    assert resp.outcome is AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS

    intent = execution_platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR)
    assert "consent_required" in intent.authorization_constraints
    assert "notify_subject" in intent.authorization_obligations


def test_parameter_expansion_is_rejected(execution_platform):
    req = authorized_request(execution_platform, params={"stage": "interview"})
    with pytest.raises(ExecutionParameterMismatchError):
        execution_platform.execution_service.create_execution_intent(
            action_request_id=req.action_request_id, created_by=EXECUTOR,
            execution_parameters={"stage": "interview", "extra": "unauthorized"})


def test_parameter_value_change_is_rejected(execution_platform):
    req = authorized_request(execution_platform, params={"stage": "interview"})
    with pytest.raises(ExecutionParameterMismatchError):
        execution_platform.execution_service.create_execution_intent(
            action_request_id=req.action_request_id, created_by=EXECUTOR,
            execution_parameters={"stage": "DIFFERENT"})


def test_exact_request_version_is_pinned(execution_platform):
    req = authorized_request(execution_platform)
    intent = execution_platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR)
    assert intent.action_request_version == req.version


def _authorized_with_clocks(platform, *, authz_validity, cer_validity, anchor):
    """Wire 4B with fixed-clock binder/authz so authz and CER expiries differ."""
    from ai_hiring.action_requests import OfflineDeterministicControlPlane
    from ai_hiring.services.action_authorization_service import ActionAuthorizationService
    from ai_hiring.services.cer_binding_service import CERBindingService

    _, decision = decided_case(platform)
    published_mapping(platform)
    req = platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})
    platform.action_request_service.validate_action_request(
        request_id=req.action_request_id, actor=OPS)
    binder = CERBindingService(
        platform.action_request_repo, platform.decision_case_repo,
        platform.audit_service, platform.identity_provider,
        platform.evidence_access_policy, default_validity=cer_validity,
        clock=lambda: anchor)
    binder.bind_cer(request_id=req.action_request_id, actor=OPS)
    cp = OfflineDeterministicControlPlane(validity=authz_validity, clock=lambda: anchor)
    authz = ActionAuthorizationService(
        platform.action_request_repo, cp, platform.audit_service,
        platform.identity_provider, platform.evidence_access_policy,
        clock=lambda: anchor)
    authz.submit_for_authorization(request_id=req.action_request_id, actor=OPS)
    return req


def test_expired_authorization_blocks_execution(execution_platform):
    """Authorization valid at submit time but expired later blocks intent creation."""
    from ai_hiring.services.execution_service import ExecutionService
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 1, 1, 18, 0, 0, tzinfo=timezone.utc)
    # Short authorization validity, long CER validity → only authz expires.
    req = _authorized_with_clocks(
        execution_platform, authz_validity=timedelta(minutes=1),
        cer_validity=timedelta(days=365), anchor=t0)
    late_exec = ExecutionService(
        execution_platform.execution_repo, execution_platform.action_request_repo,
        execution_platform.execution_validation_service,
        execution_platform.external_execution_adapter, execution_platform.audit_service,
        execution_platform.identity_provider, execution_platform.evidence_access_policy,
        clock=lambda: t_late)
    with pytest.raises(AuthorizationExpiredError):
        late_exec.create_execution_intent(
            action_request_id=req.action_request_id, created_by=EXECUTOR)


def test_expired_cer_blocks_execution(execution_platform):
    """CER valid at submit time but expired later blocks intent creation."""
    from ai_hiring.services.execution_service import ExecutionService
    t0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    t_late = datetime(2026, 1, 1, 18, 0, 0, tzinfo=timezone.utc)
    # Long authorization validity, short CER validity → only the CER expires.
    req = _authorized_with_clocks(
        execution_platform, authz_validity=timedelta(days=365),
        cer_validity=timedelta(minutes=1), anchor=t0)
    late_exec = ExecutionService(
        execution_platform.execution_repo, execution_platform.action_request_repo,
        execution_platform.execution_validation_service,
        execution_platform.external_execution_adapter, execution_platform.audit_service,
        execution_platform.identity_provider, execution_platform.evidence_access_policy,
        clock=lambda: t_late)
    with pytest.raises(CERExpiredForExecutionError):
        late_exec.create_execution_intent(
            action_request_id=req.action_request_id, created_by=EXECUTOR)


def test_cross_tenant_intent_creation_is_denied(execution_platform):
    """An actor granted only in another tenant cannot execute a t1 request."""
    from ai_hiring.errors import ExecutionAuthorizationError
    from ai_hiring.policies.evidence_access_policy import AccessGrant, Permission
    execution_platform.access_grants.add(
        AccessGrant("exec-2", "t2", frozenset(Permission)))
    req = authorized_request(execution_platform)  # tenant t1
    with pytest.raises(ExecutionAuthorizationError):
        execution_platform.execution_service.create_execution_intent(
            action_request_id=req.action_request_id, created_by="exec-2")
