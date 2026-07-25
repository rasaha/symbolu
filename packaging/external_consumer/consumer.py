"""A third-party consumer that depends only on decision-governance's public API.

Imports exclusively from ``decision_governance.api`` (plus the frozen
``vocabulary`` reason codes), wires neutral kernel services, runs one governance
lifecycle to reconciliation, serializes a record, and validates the audit log.
Used by ``verify_independent_distribution.py`` inside an isolated virtual
environment where only ``decision-governance`` (and its declared deps) are
installed.
"""

from __future__ import annotations

from decision_governance.api.audit import (
    AuditEventType,
    AuditService,
    InMemoryAuditRepository,
)
from decision_governance.api.contracts import (
    ActionMapping,
    AuthorityContext,
    AuthorityType,
    DecisionOutcome,
    ParameterSchema,
    ReconciliationStatus,
)
from decision_governance.api.identity import StaticIdentityProvider
from decision_governance.api.policy import (
    AccessGrant,
    EvidenceAccessPolicy,
    GrantStore,
    Permission,
)
from decision_governance.api.ports import (
    FINALIZED_STATUS,
    LinkedRecordSnapshot,
    OfflineDeterministicControlPlane,
    OfflineDeterministicExecutionAdapter,
)
from decision_governance.api.repositories import (
    InMemoryActionRequestRepository,
    InMemoryDecisionCaseRepository,
    InMemoryExecutionRepository,
)
from decision_governance.api.services import (
    ActionAuthorizationService,
    ActionRequestService,
    ActionRequestValidationService,
    CaseDecisionService,
    CaseValidationService,
    CERBindingService,
    DecisionCaseService,
    ExecutionService,
    ExecutionValidationService,
    ReconciliationService,
)
from decision_governance.api.vocabulary import ReasonCode


class _Linked:
    def get_record(self, *, tenant_id, record_type, record_id, version=None):
        return LinkedRecordSnapshot(
            record_type=record_type, record_id=record_id, version=version or 1,
            tenant_id="t", status=FINALIZED_STATUS, subject_ref="s")


def run() -> str:
    t, actor = "t", "gov"
    idp = StaticIdentityProvider(); idp.register_human(actor)
    grants = GrantStore(); grants.add(AccessGrant(actor, t, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants)
    audit = AuditService(InMemoryAuditRepository())
    cr = InMemoryDecisionCaseRepository()
    ar = InMemoryActionRequestRepository()
    er = InMemoryExecutionRepository()
    val = CaseValidationService(_Linked())
    cases = DecisionCaseService(cr, val, audit, idp, policy)
    dec = CaseDecisionService(cr, val, audit, idp, policy)
    acts = ActionRequestService(ar, cr, ActionRequestValidationService(ar, cr), audit, idp, policy)
    cer = CERBindingService(ar, cr, audit, idp, policy)
    authz = ActionAuthorizationService(ar, OfflineDeterministicControlPlane(), audit, idp, policy)
    adapter = OfflineDeterministicExecutionAdapter()
    exe = ExecutionService(er, ar, ExecutionValidationService(er, ar), adapter, audit, idp, policy)
    rec = ReconciliationService(er, adapter, audit, idp, policy)

    case = cases.create_case(tenant_id=t, decision_type="approve",
                             subject_ids=("s",), created_by=actor)
    cases.link_assessment(case_id=case.decision_case_id, assessment_id="a",
                          version=1, actor=actor)
    decision = dec.record_decision(
        case_id=case.decision_case_id, outcome=DecisionOutcome.ADVANCE,
        authority=AuthorityContext(authority_id=actor,
                                   authority_type=AuthorityType.HUMAN_APPROVER,
                                   decision_scope="approve"),
        decided_by=actor, reason_codes=(ReasonCode.NOT_APPLICABLE,))
    acts.publish_action_mapping(
        ActionMapping(mapping_id="m", version=1, domain_id="generic",
                      decision_type="approve", decision_outcome=DecisionOutcome.ADVANCE,
                      permitted_action_type="ACT", target_system_type="SYS",
                      parameter_schema=ParameterSchema(required_fields=("k",))),
        actor=actor, tenant_id=t)
    req = acts.create_action_request(
        decision_id=decision.decision_id, mapping_id="m", target_system="SYS",
        created_by=actor, requested_parameters={"k": "v"})
    acts.validate_action_request(request_id=req.action_request_id, actor=actor)
    cer.bind_cer(request_id=req.action_request_id, actor=actor)
    authz.submit_for_authorization(request_id=req.action_request_id, actor=actor)
    intent = exe.create_execution_intent(action_request_id=req.action_request_id, created_by=actor)
    exe.dispatch_execution(intent_id=intent.execution_intent_id, actor=actor)
    rec.query_external_status(intent_id=intent.execution_intent_id, actor=actor)
    result = rec.reconcile_execution(intent_id=intent.execution_intent_id, actor=actor)

    assert result.status is ReconciliationStatus.RECONCILED
    assert type(decision)(**decision.model_dump()) == decision  # serialization round-trip
    events = {e.event_type for e in audit._repo.all()}
    assert AuditEventType.EXECUTION_RECONCILED in events
    return result.status.value


if __name__ == "__main__":
    print("external consumer:", run())
