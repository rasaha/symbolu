"""Adapter: ActionGovernanceProvider → kernel ActionControlPlanePort.

Preserves authorization outcome, constraints, obligations, expiry, and authority
basis. Provider failures are normalized at this boundary to a fail-safe
``INDETERMINATE`` authorization — a vendor exception never leaks into the kernel.

The Decision Authority kernel is an **optional** dependency: this module imports
without it (class defined, signatures intact); the kernel is loaded lazily the
first time an adapter is invoked. Absent the optional dependency, invocation
raises a precise ``ModuleNotFoundError`` naming the ``[adapters]`` extra.
"""

from __future__ import annotations

from datetime import timedelta

from ..contracts import ActionGovernanceRequest
from ..contracts.action import ActionGovernanceOutcome, ActionGovernanceProvider
from ..errors import ProviderError
from ._kernel import require_decision_authority

_KERNEL: dict | None = None


def _kernel() -> dict:
    """Lazily load and cache the optional kernel symbols + the frozen outcome map.

    Raises the precise optional-dependency error if Decision Authority is absent.
    """
    global _KERNEL
    if _KERNEL is None:
        require_decision_authority()
        from decision_governance.api.common import new_id, utc_now
        from decision_governance.api.contracts import (
            ActionAuthorizationResponse,
            AuthorizationOutcome as KernelAuthorizationOutcome,
        )
        _KERNEL = {
            "new_id": new_id,
            "utc_now": utc_now,
            "ActionAuthorizationResponse": ActionAuthorizationResponse,
            "AuthorizationOutcome": KernelAuthorizationOutcome,
            "OUTCOME_MAP": {
                ActionGovernanceOutcome.AUTHORIZED: KernelAuthorizationOutcome.AUTHORIZED,
                ActionGovernanceOutcome.AUTHORIZED_WITH_CONSTRAINTS:
                    KernelAuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS,
                ActionGovernanceOutcome.DENIED: KernelAuthorizationOutcome.DENIED,
                ActionGovernanceOutcome.INDETERMINATE: KernelAuthorizationOutcome.INDETERMINATE,
                ActionGovernanceOutcome.EXPIRED: KernelAuthorizationOutcome.EXPIRED,
            },
        }
    return _KERNEL


def _default_new_id(*args, **kwargs):
    """Default id factory — delegates to the kernel's ``new_id`` (lazily loaded)."""
    return _kernel()["new_id"](*args, **kwargs)


def _default_clock(*args, **kwargs):
    """Default clock — delegates to the kernel's ``utc_now`` (lazily loaded)."""
    return _kernel()["utc_now"](*args, **kwargs)


class ActionGovernanceControlPlaneAdapter:
    """Implements ``ActionControlPlanePort`` over an :class:`ActionGovernanceProvider`."""

    def __init__(self, provider: ActionGovernanceProvider, *,
                 validity: timedelta = timedelta(hours=1),
                 id_factory: IdFactory = _default_new_id, clock: Clock = _default_clock) -> None:
        self._provider = provider
        self._validity = validity
        self._new_id = id_factory
        self._clock = clock

    def authorize(self, action_request, cer) -> ActionAuthorizationResponse:
        k = _kernel()
        KernelAuthorizationOutcome = k["AuthorizationOutcome"]
        ActionAuthorizationResponse = k["ActionAuthorizationResponse"]
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
            # Inclusive boundary: the instant a CER expires, it is expired. The
            # exclusive form (`expires_at < now`) treated the boundary instant as
            # still valid, which disagreed by one instant with Action Clearance,
            # where `evaluation_time >= expires_at` is expired. A one-instant
            # disagreement about whether an authorization is live is a window in
            # which one layer authorizes what the other has already retired.
            authorization_expired=cer.expires_at is not None and now >= cer.expires_at)
        try:
            result = self._provider.authorize(req)
            outcome = k["OUTCOME_MAP"][result.outcome]
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
