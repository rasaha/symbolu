"""Cross-domain conformance: hiring and procurement on one unchanged kernel.

Proves the central Phase-5D claim: two materially different enterprise workflows
(AI hiring and procurement) execute the *same* governance lifecycle through the
*identical* kernel service classes. The domains differ only in the adapters they
plug into the kernel ports — never in the governance engine.
"""

from __future__ import annotations

import applications.ai_hiring as hiring_app
import applications.procurement as procurement_app
from applications.procurement.api import ProcurementAPI

from decision_governance.audit import AuditNamespace, audit_namespace

from domains.procurement.policies import BudgetAuthorityAdapter
from domains.procurement.suppliers import SupplierExecutionAdapter

from .conftest import APPROVER, REQUESTER, build_platform, make_request

# The governance services both composition roots wire.
_GOVERNANCE_SERVICES = (
    "decision_case_service", "case_recommendation_service", "case_decision_service",
    "case_validation_service", "action_request_service",
    "action_request_validation_service", "cer_binding_service",
    "action_authorization_service", "execution_service",
    "execution_validation_service", "reconciliation_service", "compensation_service",
)


def test_both_platforms_wire_identical_kernel_service_classes():
    hiring = hiring_app.build_in_memory_platform()
    procurement = procurement_app.build_in_memory_platform()
    for attr in _GOVERNANCE_SERVICES:
        h = type(getattr(hiring, attr))
        p = type(getattr(procurement, attr))
        assert h is p, f"{attr}: hiring={h!r} procurement={p!r}"
        assert h.__module__.startswith(("ugence_decision_authority.", "decision_governance.")), attr


def test_both_platforms_reuse_the_kernel_audit_service():
    hiring = hiring_app.build_in_memory_platform()
    procurement = procurement_app.build_in_memory_platform()
    assert type(hiring.audit_service) is type(procurement.audit_service)
    assert type(hiring.audit_service).__module__.startswith(("ugence_decision_authority.", "decision_governance."))


def test_domains_supply_only_adapters_not_engines():
    """The domain contributes port *adapters*; the engine stays in the kernel."""
    procurement = procurement_app.build_in_memory_platform()
    # Control plane + execution adapters are procurement-owned…
    assert isinstance(procurement.budget_authority, BudgetAuthorityAdapter)
    assert isinstance(procurement.supplier_adapter, SupplierExecutionAdapter)
    assert type(procurement.budget_authority).__module__.startswith(
        ("ugence_procurement.", "domains.procurement."))
    assert type(procurement.supplier_adapter).__module__.startswith(
        ("ugence_procurement.", "domains.procurement."))
    # …but the authorization/execution *services* are kernel-owned.
    assert type(procurement.action_authorization_service).__module__.startswith(
        ("ugence_decision_authority.", "decision_governance."))
    assert type(procurement.execution_service).__module__.startswith(("ugence_decision_authority.", "decision_governance."))


def test_procurement_executes_the_shared_governance_lifecycle():
    platform = build_platform()
    api = ProcurementAPI(platform)
    result = api.run(request=make_request(), requester=REQUESTER, approver=APPROVER)
    assert result.reconciliation_status == "RECONCILED"
    # Same governance vocabulary as hiring: only KERNEL-namespace audit events.
    emitted = {e.event_type for e in platform.audit_service._repo.all()}
    assert emitted
    assert all(audit_namespace(e) is AuditNamespace.KERNEL for e in emitted)


