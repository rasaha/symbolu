"""Hiring-action execution service (H4).

Executes an AUTHORIZED action through the **replaceable external-execution port**,
after enforcing the exact authorization: valid + current (unexpired), unchanged
parameters, and all pre-execution obligations met. Transport (dispatch) is kept
separate from the observed business outcome (the receipt) — a transport ack never
means executed. Retries are bounded, idempotent, and only for classified transient
failures; a succeeded action is never retried and no second external action is
created.
"""

from __future__ import annotations

from typing import Callable, Optional

from ugence_decision_authority.api.common import new_id, utc_now
from ugence_governance_provider_framework.api import ExecutionBusinessOutcome, ExecutionDispatchRequest

from ..actions.records import (
    ExecutionAttempt,
    ExecutionErrorClass,
    ExecutionReceipt,
    params_hash,
)
from ..actions.status import ActionProposalStatus
from ..domain_audit.events import HiringDomainEventType
from ..domain_audit.service import HiringDomainAuditService
from ..errors import (
    ActionConstraintViolationError,
    ActionNotAuthorizedError,
    HiringAuthorizationExpiredError,
    DuplicateExecutionError,
    IllegalActionTransitionError,
    MalformedReceiptError,
    ObligationUnmetError,
    TargetMismatchError,
)
from ._hiring_context import ActorContext, guard_tenant

_EXECUTABLE_FROM = (ActionProposalStatus.AUTHORIZED, ActionProposalStatus.EXECUTION_FAILED)


