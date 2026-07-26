"""Hiring-action compensation service (H4).

Compensation is **explicit and separately governed**. A reversible compensation is
proposed as a requirement whose compensating action must be separately authorized
(never auto-executed, never AI-self-authorized). An **irreversible** action is never
auto-compensated — it is flagged for human remediation. Where compensation changes
external state, it is represented as a new proposed action requiring its own
ActionGate authorization.
"""

from __future__ import annotations

from typing import Callable, Optional

from decision_governance.api.common import new_id

from ..actions.records import CompensationRequirement, CompensationStatus
from ..actions.status import ActionProposalStatus
from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..errors import CompensationError
from ._hiring_context import ActorContext, guard_tenant


class HiringCompensationService:
    def __init__(
        self, *, proposals, compensations, audit: HiringDomainAuditService,
        id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._proposals = proposals
        self._compensations = compensations
        self._audit = audit
        self._new_id = id_factory

    def propose_compensation(
        self, ctx: ActorContext, *, proposal_id: str, reversible: bool, reason: str,
        proposed_compensation_action_id: str = "",
    ) -> CompensationRequirement:
        proposal = self._proposals.get(proposal_id)
        guard_tenant(ctx, record_tenant_id=proposal.tenant_id, entity_type="action",
                     entity_id=proposal_id, audit=self._audit)
        if proposal.status is not ActionProposalStatus.COMPENSATION_REQUIRED:
            raise CompensationError(
                f"action '{proposal_id}' is not COMPENSATION_REQUIRED ({proposal.status.value})")

        requires_human = not reversible  # irreversible → human remediation, never auto-compensated
        status = (CompensationStatus.HUMAN_REMEDIATION_REQUIRED if requires_human
                  else CompensationStatus.PROPOSED)
        comp = CompensationRequirement(
            compensation_id=self._new_id("comp"), tenant_id=proposal.tenant_id,
            action_proposal_id=proposal_id, reason=reason, reversible=reversible,
            requires_human_remediation=requires_human,
            proposed_compensation_action_id=proposed_compensation_action_id, status=status,
            correlation_id=proposal.correlation_id)
        self._compensations.add(comp)
        self._audit.record(
            event_type=(HiringDomainEventType.REMEDIATION_REQUESTED if requires_human
                        else HiringDomainEventType.COMPENSATION_PROPOSED),
            entity_type="action", entity_id=proposal_id, tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id, actor_type=ctx.actor_type, correlation_id=proposal.correlation_id,
            causation_id=comp.compensation_id,
            payload={"reversible": str(reversible), "reason": reason})
        return comp

    def resolve_compensation(self, ctx: ActorContext, *, compensation_id: str,
                             proposal_id: str) -> CompensationRequirement:
        """Mark a compensation resolved (after its separately-authorized action, or
        human remediation, is complete) and close out the original action."""
        proposal = self._proposals.get(proposal_id)
        guard_tenant(ctx, record_tenant_id=proposal.tenant_id, entity_type="action",
                     entity_id=proposal_id, audit=self._audit)
        comps = [c for c in self._compensations.for_proposal(proposal_id)
                 if c.compensation_id == compensation_id]
        if not comps:
            raise CompensationError(f"compensation '{compensation_id}' not found for '{proposal_id}'")
        resolved = comps[0].model_copy(update={"status": CompensationStatus.RESOLVED})
        # append-only store: record resolution as a new compensation entry keyed distinctly
        resolved = resolved.model_copy(update={"compensation_id": comps[0].compensation_id + ":resolved"})
        self._compensations.add(resolved)
        self._proposals.add(proposal.with_status(ActionProposalStatus.COMPENSATED))
        return resolved
