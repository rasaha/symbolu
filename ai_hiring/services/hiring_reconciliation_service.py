"""Hiring-action reconciliation service (H4).

Compares authorized intent (proposal + authorization) with what actually occurred
(the execution receipt/observed outcome) and classifies the result. A successful
transport or API response alone is never treated as reconciled — reconciliation
requires the observed business outcome. Mismatches and duplicates require
compensation and remain visible until explicitly handled.
"""

from __future__ import annotations

from typing import Callable

from decision_governance.api.common import new_id
from governance_providers.api import ExecutionBusinessOutcome

from ..actions.records import ReconciliationOutcome, ReconciliationRecord
from ..actions.status import ActionProposalStatus
from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ._hiring_context import ActorContext, guard_tenant

_COMPENSATION_OUTCOMES = frozenset(
    {ReconciliationOutcome.MISMATCHED, ReconciliationOutcome.DUPLICATE_EXECUTION})


class HiringReconciliationService:
    def __init__(
        self, *, proposals, authorizations, attempts, reconciliations,
        audit: HiringDomainAuditService, id_factory: Callable[[str], str] = new_id,
    ) -> None:
        self._proposals = proposals
        self._authorizations = authorizations
        self._attempts = attempts
        self._reconciliations = reconciliations
        self._audit = audit
        self._new_id = id_factory

    def reconcile(self, ctx: ActorContext, *, proposal_id: str) -> ReconciliationRecord:
        proposal = self._proposals.get(proposal_id)
        guard_tenant(ctx, record_tenant_id=proposal.tenant_id, entity_type="action",
                     entity_id=proposal_id, audit=self._audit)
        auth = self._authorizations.latest_for_proposal(proposal_id)
        attempts = self._attempts.for_proposal(proposal_id)

        outcome, matched, mismatched, details, attempt_id = self._classify(proposal, attempts)

        record = ReconciliationRecord(
            reconciliation_id=self._new_id("recon"), tenant_id=proposal.tenant_id,
            action_proposal_id=proposal_id, human_decision_id=proposal.human_decision_id,
            authorization_id=auth.authorization_id if auth else "", attempt_id=attempt_id,
            outcome=outcome, matched_fields=matched, mismatched_fields=mismatched, details=details,
            compensation_required=outcome in _COMPENSATION_OUTCOMES,
            correlation_id=proposal.correlation_id)
        self._reconciliations.add(record)

        # proposal transition (visible-until-handled for NOT_EXECUTED / UNVERIFIABLE)
        if proposal.status is ActionProposalStatus.RECONCILIATION_REQUIRED:
            if outcome in (ReconciliationOutcome.MATCHED, ReconciliationOutcome.PARTIALLY_MATCHED):
                self._proposals.add(proposal.with_status(ActionProposalStatus.RECONCILED))
            elif outcome in _COMPENSATION_OUTCOMES:
                self._proposals.add(proposal.with_status(ActionProposalStatus.COMPENSATION_REQUIRED))

        self._audit.record(
            event_type=HiringDomainEventType.RECONCILIATION_COMPLETED, entity_type="action",
            entity_id=proposal_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=proposal.correlation_id,
            causation_id=record.reconciliation_id, payload={"outcome": outcome.value})
        if outcome in _COMPENSATION_OUTCOMES:
            self._audit.record(
                event_type=HiringDomainEventType.RECONCILIATION_MISMATCH_DETECTED, entity_type="action",
                entity_id=proposal_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
                actor_type=ctx.actor_type, correlation_id=proposal.correlation_id,
                payload={"outcome": outcome.value, "mismatched": ",".join(mismatched)})
        return record

    def _classify(self, proposal, attempts):
        succeeded = [a for a in attempts if a.execution_status == ExecutionBusinessOutcome.SUCCEEDED.value]
        duplicate = [a for a in attempts if a.execution_status == ExecutionBusinessOutcome.DUPLICATE.value]
        if duplicate:
            return (ReconciliationOutcome.DUPLICATE_EXECUTION, (), ("target",),
                    ("duplicate external execution",), duplicate[-1].attempt_id)
        if not succeeded:
            return (ReconciliationOutcome.NOT_EXECUTED, (), (), ("no successful execution",),
                    attempts[-1].attempt_id if attempts else "")
        attempt = succeeded[-1]
        receipt = attempt.receipt
        if receipt is None or not receipt.final:
            return (ReconciliationOutcome.UNVERIFIABLE, (), (), ("no final receipt",), attempt.attempt_id)
        requested = proposal.params()
        observed = {k: v for k, v in receipt.observed_parameters if k != "target"}
        matched, mismatched, missing = [], [], []
        for k, v in requested.items():
            if k not in observed:
                missing.append(k)
            elif observed[k] != v:
                mismatched.append(k)
            else:
                matched.append(k)
        if mismatched:
            return (ReconciliationOutcome.MISMATCHED, tuple(sorted(matched)), tuple(sorted(mismatched)),
                    ("observed parameters differ from authorized",), attempt.attempt_id)
        if missing:
            return (ReconciliationOutcome.PARTIALLY_MATCHED, tuple(sorted(matched)), tuple(sorted(missing)),
                    ("some authorized parameters not observed",), attempt.attempt_id)
        return (ReconciliationOutcome.MATCHED, tuple(sorted(matched)), (), ("authorized intent matched",),
                attempt.attempt_id)