class HiringActionExecutionService:
    def __init__(
        self, *, proposals, authorizations, attempts, audit: HiringDomainAuditService,
        id_factory: Callable[[str], str] = new_id, max_retries: int = 2,
    ) -> None:
        self._proposals = proposals
        self._authorizations = authorizations
        self._attempts = attempts
        self._audit = audit
        self._new_id = id_factory
        self._max_retries = max_retries

    def execute(
        self, ctx: ActorContext, *, proposal_id: str, adapter,
        satisfied_obligations: tuple[str, ...] = (), now=None,
    ) -> ExecutionAttempt:
        proposal = self._proposals.get(proposal_id)
        guard_tenant(ctx, record_tenant_id=proposal.tenant_id, entity_type="action",
                     entity_id=proposal_id, audit=self._audit)
        if proposal.status not in _EXECUTABLE_FROM:
            raise IllegalActionTransitionError(
                f"action '{proposal_id}' is not executable ({proposal.status.value})")

        auth = self._authorizations.latest_for_proposal(proposal_id)
        if auth is None or not auth.authorized:
            raise ActionNotAuthorizedError(f"action '{proposal_id}' has no valid authorization")

        # --- exact + current authorization (§7) ---
        clock = now or utc_now()
        if auth.expiry is not None and clock > auth.expiry:
            raise HiringAuthorizationExpiredError(f"authorization for '{proposal_id}' has expired")
        if params_hash(proposal.normalized_parameters) != auth.bound_parameter_hash:
            raise ActionConstraintViolationError(
                "action parameters changed since authorization; a new authorization is required")

        # --- pre-execution obligations (§8) ---
        unmet = tuple(sorted(set(auth.obligations) - set(satisfied_obligations)))
        if unmet:
            self._audit.record(
                event_type=HiringDomainEventType.ACTION_OBLIGATION_UNMET, entity_type="action",
                entity_id=proposal_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
                actor_type=ctx.actor_type, correlation_id=proposal.correlation_id,
                payload={"unmet": ",".join(unmet)})
            raise ObligationUnmetError(f"unmet pre-execution obligations: {', '.join(unmet)}")

        # --- idempotency + bounded retry (§11) ---
        prior = self._attempts.for_proposal(proposal_id)
        if any(a.execution_status == ExecutionBusinessOutcome.SUCCEEDED.value for a in prior):
            raise DuplicateExecutionError(f"action '{proposal_id}' already executed successfully")
        attempt_number = len(prior) + 1
        is_retry = attempt_number > 1
        if is_retry:
            last = prior[-1]
            if last.error_classification is not ExecutionErrorClass.RETRYABLE:
                raise IllegalActionTransitionError("last failure is not retryable")
            if attempt_number - 1 > self._max_retries:
                raise IllegalActionTransitionError("retry budget exhausted")

        # move to EXECUTION_PENDING (from AUTHORIZED or EXECUTION_FAILED)
        pending = proposal.with_status(ActionProposalStatus.EXECUTION_PENDING)
        self._proposals.add(pending)
        self._audit.record(
            event_type=(HiringDomainEventType.HIRING_EXECUTION_RETRIED if is_retry
                        else HiringDomainEventType.HIRING_EXECUTION_REQUESTED),
            entity_type="action", entity_id=proposal_id, tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id, actor_type=ctx.actor_type, entity_version=pending.version,
            correlation_id=proposal.correlation_id, payload={"attempt": str(attempt_number)})

        # --- dispatch (transport) ---
        req = ExecutionDispatchRequest(
            action_type=proposal.action_type.value, parameters=proposal.params(),
            idempotency_key=proposal.idempotency_key, correlation_id=proposal.correlation_id)
        dispatch = adapter.dispatch(req)

        attempt_kwargs = dict(
            attempt_id=self._new_id("attempt"), tenant_id=proposal.tenant_id,
            action_proposal_id=proposal_id, authorization_id=auth.authorization_id,
            target_system=proposal.target_system, action_type=proposal.action_type.value,
            request_parameter_hash=params_hash(proposal.normalized_parameters),
            attempt_number=attempt_number, idempotency_key=proposal.idempotency_key,
            adapter_id=getattr(adapter, "adapter_id", ""),
            transport_accepted=dispatch.accepted, transport_error=dispatch.transport_error,
            external_request_id=dispatch.external_request_id,
            correlation_id=proposal.correlation_id, causation_id=auth.authorization_id)

        # transport failure / timeout → transient (or permanent) failure, no execution
        if not dispatch.accepted or dispatch.timed_out:
            err = ExecutionErrorClass.RETRYABLE if dispatch.retryable else ExecutionErrorClass.TERMINAL
            attempt = ExecutionAttempt(execution_status=ExecutionBusinessOutcome.UNKNOWN.value,
                                       error_classification=err, completed_at=clock, **attempt_kwargs)
            self._attempts.add(attempt)
            self._proposals.add(pending.with_status(ActionProposalStatus.EXECUTION_FAILED))
            self._fail_audit(ctx, proposal_id, proposal.correlation_id,
                             reason="transport_failed" if not dispatch.accepted else "timeout")
            return attempt

        if dispatch.pending:
            attempt = ExecutionAttempt(execution_status=ExecutionBusinessOutcome.PENDING.value,
                                       error_classification=ExecutionErrorClass.INDETERMINATE,
                                       **attempt_kwargs)
            self._attempts.add(attempt)
            self._audit.record(
                event_type=HiringDomainEventType.HIRING_EXECUTION_ATTEMPTED, entity_type="action",
                entity_id=proposal_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
                actor_type=ctx.actor_type, correlation_id=proposal.correlation_id,
                payload={"status": "PENDING"})
            return attempt  # proposal stays EXECUTION_PENDING (delayed completion)

        # --- observe (business outcome) ---
        obs = adapter.observe(external_request_id=dispatch.external_request_id)

        if obs.business_outcome is ExecutionBusinessOutcome.UNKNOWN:
            attempt = ExecutionAttempt(execution_status=obs.business_outcome.value,
                                       error_classification=ExecutionErrorClass.INDETERMINATE,
                                       completed_at=clock, **attempt_kwargs)
            self._attempts.add(attempt)
            self._proposals.add(pending.with_status(ActionProposalStatus.EXECUTION_FAILED))
            self._fail_audit(ctx, proposal_id, proposal.correlation_id, reason="malformed_receipt")
            raise MalformedReceiptError(f"malformed execution receipt for '{proposal_id}'")

        observed = tuple(sorted(obs.observed_parameters.items()))
        receipt = ExecutionReceipt(
            receipt_id=self._new_id("rcpt"), business_outcome=obs.business_outcome.value,
            observed_parameters=observed, final=obs.final, reason=obs.reason,
            target_system=proposal.target_system, provider_trace_id=obs.provider_trace_id,
            fingerprint=obs.fingerprint, raw_receipt_ref=dispatch.external_request_id)

        observed_target = dict(observed).get("target")
        if observed_target is not None and observed_target != proposal.target_system:
            attempt = ExecutionAttempt(execution_status=obs.business_outcome.value, receipt=receipt,
                                       error_classification=ExecutionErrorClass.TERMINAL,
                                       completed_at=clock, **attempt_kwargs)
            self._attempts.add(attempt)
            self._proposals.add(pending.with_status(ActionProposalStatus.EXECUTION_FAILED))
            self._fail_audit(ctx, proposal_id, proposal.correlation_id, reason="target_mismatch")
            raise TargetMismatchError(
                f"receipt target '{observed_target}' != authorized '{proposal.target_system}'")

        # legitimate business outcomes
        if obs.business_outcome in (ExecutionBusinessOutcome.SUCCEEDED, ExecutionBusinessOutcome.DUPLICATE):
            attempt = ExecutionAttempt(execution_status=obs.business_outcome.value, receipt=receipt,
                                       error_classification=ExecutionErrorClass.NONE, completed_at=clock,
                                       **attempt_kwargs)
            self._attempts.add(attempt)
            executed = pending.with_status(ActionProposalStatus.EXECUTED)
            self._proposals.add(executed)
            self._proposals.add(executed.with_status(ActionProposalStatus.RECONCILIATION_REQUIRED))
            self._audit.record(
                event_type=HiringDomainEventType.HIRING_EXECUTION_SUCCEEDED, entity_type="action",
                entity_id=proposal_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
                actor_type=ctx.actor_type, correlation_id=proposal.correlation_id,
                causation_id=receipt.receipt_id,
                payload={"outcome": obs.business_outcome.value})
            return attempt

        # FAILED / REJECTED / PENDING (non-final)
        err = ExecutionErrorClass.TERMINAL if obs.final else ExecutionErrorClass.INDETERMINATE
        attempt = ExecutionAttempt(execution_status=obs.business_outcome.value, receipt=receipt,
                                   error_classification=err, completed_at=clock, **attempt_kwargs)
        self._attempts.add(attempt)
        self._proposals.add(pending.with_status(ActionProposalStatus.EXECUTION_FAILED))
        self._fail_audit(ctx, proposal_id, proposal.correlation_id, reason=obs.business_outcome.value)
        return attempt

    def _fail_audit(self, ctx, proposal_id, correlation_id, *, reason):
        self._audit.record(
            event_type=HiringDomainEventType.HIRING_EXECUTION_FAILED, entity_type="action",
            entity_id=proposal_id, tenant_id=ctx.tenant_id, actor_id=ctx.actor_id,
            actor_type=ctx.actor_type, correlation_id=correlation_id, payload={"reason": reason})
