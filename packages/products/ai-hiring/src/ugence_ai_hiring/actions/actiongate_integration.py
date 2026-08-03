"""Action Governance (ActionGate) integration boundary (H4).

Authorizes a prepared hiring action **only** through the Action Governance Provider
contract from `ugence_governance_provider_framework.api` — never ActionGate internals. ActionGate
(or any conformant action-governance provider, incl. the framework's deterministic
reference provider) is injected. Provider failure is fail-safe: the action is
recorded as NOT authorized with the error preserved, so nothing can execute.

The provider authorizes; it does not execute. Its constraints/obligations/expiry are
persisted exactly; no downstream adapter may relax them.
"""

from __future__ import annotations

from typing import Optional

from ugence_governance_provider_framework.api import (
    ActionGovernanceOutcome,
    ActionGovernanceRequest,
    ProviderError,
)

from .proposal import HiringActionProposal
from .records import ActionAuthorizationRecord, params_hash

_AUTHORIZED_OUTCOMES = frozenset(
    {ActionGovernanceOutcome.AUTHORIZED, ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS})


class ActionAuthorizationIntegration:
    """Wrap an action-governance provider and normalize its authorization result."""

    def __init__(self, provider, *, provider_id: str = "", id_factory=None) -> None:
        self._provider = provider
        self._provider_id = provider_id or getattr(provider.descriptor(), "provider_id", "")
        from ugence_decision_authority.api.common import new_id
        self._new_id = id_factory or new_id

    def authorize(
        self, proposal: HiringActionProposal, *, decision_refs: tuple[str, ...] = (),
        evidence_refs: tuple[str, ...] = (), risk_context: Optional[dict] = None,
        authorization_expired: bool = False,
    ) -> ActionAuthorizationRecord:
        request = ActionGovernanceRequest(
            action_type=proposal.action_type.value, requested_parameters=proposal.params(),
            actor=proposal.proposing_actor, authority_context=proposal.accountable_authority,
            target_resource=proposal.target_system, policy_refs=proposal.policy_refs,
            risk_context=risk_context or {}, evidence_refs=evidence_refs, decision_refs=decision_refs,
            idempotency_key=proposal.idempotency_key, correlation_id=proposal.correlation_id,
            authorization_expired=authorization_expired)

        auth_id = self._new_id("auth")
        common = dict(
            authorization_id=auth_id, tenant_id=proposal.tenant_id,
            action_proposal_id=proposal.action_proposal_id, action_type=proposal.action_type.value,
            provider_id=self._provider_id, bound_actor=proposal.proposing_actor,
            bound_target=proposal.target_system,
            bound_parameter_hash=params_hash(proposal.normalized_parameters),
            idempotency_key=proposal.idempotency_key, correlation_id=proposal.correlation_id,
            causation_id=proposal.action_proposal_id)

        try:
            result = self._provider.authorize(request)
        except ProviderError as exc:
            return ActionAuthorizationRecord(
                outcome=ActionGovernanceOutcome.INDETERMINATE.value, authorized=False,
                reason_codes=(f"{type(exc).__name__}",), **common)

        return ActionAuthorizationRecord(
            outcome=result.outcome.value, authorized=result.outcome in _AUTHORIZED_OUTCOMES,
            constraints=result.constraints, obligations=result.obligations, expiry=result.expiry,
            authority_basis=result.authority_basis, reason_codes=result.reason_codes,
            provider_trace_id=result.provider_trace_id, fingerprint=result.fingerprint, **common)
