"""H4 read models (read-only projections).

Authorization summary, pending obligations, execution timeline, execution failures,
reconciliation status, unresolved mismatches, compensation queue, and the complete
decision→outcome trace. All read-only; tenant-isolated in the service.
"""

from __future__ import annotations

from ..domain.base import DomainModel
from ..errors import CrossTenantHiringAccessError
from .status import ActionProposalStatus


class AuthorizationSummaryView(DomainModel):
    action_proposal_id: str
    action_type: str
    authorized: bool = False
    outcome: str = ""
    constraints: tuple[str, ...] = ()
    obligations: tuple[str, ...] = ()
    provider_id: str = ""


class ExecutionTimelineEntry(DomainModel):
    attempt_number: int
    execution_status: str
    error_classification: str
    transport_accepted: bool
    external_request_id: str = ""


class ExecutionTimelineView(DomainModel):
    action_proposal_id: str
    status: str
    entries: tuple[ExecutionTimelineEntry, ...] = ()


class ReconciliationStatusView(DomainModel):
    action_proposal_id: str
    status: str
    reconciliation_outcome: str = ""
    compensation_required: bool = False
    mismatched_fields: tuple[str, ...] = ()


class DecisionToOutcomeTrace(DomainModel):
    action_proposal_id: str
    recommendation_id: str
    human_decision_id: str
    decision_case_id: str
    action_type: str
    authorized: bool = False
    execution_status: str = ""
    reconciliation_outcome: str = ""
    final_status: str = ""


class ActionReadModelService:
    def __init__(self, *, proposals, authorizations, attempts, reconciliations, compensations) -> None:
        self._proposals = proposals
        self._auths = authorizations
        self._attempts = attempts
        self._recons = reconciliations
        self._comps = compensations

    def _p(self, ctx, proposal_id):
        p = self._proposals.get(proposal_id)
        if p.tenant_id != ctx.tenant_id:
            raise CrossTenantHiringAccessError(f"cross-tenant read: {proposal_id}")
        return p

    def authorization_summary(self, ctx, proposal_id: str) -> AuthorizationSummaryView:
        p = self._p(ctx, proposal_id)
        a = self._auths.latest_for_proposal(proposal_id)
        return AuthorizationSummaryView(
            action_proposal_id=proposal_id, action_type=p.action_type.value,
            authorized=bool(a and a.authorized), outcome=a.outcome if a else "",
            constraints=a.constraints if a else (), obligations=a.obligations if a else (),
            provider_id=a.provider_id if a else "")

    def pending_obligations(self, ctx, proposal_id: str, satisfied: tuple[str, ...] = ()) -> tuple[str, ...]:
        self._p(ctx, proposal_id)
        a = self._auths.latest_for_proposal(proposal_id)
        if a is None:
            return ()
        return tuple(sorted(set(a.obligations) - set(satisfied)))

    def execution_timeline(self, ctx, proposal_id: str) -> ExecutionTimelineView:
        p = self._p(ctx, proposal_id)
        entries = tuple(ExecutionTimelineEntry(
            attempt_number=a.attempt_number, execution_status=a.execution_status,
            error_classification=a.error_classification.value, transport_accepted=a.transport_accepted,
            external_request_id=a.external_request_id) for a in self._attempts.for_proposal(proposal_id))
        return ExecutionTimelineView(action_proposal_id=proposal_id, status=p.status.value, entries=entries)

    def execution_failures(self, ctx) -> tuple[str, ...]:
        return tuple(p.action_proposal_id for p in self._proposals.by_tenant(ctx.tenant_id)
                     if p.status is ActionProposalStatus.EXECUTION_FAILED)

    def reconciliation_status(self, ctx, proposal_id: str) -> ReconciliationStatusView:
        p = self._p(ctx, proposal_id)
        r = self._recons.latest_for_proposal(proposal_id)
        return ReconciliationStatusView(
            action_proposal_id=proposal_id, status=p.status.value,
            reconciliation_outcome=r.outcome.value if r else "",
            compensation_required=bool(r and r.compensation_required),
            mismatched_fields=r.mismatched_fields if r else ())

    def unresolved_mismatches(self, ctx) -> tuple[str, ...]:
        return tuple(p.action_proposal_id for p in self._proposals.by_tenant(ctx.tenant_id)
                     if p.status is ActionProposalStatus.COMPENSATION_REQUIRED)

    def compensation_queue(self, ctx) -> tuple:
        return self._comps.by_tenant(ctx.tenant_id)

    def decision_to_outcome_trace(self, ctx, proposal_id: str) -> DecisionToOutcomeTrace:
        p = self._p(ctx, proposal_id)
        a = self._auths.latest_for_proposal(proposal_id)
        attempts = self._attempts.for_proposal(proposal_id)
        r = self._recons.latest_for_proposal(proposal_id)
        return DecisionToOutcomeTrace(
            action_proposal_id=proposal_id, recommendation_id=p.recommendation_id,
            human_decision_id=p.human_decision_id, decision_case_id=p.decision_case_id,
            action_type=p.action_type.value, authorized=bool(a and a.authorized),
            execution_status=attempts[-1].execution_status if attempts else "",
            reconciliation_outcome=r.outcome.value if r else "", final_status=p.status.value)
