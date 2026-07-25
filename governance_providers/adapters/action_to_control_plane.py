"""Adapter: ActionGovernanceProvider → kernel ActionControlPlanePort.

Preserves authorization outcome, constraints, obligations, expiry, and authority
basis. Provider failures are normalized at this boundary to a fail-safe
``INDETERMINATE`` authorization — a vendor exception never leaks into the kernel.
"""

from __future__ import annotations

from datetime import timedelta

from decision_governance.api.common import Clock, IdFactory, new_id, utc_now
from decision_governance.api.contracts import (
    ActionAuthorizationResponse,
    AuthorizationOutcome as KernelAuthorizationOutcome,
)

from ..contracts import ActionGovernanceRequest
from ..contracts.action import ActionGovernanceOutcome, ActionGovernanceProvider
from ..errors import ProviderError

_OUTCOME_MAP = {
    ActionGovernanceOutcome.AUTHORIZED: KernelAuthorizationOutcome.AUTHORIZED,
    ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS: KernelAuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS,
    ActionGovernanceOutcome.DENIED: KernelAuthorizationOutcome.DENIED,
    ActionGovernanceOutcome.INDETERMINATE: KernelAuthorizationOutcome.INDETERMINATE,
    ActionGovernanceOutcome.EXPIRED: KernelAuthorizationOutcome.EXPIRED,
}


class ActionGovernanceControlPlaneAdapter:
    """Implements ``ActionControlPlanePort`` over an :class:`ActionGovernanceProvider`."""

    def __init__(self, provider: ActionGovernanceProvider, *,
                 validity: timedelta = timedelta(hours=1),
                 id_factory: IdFactory = new_id, clock: Clock = utc_now) -> None:
        self._provider = provider
        self._validity = validity
        self._new_id = id_factory
        self._clock = clock

    def authorize(self, action_request, cer) -> ActionAuthorizationResponse:
        now = self._clock()
        req = ActionGovernanceRequest(
            action_type=action_request.action_type,
            requested_parameters=dict(action_request.requested_parameters or {}),
            actor=action_request.created_by,
            authority_context=action_request.authority_ref or "",
            target_resource=action_request.target_system,
            policy_refs=tuple(f"{r.ref_id}:{r.version}" for r in cer.policy_context.policy_refs),
            decision_refs=(action_request.decision_id,),
            idempotency_key=action_request.idempotency_key,
            correlation_id=cer.correlation_id,
            authorization_expired=cer.expires_at is not None and cer.expires_at < now)
        try:
            result = self._provider.authorize(req)
            outcome = _OUTCOME_MAP[result.outcome]
            constraints, obligations = result.constraints, result.obligations
            authority_basis = result.authority_basis
            reason_codes = result.reason_codes or (outcome.value,)
        except ProviderError as exc:  # normalized fail-safe — never leak the vendor error
            outcome = KernelAuthorizationOutcome.INDETERMINATE
            constraints, obligations = (), ()
            authority_basis = ""
            reason_codes = (outcome.value, f"provider_error:{type(exc).__name__}")
        return ActionAuthorizationResponse(
            authorization_id=self._new_id("authz"),
            action_request_id=action_request.action_request_id, cer_id=cer.cer_id,
            outcome=outcome, constraints=constraints, obligations=obligations,
            authorized_at=now,
            expires_at=None if outcome is KernelAuthorizationOutcome.EXPIRED else now + self._validity,
            control_plane_ref=f"provider:{self._provider.descriptor().provider_id}"
                              + (f"|authority:{authority_basis}" if authority_basis else ""),
            reason_codes=reason_codes,
            policy_versions=tuple(f"{r.ref_id}:{r.version}" for r in cer.policy_context.policy_refs),
            correlation_id=cer.correlation_id)
