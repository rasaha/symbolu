"""Kernel-lifecycle integration helper (shared by the integration tests).

Drives the full Decision Authority kernel governance chain through a provider-backed
control plane and linked-record adapter. Extracted verbatim from the pre-migration
``governance_providers/tests/conftest.py`` (no behaviour change); relocated to an
importable module so the subdivided test tree can share it.
"""

from __future__ import annotations


def run_kernel_action_lifecycle(*, control_plane, linked_record):
    """Drive the full kernel governance chain with a provider-backed control plane
    and linked-record adapter; return (reconciliation_status, emitted_events)."""
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

    t, actor, subject = "t", "gov", "subject"
    idp = StaticIdentityProvider(); idp.register_human(actor)
    grants = GrantStore(); grants.add(AccessGrant(actor, t, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants); audit = AuditService(InMemoryAuditRepository())
    cr, ar, er = (InMemoryDecisionCaseRepository(), InMemoryActionRequestRepository(),
                  InMemoryExecutionRepository())
    val = CaseValidationService(linked_record)
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
        return resp.outcome.value, set(), resp
    intent = exe.create_execution_intent(action_request_id=req.action_request_id, created_by=actor)
    exe.dispatch_execution(intent_id=intent.execution_intent_id, actor=actor)
    rec.query_external_status(intent_id=intent.execution_intent_id, actor=actor)
    result = rec.reconcile_execution(intent_id=intent.execution_intent_id, actor=actor)
    return result.status.value, {e.event_type for e in audit._repo.all()}, resp
