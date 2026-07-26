"""Hiring-action authorization service (H4).

Authorizes a READY_FOR_AUTHORIZATION proposal **through the Action Governance
Provider (ActionGate)** via the injected `ActionAuthorizationIntegration`. It never
grants authorization itself — the provider does — and it persists the provider's
exact constraints/obligations/expiry. Denied/expired/indeterminate outcomes leave
the action non-executable.
"""

from __future__ import annotations

from typing import Callable

from decision_governance.api.common import new_id

from ..actions.records import ActionAuthorizationRecord
from ..actions.status import ActionProposalStatus
from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..errors import IllegalActionTransitionError
from ._hiring_context import ActorContext, guard_tenant


class HiringActionAuthorizationService:
    def __init__(
        self, *, proposals, authorizations, audit: HiringDomainAuditService,
        id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._proposals = proposals
        self._authorizations = authorizations
        self._audit = audit
        self._new_id = id_factory

    def authorize(
        self, ctx: ActorContext, *, proposal_id: str, integration,
        decision_refs: tuple[str, ...] = (), evidence_refs: tuple[str, ...] = (),
        authorization_expired: bool = False,
    ) -> ActionAuthorizationRecord:
        proposal = self._proposals.get(proposal_id)
        guard_tenant(ctx, record_tenant_id=proposal.tenant_id, entity_type="action",
                     entity_id=proposal_id, audit=self._audit)
        if proposal.status is not ActionProposalStatus.READY_FOR_AUTHORIZATION:
            raise IllegalActionTransitionError(
                f"action '{proposal_id}' is not READY_FOR_AUTHORIZATION ({proposal.status.value})")

        self._audit.record(
            event_type=HiringDomainEventType.ACTION_AUTHORIZATION_REQUESTED, entity_type="action",
            entity_id=proposal_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=proposal.correlation_id,
            payload={"action_type": proposal.action_type.value})

        auth = integration.authorize(
            proposal, decision_refs=decision_refs or (proposal.human_decision_id,),
            evidence_refs=evidence_refs, authorization_expired=authorization_expired)
        self._authorizations.add(auth)

        if auth.authorized:
            updated = proposal.with_status(ActionProposalStatus.AUTHORIZED)
            event = HiringDomainEventType.ACTION_AUTHORIZED
        else:
            updated = proposal.with_status(ActionProposalStatus.AUTHORIZATION_DENIED)
            event = HiringDomainEventType.ACTION_AUTHORIZATION_REFUSED
        self._proposals.add(updated)
        self._audit.record(
            event_type=event, entity_type="action", entity_id=proposal_id, tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id, actor_type=ctx.actor_type, previous_state=proposal.status.value,
            new_state=updated.status.value, entity_version=updated.version,
            correlation_id=proposal.correlation_id, causation_id=auth.authorization_id,
            payload={"outcome": auth.outcome, "provider": auth.provider_id,
                     "constraints": ",".join(auth.constraints), "obligations": ",".join(auth.obligations)})
        return auth