def test_neutral_shared_pipeline_matches_both_domains():
    """The kernel governance chain runs standalone (no hiring, no procurement
    imports) to RECONCILED — the pipeline both domains share."""
    from decision_governance.audit import AuditService, InMemoryAuditRepository
    from decision_governance.identity import StaticIdentityProvider
    from decision_governance.policy import (
        AccessGrant, EvidenceAccessPolicy, GrantStore, Permission)
    from decision_governance.ports.linked_record import FINALIZED_STATUS, LinkedRecordSnapshot
    from decision_governance.repositories import (
        InMemoryActionRequestRepository, InMemoryDecisionCaseRepository,
        InMemoryExecutionRepository)
    from decision_governance.services import (
        ActionAuthorizationService, ActionRequestService,
        ActionRequestValidationService, CaseValidationService, CERBindingService,
        DecisionCaseService, ExecutionService, ExecutionValidationService,
        ReconciliationService)
    from decision_governance.services.case_decision_service import CaseDecisionService
    from decision_governance.decisions import AuthorityContext, AuthorityType, DecisionOutcome
    from decision_governance.actions import (
        ActionMapping, OfflineDeterministicControlPlane, ParameterSchema)
    from decision_governance.execution import (
        BusinessOutcome, Finality, OfflineDeterministicExecutionAdapter, OutcomeSource,
        ReconciliationStatus)
    from decision_governance.vocabulary import ReasonCode

    tenant, subject, actor = "t", "s", "gov"
    idp = StaticIdentityProvider(); idp.register_human(actor)
    grants = GrantStore(); grants.add(AccessGrant(actor, tenant, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants)
    audit = AuditService(InMemoryAuditRepository())
    case_repo, ar_repo, ex_repo = (
        InMemoryDecisionCaseRepository(), InMemoryActionRequestRepository(),
        InMemoryExecutionRepository())

    class _Linked:
        def get_record(self, *, tenant_id, record_type, record_id, version=None):
            return LinkedRecordSnapshot(
                record_type=record_type, record_id=record_id, version=version or 1,
                tenant_id=tenant, status=FINALIZED_STATUS, subject_ref=subject)

    validation = CaseValidationService(_Linked())
    cases = DecisionCaseService(case_repo, validation, audit, idp, policy)
    decisions = CaseDecisionService(case_repo, validation, audit, idp, policy)
    actions = ActionRequestService(
        ar_repo, case_repo, ActionRequestValidationService(ar_repo, case_repo),
        audit, idp, policy)
    cer = CERBindingService(ar_repo, case_repo, audit, idp, policy)
    authz = ActionAuthorizationService(
        ar_repo, OfflineDeterministicControlPlane(), audit, idp, policy)
    adapter = OfflineDeterministicExecutionAdapter()
    execs = ExecutionService(
        ex_repo, ar_repo, ExecutionValidationService(ex_repo, ar_repo), adapter,
        audit, idp, policy)
    recon = ReconciliationService(ex_repo, adapter, audit, idp, policy)

    case = cases.create_case(tenant_id=tenant, decision_type="approve",
                             subject_ids=(subject,), created_by=actor)
    cases.link_assessment(case_id=case.decision_case_id, assessment_id="a1",
                          version=1, actor=actor)
    decision = decisions.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=AuthorityContext(authority_id=actor,
                                   authority_type=AuthorityType.HUMAN_APPROVER,
                                   decision_scope="approve"),
        decided_by=actor, reason_codes=(ReasonCode.NOT_APPLICABLE,))
    actions.publish_action_mapping(ActionMapping(
        mapping_id="m", version=1, domain_id="generic", decision_type="approve",
        decision_outcome=DecisionOutcome.ADVANCE, permitted_action_type="ACT",
        target_system_type="SYS",
        parameter_schema=ParameterSchema(required_fields=("k",))), actor=actor, tenant_id=tenant)
    req = actions.create_action_request(
        decision_id=decision.decision_id, mapping_id="m", target_system="SYS",
        created_by=actor, requested_parameters={"k": "v"})
    actions.validate_action_request(request_id=req.action_request_id, actor=actor)
    cer.bind_cer(request_id=req.action_request_id, actor=actor)
    authz.submit_for_authorization(request_id=req.action_request_id, actor=actor)
    intent = execs.create_execution_intent(
        action_request_id=req.action_request_id, created_by=actor)
    execs.dispatch_execution(intent_id=intent.execution_intent_id, actor=actor)
    recon.record_external_outcome(
        intent_id=intent.execution_intent_id, actor=actor,
        business_outcome=BusinessOutcome.SUCCEEDED, observed_parameters={"k": "v"},
        finality=Finality.FINAL, source=OutcomeSource.EXTERNAL_CALLBACK)
    result = recon.reconcile_execution(intent_id=intent.execution_intent_id, actor=actor)
    assert result.status is ReconciliationStatus.RECONCILED
