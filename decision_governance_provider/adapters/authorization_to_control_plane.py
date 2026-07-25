"""Adapter: AuthorizationProvider → kernel ActionControlPlanePort.

Implements the frozen ``ActionControlPlanePort`` by extracting a neutral
:class:`AuthorizationContext` from the kernel action request + CER, delegating to
an :class:`AuthorizationProvider`, and mapping its :class:`AuthorizationVerdict`
onto the kernel ``ActionAuthorizationResponse``. The kernel's
``ActionAuthorizationService`` remains the authorization *engine*; the provider
supplies the decision through this seam.
"""

from __future__ import annotations

from datetime import timedelta

from decision_governance.api.common import Clock, IdFactory, new_id, utc_now
from decision_governance.api.contracts import (
    ActionAuthorizationResponse,
    AuthorizationOutcome as KernelAuthorizationOutcome,
)

from ..contracts import AuthorizationContext, AuthorizationProvider


class AuthorizationProviderControlPlaneAdapter:
    """Implements ``ActionControlPlanePort`` over an :class:`AuthorizationProvider`."""

    def __init__(
        self,
        provider: AuthorizationProvider,
        *,
        validity: timedelta = timedelta(hours=1),
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._provider = provider
        self._validity = validity
        self._new_id = id_factory
        self._clock = clock

    def authorize(self, action_request, cer) -> ActionAuthorizationResponse:
        now = self._clock()
        context = AuthorizationContext(
            action_type=action_request.action_type,
            parameters=dict(action_request.requested_parameters or {}),
            tenant_id=action_request.tenant_id,
            subject_refs=tuple(getattr(s, "ref_id", str(s))
                               for s in action_request.subject_refs),
            correlation_id=cer.correlation_id,
            policy_refs=tuple(f"{r.ref_id}:{r.version}"
                              for r in cer.policy_context.policy_refs),
            cer_expired=cer.expires_at is not None and cer.expires_at < now)
        verdict = self._provider.authorize(context)
        outcome = KernelAuthorizationOutcome(verdict.outcome.value)
        return ActionAuthorizationResponse(
            authorization_id=self._new_id("authz"),
            action_request_id=action_request.action_request_id,
            cer_id=cer.cer_id,
            outcome=outcome,
            constraints=verdict.constraints,
            obligations=verdict.obligations,
            authorized_at=now,
            expires_at=None if outcome is KernelAuthorizationOutcome.EXPIRED
            else now + self._validity,
            control_plane_ref=f"provider:{self._provider.metadata().name}",
            reason_codes=(outcome.value,) if not verdict.reason else (outcome.value, verdict.reason),
            policy_versions=tuple(f"{r.ref_id}:{r.version}"
                                  for r in cer.policy_context.policy_refs),
            correlation_id=cer.correlation_id)
