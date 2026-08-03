"""Kernel lifecycle harness for ActionGate control-plane integration tests.

Drives the full Decision Authority governance lifecycle with an ActionGate-backed
``ActionControlPlanePort`` and reports whether authorization reached dispatch /
reconciliation. It requires the optional ``decision-authority`` dependency (the
kernel is reached through ``decision_governance.api`` / ``ugence_decision_authority``).
The harness itself imports NO ActionGate symbol — it only exercises a supplied
control plane — so it also proves ActionGate never dispatches or executes: for
DENIED / INDETERMINATE the lifecycle stops before dispatch.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class LifecycleResult:
    authorization_outcome: str
    reconciliation_status: Optional[str]
    dispatched: bool
    events: set


class _NeutralLinked:
    """A neutral finalized linked record so the case can reach a decision."""

    def get_record(self, *, tenant_id, record_type, record_id, version=None):
        from decision_governance.api.ports import FINALIZED_STATUS, LinkedRecordSnapshot
        return LinkedRecordSnapshot(
            record_type=record_type, record_id=record_id, version=version or 1,
            tenant_id="t", status=FINALIZED_STATUS, subject_ref="subject")


def run_actiongate_lifecycle(control_plane) -> LifecycleResult:
    """Drive the full lifecycle with ActionGate as the control plane.

    Stops at authorization when not authorized (proving no dispatch/execution/
    reconciliation happens for DENIED / INDETERMINATE).
    """
    from decision_governance.api.audit import AuditService, InMemoryAuditRepository
    from decision_governance.api.identity import StaticIdentityProvider
    from decision_governance.api.policy import (
        AccessGrant, EvidenceAccessPolicy, GrantStore, Permission)
    from decision_governance.api.repositories import (
        InMemoryActionRequestRepository, InMemoryDecisionCaseRepository,
        InMemoryExecutionRepository)
    from decision_governance.api.services import (
        ActionAuthorizationService, ActionRequestService, ActionRequestValidationService,
        CaseDecisionService, CaseValidationService, CERBindingService, DecisionCaseService,
        ExecutionService, ExecutionValidationService, ReconciliationService)
    from decision_governance.api.contracts import (
        ActionMapping, AuthorityContext, AuthorityType, DecisionOutcome, ParameterSchema)
    from decision_governance.api.ports import OfflineDeterministicExecutionAdapter
    from decision_governance.api.vocabulary import ReasonCode
    from decision_governance.errors import ActionRequestNotExecutableError

    t, actor, subject = "t", "gov", "subject"
    idp = StaticIdentityProvider(); idp.register_human(actor)
    grants = GrantStore(); grants.add(AccessGrant(actor, t, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants); audit = AuditService(InMemoryAuditRepository())
    cr, ar, er = (InMemoryDecisionCaseRepository(), InMemoryActionRequestRepository(),
                  InMemoryExecutionRepository())
    val = CaseValidationService(_NeutralLinked())
    cases = DecisionCaseService(cr, val, audit, idp, policy)
    dec = CaseDecisionService(cr, val, audit, idp, policy)
    acts = ActionRequestService(ar, cr, ActionRequestValidationService(ar, cr), audit, idp, policy)
    cer = CERBindingService(ar, cr, audit, idp, policy)
    authz = ActionAuthorizationService(ar, control_plane, audit, idp, policy)
    ex_adapter = OfflineDeterministicExecutionAdapter()
    exe = ExecutionService(er, ar, ExecutionValidationService(er, ar), ex_adapter, audit, idp, policy)
    rec = ReconciliationService(er, ex_adapter, audit, idp, policy)

    case = cases.create_case(tenant_id=t, decision_type="approve", subject_ids=(subject,), created_by=actor)
    cases.link_assessment(case_id=case.decision_case_id, assessment_id="a1", version=1, actor=actor)
    decision = dec.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=AuthorityContext(authority_id=actor, authority_type=AuthorityType.HUMAN_APPROVER,
                                   decision_scope="approve"),
        decided_by=actor, reason_codes=(ReasonCode.NOT_APPLICABLE,))
    acts.publish_action_mapping(
        ActionMapping(mapping_id="m", version=1, domain_id="generic", decision_type="approve",
                      decision_outcome=DecisionOutcome.ADVANCE, permitted_action_type="ACT",
                      target_system_type="SYS", parameter_schema=ParameterSchema(required_fields=("k",))),
        actor=actor, tenant_id=t)
    req = acts.create_action_request(decision_id=decision.decision_id, mapping_id="m",
        target_system="SYS", created_by=actor, requested_parameters={"k": "v"})
    acts.validate_action_request(request_id=req.action_request_id, actor=actor)
    cer.bind_cer(request_id=req.action_request_id, actor=actor)
    resp = authz.submit_for_authorization(request_id=req.action_request_id, actor=actor)

    if resp.outcome.value not in ("AUTHORIZED", "AUTHORIZED_WITH_CONSTRAINTS"):
        try:
            exe.create_execution_intent(action_request_id=req.action_request_id, created_by=actor)
            dispatched = True
        except ActionRequestNotExecutableError:
            dispatched = False
        return LifecycleResult(resp.outcome.value, None, dispatched,
                               {e.event_type for e in audit._repo.all()})

    intent = exe.create_execution_intent(action_request_id=req.action_request_id, created_by=actor)
    exe.dispatch_execution(intent_id=intent.execution_intent_id, actor=actor)
    rec.query_external_status(intent_id=intent.execution_intent_id, actor=actor)
    result = rec.reconcile_execution(intent_id=intent.execution_intent_id, actor=actor)
    return LifecycleResult(resp.outcome.value, result.status.value, True,
                           {e.event_type for e in audit._repo.all()})
