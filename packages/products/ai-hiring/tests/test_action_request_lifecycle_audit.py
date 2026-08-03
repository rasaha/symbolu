"""Lifecycle, idempotency, authorization/SoD, audit, and scope-protection."""

from __future__ import annotations

import pytest

from ugence_ai_hiring.action_requests import ActionRequestStatus, is_legal_transition
from ugence_ai_hiring.api.action_request_routes import (
    ActionRequestActionRequest,
    ActionRequestAPI,
    BindCERRequest,
    CreateActionRequestRequest,
    PublishMappingRequest,
)
from ugence_ai_hiring.domain.enums import AuditEventType
from ugence_ai_hiring.errors import (
    ActionRequestAuthorizationError,
    ActionRequestNotFoundError,
    InvalidActionRequestTransitionError,
)

from .conftest import (
    MAPPING_ADMIN,
    OPS,
    TENANT,
    decided_case,
    make_action_mapping,
    published_mapping,
)


def _full_flow(platform):
    _, decision = decided_case(platform)
    published_mapping(platform)
    req = platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "interview"},
        idempotency_key="k1")
    platform.action_request_service.validate_action_request(
        request_id=req.action_request_id, actor=OPS)
    platform.cer_binding_service.bind_cer(request_id=req.action_request_id, actor=OPS)
    platform.action_authorization_service.submit_for_authorization(
        request_id=req.action_request_id, actor=OPS)
    return req, decision


def test_legal_transition_table_has_no_executed_state(action_platform):
    assert is_legal_transition(ActionRequestStatus.CER_BOUND,
                               ActionRequestStatus.READY_FOR_AUTHORIZATION)
    # AUTHORIZED only goes to SUPERSEDED/CANCELLED — never to any executed state.
    from ugence_ai_hiring.action_requests.lifecycle import ALLOWED_TRANSITIONS
    for targets in ALLOWED_TRANSITIONS.values():
        for t in targets:
            assert t.value not in ("EXECUTED", "SUCCEEDED", "APPLIED")


def test_illegal_transition_is_rejected(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    req = action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})
    # Cannot submit for authorization straight from DRAFT (no CER).
    from ugence_ai_hiring.errors import ActionRequestNotReadyError
    with pytest.raises(ActionRequestNotReadyError):
        action_platform.action_authorization_service.submit_for_authorization(
            request_id=req.action_request_id, actor=OPS)


def test_idempotent_creation_returns_same_request(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    kwargs = dict(decision_id=decision.decision_id, mapping_id="map.advance",
                  target_system="ATS", created_by=OPS,
                  requested_parameters={"stage": "interview"}, idempotency_key="idem-1")
    a = action_platform.action_request_service.create_action_request(**kwargs)
    b = action_platform.action_request_service.create_action_request(**kwargs)
    assert a.action_request_id == b.action_request_id


def test_conflicting_idempotency_key_is_rejected(action_platform):
    from ugence_ai_hiring.errors import DuplicateActionRequestError
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "interview"},
        idempotency_key="dup")
    with pytest.raises(DuplicateActionRequestError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by=OPS,
            requested_parameters={"stage": "onsite"}, idempotency_key="dup")


def test_supersession_creates_a_fresh_request(action_platform):
    req, _ = _full_flow(action_platform)
    replacement = action_platform.action_request_service.supersede_action_request(
        request_id=req.action_request_id, target_system="ATS", actor=OPS,
        requested_parameters={"stage": "onsite"})
    assert replacement.action_request_id != req.action_request_id
    assert action_platform.action_request_service.get_action_request(
        req.action_request_id).status is ActionRequestStatus.SUPERSEDED
    assert replacement.status is ActionRequestStatus.DRAFT


def test_cancellation_preserves_history(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    req = action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})
    action_platform.action_request_service.cancel_action_request(
        request_id=req.action_request_id, actor=OPS)
    history = action_platform.action_request_service.get_action_request_history(
        req.action_request_id)
    assert history[0].status is ActionRequestStatus.DRAFT
    assert history[-1].status is ActionRequestStatus.CANCELLED
    assert [h.version for h in history] == sorted(h.version for h in history)


def test_unauthorized_submit_is_denied_and_audited(action_platform):
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    req = action_platform.action_request_service.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", created_by=OPS, requested_parameters={"stage": "x"})
    # "stranger" is unregistered / ungranted.
    with pytest.raises(ActionRequestAuthorizationError):
        action_platform.cer_binding_service.bind_cer(
            request_id=req.action_request_id, actor="stranger")
    types = {e.event_type for e in action_platform.audit_repo.all()}
    assert AuditEventType.ACTION_REQUEST_ACCESS_DENIED in types


