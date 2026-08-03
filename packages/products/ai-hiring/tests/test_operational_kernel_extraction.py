"""Phase 5B operational extraction guarantees.

Proves the operational kernel (services, repositories, audit, identity, policy)
runs the full governance lifecycle standalone — with no hiring imports — and that
the legacy ``ugence_ai_hiring.*`` paths resolve to the identical kernel objects.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Optional

import pytest

from ugence_decision_authority.ports.linked_record import (
    FINALIZED_STATUS,
    LinkedRecordSnapshot,
)


# --- compatibility identity -------------------------------------------------

def test_service_classes_are_object_identical():
    from ugence_ai_hiring.services import (
        ExecutionService as OldExec, DecisionCaseService as OldCase,
        ReconciliationService as OldRec, CompensationService as OldComp)
    from ugence_decision_authority.services import (
        ExecutionService as NewExec, DecisionCaseService as NewCase,
        ReconciliationService as NewRec, CompensationService as NewComp)
    assert OldExec is NewExec
    assert OldCase is NewCase
    assert OldRec is NewRec
    assert OldComp is NewComp


def test_repository_classes_are_object_identical():
    from ugence_ai_hiring.repositories import (
        InMemoryDecisionCaseRepository as OldD,
        InMemoryActionRequestRepository as OldA,
        InMemoryExecutionRepository as OldE)
    from ugence_decision_authority.repositories import (
        InMemoryDecisionCaseRepository as NewD,
        InMemoryActionRequestRepository as NewA,
        InMemoryExecutionRepository as NewE)
    assert OldD is NewD and OldA is NewA and OldE is NewE


def test_audit_identity_policy_are_object_identical():
    from ugence_ai_hiring.services.audit_service import AuditService as OldAudit
    from ugence_ai_hiring.domain.enums import AuditEventType as OldEv, ActorType as OldAct
    from ugence_ai_hiring.policies.evidence_access_policy import Permission as OldPerm
    from ugence_ai_hiring.policies.decision_boundary import IdentityProvider as OldIdp
    from ugence_decision_authority.audit import AuditService as NewAudit, AuditEventType as NewEv
    from ugence_decision_authority.identity import ActorType as NewAct, IdentityProvider as NewIdp
    from ugence_decision_authority.policy import Permission as NewPerm
    assert OldAudit is NewAudit
    assert OldEv is NewEv and OldAct is NewAct
    assert OldPerm is NewPerm and OldIdp is NewIdp


def test_typed_errors_are_object_identical():
    from ugence_ai_hiring.errors import (
        ExecutionError as OldE, DecisionCaseError as OldD, VersionConflictError as OldV)
    from ugence_decision_authority.errors import (
        ExecutionError as NewE, DecisionCaseError as NewD, VersionConflictError as NewV)
    assert OldE is NewE and OldD is NewD and OldV is NewV


# --- kernel independence ----------------------------------------------------

def test_operational_kernel_imports_without_the_application():
    code = (
        "import ugence_decision_authority.services, ugence_decision_authority.repositories, "
        "ugence_decision_authority.audit, ugence_decision_authority.identity, "
        "ugence_decision_authority.policy, sys; "
        "bad=[m for m in sys.modules if m.startswith(('ugence_ai_hiring','domains','applications'))]; "
        "assert not bad, bad; print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


# --- full neutral lifecycle -------------------------------------------------

class _NeutralLinkedRecords:
    """A neutral LinkedRecordPort adapter (no hiring types) for the lifecycle test."""

    def __init__(self, tenant_id: str, subject_id: str) -> None:
        self._tenant, self._subject = tenant_id, subject_id

    def get_record(self, *, tenant_id, record_type, record_id, version=None
                   ) -> Optional[LinkedRecordSnapshot]:
        return LinkedRecordSnapshot(
            record_type=record_type, record_id=record_id, version=version or 1,
            tenant_id=self._tenant, status=FINALIZED_STATUS, subject_ref=self._subject)


def test_full_governance_lifecycle_runs_without_the_hiring_domain():
    # Everything imported here is kernel-only — no ugence_ai_hiring, no domains.hiring.
    from ugence_decision_authority.audit import AuditService, InMemoryAuditRepository
    from ugence_decision_authority.identity import StaticIdentityProvider
    from ugence_decision_authority.policy import AccessGrant, EvidenceAccessPolicy, GrantStore, Permission
    from ugence_decision_authority.repositories import (
        InMemoryActionRequestRepository, InMemoryDecisionCaseRepository,
        InMemoryExecutionRepository)
    from ugence_decision_authority.services import (
        ActionAuthorizationService, ActionRequestService,
        ActionRequestValidationService, CaseValidationService, CERBindingService,
        CompensationService, DecisionCaseService, ExecutionService,
        ExecutionValidationService, ReconciliationService)
    from ugence_decision_authority.decisions import AuthorityContext, AuthorityType, DecisionOutcome
    from ugence_decision_authority.actions import (
        ActionMapping, OfflineDeterministicControlPlane, ParameterSchema)
    from ugence_decision_authority.execution import (
        BusinessOutcome, Finality, OfflineDeterministicExecutionAdapter, OutcomeSource,
        ReconciliationStatus)
    from ugence_decision_authority.vocabulary import ReasonCode

    tenant, subject, actor = "t1", "subj-1", "gov-1"
    idp = StaticIdentityProvider()
    idp.register_human(actor)
    grants = GrantStore()
    grants.add(AccessGrant(actor, tenant, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants)
    audit = AuditService(InMemoryAuditRepository())

    case_repo = InMemoryDecisionCaseRepository()
    ar_repo = InMemoryActionRequestRepository()
    ex_repo = InMemoryExecutionRepository()
    linked = _NeutralLinkedRecords(tenant, subject)

    validation = CaseValidationService(linked)
    cases = DecisionCaseService(case_repo, validation, audit, idp, policy)
    ar_validation = ActionRequestValidationService(ar_repo, case_repo)
    actions = ActionRequestService(ar_repo, case_repo, ar_validation, audit, idp, policy)
    cer = CERBindingService(ar_repo, case_repo, audit, idp, policy)
    authz = ActionAuthorizationService(
        ar_repo, OfflineDeterministicControlPlane(), audit, idp, policy)
    ex_validation = ExecutionValidationService(ex_repo, ar_repo)
    adapter = OfflineDeterministicExecutionAdapter()
    execs = ExecutionService(ex_repo, ar_repo, ex_validation, adapter, audit, idp, policy)
    recon = ReconciliationService(ex_repo, adapter, audit, idp, policy)
    comp = CompensationService(ex_repo, audit, idp, policy)  # noqa: F841

    # DecisionCase -> link record -> Decision
    case = cases.create_case(tenant_id=tenant, decision_type="approve",
                             subject_ids=(subject,), created_by=actor)
    cases.link_assessment(case_id=case.decision_case_id, assessment_id="rec-1",
                          version=1, actor=actor)
    decision = None
    from ugence_decision_authority.services.case_decision_service import CaseDecisionService
    decisions = CaseDecisionService(case_repo, validation, audit, idp, policy)
    authority = AuthorityContext(authority_id=actor,
                                 authority_type=AuthorityType.HUMAN_APPROVER,
                                 decision_scope="approve")
    decision = decisions.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=authority, decided_by=actor, reason_codes=(ReasonCode.NOT_APPLICABLE,))

    # ActionRequest -> CER -> Authorization
    mapping = ActionMapping(
        mapping_id="map.adv", version=1, domain_id="generic", decision_type="approve",
        decision_outcome=DecisionOutcome.ADVANCE, permitted_action_type="ADVANCE_STAGE",
        target_system_type="SYS", parameter_schema=ParameterSchema(required_fields=("stage",)))
    actions.publish_action_mapping(mapping, actor=actor, tenant_id=tenant)
    req = actions.create_action_request(
        decision_id=decision.decision_id, mapping_id="map.adv", target_system="SYS",
        created_by=actor, requested_parameters={"stage": "next"})
    actions.validate_action_request(request_id=req.action_request_id, actor=actor)
    cer.bind_cer(request_id=req.action_request_id, actor=actor)
    resp = authz.submit_for_authorization(request_id=req.action_request_id, actor=actor)
    assert resp.outcome.value == "AUTHORIZED"

    # Execution -> observation -> Reconciliation
    intent = execs.create_execution_intent(
        action_request_id=req.action_request_id, created_by=actor)
    execs.dispatch_execution(intent_id=intent.execution_intent_id, actor=actor)
    recon.record_external_outcome(
        intent_id=intent.execution_intent_id, actor=actor,
        business_outcome=BusinessOutcome.SUCCEEDED,
        observed_parameters={"stage": "next"}, finality=Finality.FINAL,
        source=OutcomeSource.EXTERNAL_CALLBACK)
    result = recon.reconcile_execution(intent_id=intent.execution_intent_id, actor=actor)
    assert result.status is ReconciliationStatus.RECONCILED

    # The whole chain ran on kernel objects; the audit log captured it.
    from ugence_decision_authority.audit import AuditEventType
    types = {e.event_type for e in audit._repo.all()}
    assert AuditEventType.DECISION_CASE_CREATED in types
    assert AuditEventType.DECISION_RECORDED in types
    assert AuditEventType.EXECUTION_RECONCILED in types
