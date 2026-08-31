"""DGM service composition (benchmark-owned, kernel public API only).

Builds the kernel service set every governance-bearing strategy shares, with
deterministic identity/clock. Imports no provider — the control plane (if any) is
supplied by the strategy that owns an action-governance provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from decision_governance.api.audit import AuditService, InMemoryAuditRepository
from decision_governance.api.identity import StaticIdentityProvider
from decision_governance.api.policy import (
    AccessGrant, EvidenceAccessPolicy, GrantStore, Permission)
from decision_governance.api.ports import FINALIZED_STATUS, LinkedRecordSnapshot
from decision_governance.api.repositories import (
    InMemoryActionRequestRepository, InMemoryDecisionCaseRepository, InMemoryExecutionRepository)
from decision_governance.api.services import (
    ActionAuthorizationService, ActionRequestService, ActionRequestValidationService,
    CaseDecisionService, CaseRecommendationService, CaseValidationService, CERBindingService,
    DecisionCaseService, ExecutionService, ExecutionValidationService, ReconciliationService)

from .determinism import make_clock, make_id_factory


class _NeutralLinked:
    def get_record(self, *, tenant_id, record_type, record_id, version=None):
        return LinkedRecordSnapshot(
            record_type=record_type, record_id=record_id, version=version or 1,
            tenant_id="t", status=FINALIZED_STATUS, subject_ref="subject")


@dataclass
class DGMServices:
    cases: DecisionCaseService
    rec: CaseRecommendationService
    dec: CaseDecisionService
    acts: ActionRequestService
    cer: CERBindingService
    authz: Optional[ActionAuthorizationService]
    exe: Optional[ExecutionService]
    reconcile: Optional[ReconciliationService]
    audit: AuditService
    actor: str
    tenant: str

    def audit_events(self) -> list:
        return list(self.audit._repo.all())


def build_services(seed: str, *, control_plane=None, execution_adapter=None) -> DGMServices:
    idf, clk = make_id_factory(seed), make_clock(seed)
    t, actor = "t", "gov"
    idp = StaticIdentityProvider()
    for who in (actor, "reviewer", "senior"):
        idp.register_human(who)
    grants = GrantStore()
    for who in (actor, "reviewer", "senior"):
        grants.add(AccessGrant(who, t, frozenset(Permission)))
    policy = EvidenceAccessPolicy(grants)
    # One time domain per replayed scenario (D1): every collaborator that stamps
    # or compares an instant reads the scenario clock, including the ones whose
    # own default is the wall clock.
    audit = AuditService(InMemoryAuditRepository(), clock=clk)
    cr, ar, er = (InMemoryDecisionCaseRepository(), InMemoryActionRequestRepository(),
                  InMemoryExecutionRepository())
    val = CaseValidationService(_NeutralLinked())

    authz = exe = reconcile = None
    if control_plane is not None:
        authz = ActionAuthorizationService(ar, control_plane, audit, idp, policy,
                                           id_factory=idf, clock=clk)
    if execution_adapter is not None:
        exe = ExecutionService(er, ar, ExecutionValidationService(er, ar, clock=clk),
                               execution_adapter,
                               audit, idp, policy, id_factory=idf, clock=clk)
        reconcile = ReconciliationService(er, execution_adapter, audit, idp, policy,
                                          id_factory=idf, clock=clk)
    return DGMServices(
        cases=DecisionCaseService(cr, val, audit, idp, policy, id_factory=idf, clock=clk),
        rec=CaseRecommendationService(cr, val, audit, idp, policy, id_factory=idf, clock=clk),
        dec=CaseDecisionService(cr, val, audit, idp, policy, id_factory=idf, clock=clk),
        acts=ActionRequestService(ar, cr, ActionRequestValidationService(ar, cr, clock=clk),
                                  audit, idp, policy, id_factory=idf, clock=clk),
        cer=CERBindingService(ar, cr, audit, idp, policy, id_factory=idf, clock=clk),
        authz=authz, exe=exe, reconcile=reconcile, audit=audit, actor=actor, tenant=t)