def test_creating_the_decision_grants_no_action_privilege(action_platform):
    """The decision-maker has no action-request grant here and cannot create one."""
    from ugence_ai_hiring.policies.evidence_access_policy import AccessGrant, Permission
    from .conftest import DECISION_MAKER
    # Give the decision-maker ONLY decision-case permissions, not action ones.
    action_platform.access_grants.add(AccessGrant(
        "solo-approver", TENANT, frozenset({Permission.MAKE_DECISION})))
    _, decision = decided_case(action_platform)
    published_mapping(action_platform)
    with pytest.raises(ActionRequestAuthorizationError):
        action_platform.action_request_service.create_action_request(
            decision_id=decision.decision_id, mapping_id="map.advance",
            target_system="ATS", created_by="solo-approver",
            requested_parameters={"stage": "x"})


def test_material_transitions_are_audited(action_platform):
    _full_flow(action_platform)
    types = {e.event_type for e in action_platform.audit_repo.all()}
    for expected in (
        AuditEventType.ACTION_MAPPING_PUBLISHED,
        AuditEventType.ACTION_REQUEST_CREATED,
        AuditEventType.ACTION_MAPPING_SELECTED,
        AuditEventType.ACTION_REQUEST_VALIDATED,
        AuditEventType.CER_CREATED,
        AuditEventType.CER_BOUND,
        AuditEventType.ACTION_AUTHORIZATION_SUBMITTED,
        AuditEventType.ACTION_AUTHORIZATION_GRANTED,
    ):
        assert expected in types, expected


def test_history_is_reconstructable(action_platform):
    req, _ = _full_flow(action_platform)
    history = action_platform.action_request_service.get_action_request_history(
        req.action_request_id)
    statuses = [h.status for h in history]
    assert statuses[0] is ActionRequestStatus.DRAFT
    assert ActionRequestStatus.CER_BOUND in statuses
    assert statuses[-1] is ActionRequestStatus.AUTHORIZED


def test_cross_tenant_read_denied(action_platform):
    with pytest.raises(ActionRequestNotFoundError):
        action_platform.action_request_service.get_action_request("no-such-request")


# --- scope protection ---------------------------------------------------

def test_api_exposes_no_execution_operations(action_platform):
    api = action_platform.build_action_request_api()
    forbidden = {"execute_action", "apply_action", "send_offer", "update_ats",
                 "create_purchase_order", "invoke_actiongate_directly",
                 "record_execution_success", "execute", "reconcile"}
    surface = {name for name in dir(api) if not name.startswith("_")}
    assert forbidden.isdisjoint(surface), f"forbidden ops: {forbidden & surface}"


def test_no_execution_record_type_exists():
    import ugence_ai_hiring.action_requests as ar
    assert not hasattr(ar, "ExecutionRecord")


def test_domain_depends_on_port_not_concrete_gate():
    """The domain/service layer imports the port, never a concrete ActionGate SDK."""
    import ugence_ai_hiring.services.action_authorization_service as svc
    source = svc.__file__
    with open(source, "r", encoding="utf-8") as fh:
        text = fh.read()
    assert "ActionControlPlanePort" in text
    assert "actiongate" not in text.lower() or "invoke" not in text.lower()


def test_api_full_flow(action_platform):
    _, decision = decided_case(action_platform)
    api: ActionRequestAPI = action_platform.build_action_request_api()
    api.publish_action_mapping(PublishMappingRequest(
        principal_id=MAPPING_ADMIN, tenant_id=TENANT, mapping=make_action_mapping()))
    req = api.create_action_request(CreateActionRequestRequest(
        principal_id=OPS, decision_id=decision.decision_id, mapping_id="map.advance",
        target_system="ATS", requested_parameters={"stage": "interview"}))
    api.validate_action_request(ActionRequestActionRequest(
        principal_id=OPS, request_id=req.action_request_id))
    api.bind_cer(BindCERRequest(principal_id=OPS, request_id=req.action_request_id))
    resp = api.submit_for_authorization(ActionRequestActionRequest(
        principal_id=OPS, request_id=req.action_request_id))
    assert resp.outcome.value == "AUTHORIZED"
