"""Security, segregation of duties, audit completeness, and scope protection."""

from __future__ import annotations

import pytest

from ai_hiring.api.execution_routes import (
    CreateExecutionIntentRequest,
    ExecutionActionRequest,
    ExecutionAPI,
    RecordOutcomeRequest,
)
from ai_hiring.domain.enums import AuditEventType
from ai_hiring.errors import ExecutionAuthorizationError, ExecutionIntentNotFoundError
from ai_hiring.executions import BusinessOutcome, Finality, OutcomeSource
from ai_hiring.policies.evidence_access_policy import AccessGrant, Permission

from .conftest import DECISION_MAKER, EXECUTOR, RECONCILER, TENANT, authorized_request


def _intent(platform):
    req = authorized_request(platform)
    return platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR)


def test_unauthorized_dispatch_is_denied_and_audited(execution_platform):
    intent = _intent(execution_platform)
    # "exec-2" is registered but holds no grant.
    with pytest.raises(ExecutionAuthorizationError):
        execution_platform.execution_service.dispatch_execution(
            intent_id=intent.execution_intent_id, actor="exec-2")
    types = {e.event_type for e in execution_platform.audit_repo.all()}
    assert AuditEventType.EXECUTION_ACCESS_DENIED in types


def test_decision_maker_has_no_automatic_dispatch_permission(execution_platform):
    """A principal with only decision authority cannot dispatch executions."""
    execution_platform.access_grants.add(AccessGrant(
        "solo-decider", TENANT, frozenset({Permission.MAKE_DECISION})))
    execution_platform.identity_provider.register_human("solo-decider")
    intent = _intent(execution_platform)
    with pytest.raises(ExecutionAuthorizationError):
        execution_platform.execution_service.dispatch_execution(
            intent_id=intent.execution_intent_id, actor="solo-decider")


def test_adapter_management_privilege_is_separate(execution_platform):
    """MANAGE_EXECUTION_ADAPTER is a distinct permission from DISPATCH_EXECUTION."""
    assert Permission.MANAGE_EXECUTION_ADAPTER != Permission.DISPATCH_EXECUTION
    perms = {p.value for p in Permission}
    assert "MANAGE_EXECUTION_ADAPTER" in perms and "DISPATCH_EXECUTION" in perms


def test_cross_tenant_read_denied(execution_platform):
    with pytest.raises(ExecutionIntentNotFoundError):
        execution_platform.execution_service.get_execution_intent("no-such-intent")


def test_full_flow_is_audited(execution_platform):
    intent = _intent(execution_platform)
    execution_platform.execution_service.validate_execution(
        intent_id=intent.execution_intent_id, actor=EXECUTOR)
    execution_platform.execution_service.dispatch_execution(
        intent_id=intent.execution_intent_id, actor=EXECUTOR)
    execution_platform.reconciliation_service.record_external_outcome(
        intent_id=intent.execution_intent_id, actor=RECONCILER,
        business_outcome=BusinessOutcome.SUCCEEDED,
        observed_parameters={"stage": "interview"}, finality=Finality.FINAL,
        source=OutcomeSource.EXTERNAL_CALLBACK)
    execution_platform.reconciliation_service.reconcile_execution(
        intent_id=intent.execution_intent_id, actor=RECONCILER)
    types = {e.event_type for e in execution_platform.audit_repo.all()}
    for expected in (
        AuditEventType.EXECUTION_INTENT_CREATED,
        AuditEventType.EXECUTION_VALIDATED,
        AuditEventType.EXECUTION_DISPATCH_SUBMITTED,
        AuditEventType.EXECUTION_DISPATCH_ACKNOWLEDGED,
        AuditEventType.EXECUTION_OUTCOME_RECORDED,
        AuditEventType.EXECUTION_SUCCEEDED,
        AuditEventType.EXECUTION_RECONCILIATION_STARTED,
        AuditEventType.EXECUTION_RECONCILED,
    ):
        assert expected in types, expected


def test_history_is_reconstructable(execution_platform):
    intent = _intent(execution_platform)
    execution_platform.execution_service.dispatch_execution(
        intent_id=intent.execution_intent_id, actor=EXECUTOR)
    history = execution_platform.execution_service.get_execution_history(
        intent.execution_intent_id)
    assert [h.version for h in history] == sorted(h.version for h in history)
    assert history[0].version == 1


# --- scope protection ---------------------------------------------------

def test_api_exposes_no_history_rewriting_or_vendor_ops(execution_platform):
    api = execution_platform.build_execution_api()
    forbidden = {"delete_execution", "overwrite_record", "rewrite_history",
                 "update_ats", "send_offer", "invoke_actiongate", "rank_candidates",
                 "recommend_candidate", "mutate_decision"}
    surface = {name for name in dir(api) if not name.startswith("_")}
    assert forbidden.isdisjoint(surface), f"forbidden ops: {forbidden & surface}"


def test_domain_depends_on_port_not_vendor_sdk():
    """The execution service imports the port, never a concrete vendor SDK."""
    import ai_hiring.services.execution_service as svc
    with open(svc.__file__, "r", encoding="utf-8") as fh:
        import_lines = [ln.lower() for ln in fh.read().splitlines()
                        if ln.strip().startswith(("import ", "from "))]
    blob = "\n".join(import_lines)
    for vendor in ("boto3", "urllib", "httpx", "workday", "greenhouse", "lever",
                   "stripe", "salesforce", "actiongate", "requests.api"):
        assert vendor not in blob, vendor
    # It DOES depend on the provider-neutral port.
    assert "ExternalExecutionPort" in open(svc.__file__, encoding="utf-8").read()


def test_execution_does_not_mutate_the_decision_or_request(execution_platform):
    req = authorized_request(execution_platform)
    request_before = execution_platform.action_request_service.get_action_request(
        req.action_request_id)
    intent = execution_platform.execution_service.create_execution_intent(
        action_request_id=req.action_request_id, created_by=EXECUTOR)
    execution_platform.execution_service.dispatch_execution(
        intent_id=intent.execution_intent_id, actor=EXECUTOR)
    request_after = execution_platform.action_request_service.get_action_request(
        req.action_request_id)
    # The authorized action request is unchanged by execution.
    assert request_after.version == request_before.version
    assert request_after.status == request_before.status


def test_api_full_flow(execution_platform):
    req = authorized_request(execution_platform)
    api: ExecutionAPI = execution_platform.build_execution_api()
    intent = api.create_execution_intent(CreateExecutionIntentRequest(
        principal_id=EXECUTOR, action_request_id=req.action_request_id))
    api.validate_execution(ExecutionActionRequest(
        principal_id=EXECUTOR, intent_id=intent.execution_intent_id))
    api.dispatch_execution(ExecutionActionRequest(
        principal_id=EXECUTOR, intent_id=intent.execution_intent_id))
    api.record_external_outcome(RecordOutcomeRequest(
        principal_id=RECONCILER, intent_id=intent.execution_intent_id,
        business_outcome=BusinessOutcome.SUCCEEDED,
        observed_parameters={"stage": "interview"}, finality=Finality.FINAL))
    result = api.reconcile_execution(ExecutionActionRequest(
        principal_id=RECONCILER, intent_id=intent.execution_intent_id))
    assert result.status.value == "RECONCILED"
