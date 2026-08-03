"""Hiring-action proposal service (H4).

Proposes a hiring action **only** from an eligible governed human decision (§3): a
DECIDED H3 governance binding, a human decision authority, a non-superseded
recommendation, a non-cancelled application, matching scope, and a decision outcome
that maps to the requested action type. A recommendation alone is never an
executable source. Proposals are advisory intents — they do not authorize or execute.
"""

from __future__ import annotations

from typing import Callable, Optional

from ugence_decision_authority.api.common import canonical_hash, new_id

from ..actions.action_types import HiringActionType, action_allowed_for_decision
from ..actions.proposal import HiringActionProposal
from ..actions.status import ActionProposalStatus
from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..errors import (
    DecisionActionMismatchError,
    IneligibleActionSourceError,
)
from ..governance.binding import GovernanceBindingStatus
from ..hiring_applications.status import APPLICATION_TERMINAL_STATUSES, ApplicationStatus
from ..recommendations.status import RecommendationStatus
from ._hiring_context import ActorContext, guard_tenant

_HUMAN_AUTHORITIES = {"HUMAN_REVIEWER", "HUMAN_APPROVER", "COMMITTEE"}


class HiringActionProposalService:
    def __init__(
        self, *, recommendations, bindings, applications, proposals, case_decisions,
        audit: HiringDomainAuditService, id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._recs = recommendations
        self._bindings = bindings
        self._apps = applications
        self._proposals = proposals
        self._case_decs = case_decisions
        self._audit = audit
        self._new_id = id_factory

    def propose(
        self, ctx: ActorContext, *, recommendation_id: str, action_type: HiringActionType,
        target_system: str, parameters: tuple[tuple[str, str], ...] = (),
        requested_effects: tuple[str, ...] = (), prohibited_effects: tuple[str, ...] = (),
        idempotency_key: Optional[str] = None, correlation_id: str = "",
    ) -> HiringActionProposal:
        rec = self._recs.get(recommendation_id)
        guard_tenant(ctx, record_tenant_id=rec.tenant_id, entity_type="recommendation",
                     entity_id=recommendation_id, audit=self._audit)
        if rec.status == RecommendationStatus.SUPERSEDED:
            raise IneligibleActionSourceError("recommendation is superseded")

        binding = self._bindings.for_recommendation(recommendation_id)
        if binding is None or binding.status != GovernanceBindingStatus.DECIDED or not binding.decision_id:
            raise IneligibleActionSourceError(
                "no DECIDED governance binding with a recorded human decision")

        decision = self._case_decs.get_decision(binding.decision_id)
        if decision.authority_type.value not in _HUMAN_AUTHORITIES:
            raise IneligibleActionSourceError(
                f"decision authority '{decision.authority_type.value}' is not human")

        app = self._apps.get(rec.application_id)
        if app.status in APPLICATION_TERMINAL_STATUSES:
            raise IneligibleActionSourceError(f"application is {app.status.value} (cancelled/closed)")
        if app.tenant_id != ctx.tenant_id or rec.application_id != app.application_id:
            raise IneligibleActionSourceError("tenant/application scope mismatch")

        if not action_allowed_for_decision(decision.outcome, action_type):
            raise DecisionActionMismatchError(
                f"action '{action_type.value}' not permitted for decision '{decision.outcome.value}'")

        ikey = idempotency_key or canonical_hash(
            {"decision": binding.decision_id, "action": action_type.value, "app": app.application_id})
        existing = self._proposals.for_idempotency_key(ctx.tenant_id, ikey)
        if existing is not None and existing.status not in (
                ActionProposalStatus.CANCELLED, ActionProposalStatus.SUPERSEDED):
            raise IneligibleActionSourceError(
                f"an active action proposal already exists for idempotency key")

        corr = correlation_id or binding.correlation_id or recommendation_id
        proposal = HiringActionProposal(
            action_proposal_id=self._new_id("act"), tenant_id=ctx.tenant_id,
            application_id=app.application_id, candidate_subject_ref=rec.candidate_subject_ref,
            decision_case_id=binding.decision_case_id, human_decision_id=binding.decision_id,
            recommendation_id=recommendation_id, recommendation_version=rec.version,
            action_type=action_type, target_system=target_system,
            normalized_parameters=tuple(parameters), requested_effects=requested_effects,
            prohibited_effects=prohibited_effects, proposing_actor=ctx.actor_id,
            accountable_authority=decision.decided_by, policy_refs=rec.policy_refs,
            correlation_id=corr, causation_id=binding.decision_id, idempotency_key=ikey)
        self._proposals.add(proposal)
        self._audit.record(
            event_type=HiringDomainEventType.ACTION_PROPOSED, entity_type="action",
            entity_id=proposal.action_proposal_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, new_state=proposal.status.value, entity_version=proposal.version,
            correlation_id=corr, causation_id=binding.decision_id,
            payload={"action_type": action_type.value, "decision": decision.outcome.value})
        return proposal

    def mark_ready(self, ctx: ActorContext, proposal_id: str) -> HiringActionProposal:
        return self._transition(ctx, proposal_id, ActionProposalStatus.READY_FOR_AUTHORIZATION,
                                HiringDomainEventType.ACTION_READY_FOR_AUTHORIZATION)

    def cancel(self, ctx: ActorContext, proposal_id: str) -> HiringActionProposal:
        return self._transition(ctx, proposal_id, ActionProposalStatus.CANCELLED,
                                HiringDomainEventType.ACTION_CANCELLED)

    def supersede(self, ctx: ActorContext, proposal_id: str) -> HiringActionProposal:
        return self._transition(ctx, proposal_id, ActionProposalStatus.SUPERSEDED,
                                HiringDomainEventType.ACTION_SUPERSEDED)

    def _transition(self, ctx, proposal_id, new_status, event_type) -> HiringActionProposal:
        current = self._proposals.get(proposal_id)
        guard_tenant(ctx, record_tenant_id=current.tenant_id, entity_type="action",
                     entity_id=proposal_id, audit=self._audit)
        updated = current.with_status(new_status)
        self._proposals.add(updated)
        self._audit.record(
            event_type=event_type, entity_type="action", entity_id=proposal_id,
            tenant_id=ctx.tenant_id, actor_id=ctx.actor_id, actor_type=ctx.actor_type,
            previous_state=current.status.value, new_state=updated.status.value,
            entity_version=updated.version, correlation_id=current.correlation_id)
        return updated
