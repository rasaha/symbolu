"""Provider-neutral control-plane port + an offline deterministic adapter.

The domain depends only on :class:`ActionControlPlanePort` — never on a concrete
ActionGate SDK. Authorization is the AI Control Plane's job: given a prepared
request and its CER, decide *whether the proposed action may execute under current
runtime controls*. It returns an authorization decision; it never executes.

The offline adapter is fully deterministic (rule-based, no randomness, no network)
so the whole suite runs without external services.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional, Protocol, runtime_checkable

from ..common import Clock, IdFactory, new_id, utc_now
from .action_request import ActionRequest
from .authorization import ActionAuthorizationResponse
from .cer import ContextEnvelopeRecord
from .status import AuthorizationOutcome


@runtime_checkable
class ActionControlPlanePort(Protocol):
    """The single seam between Decision Governance and the AI Control Plane."""

    def authorize(
        self,
        action_request: ActionRequest,
        cer: ContextEnvelopeRecord,
    ) -> ActionAuthorizationResponse:
        ...


class OfflineDeterministicControlPlane:
    """A deterministic, offline control-plane adapter for tests and development.

    Rules (evaluated in order, no randomness):

    * a CER already past ``expires_at`` → ``EXPIRED``;
    * ``action_type`` in ``denied_action_types`` → ``DENIED``;
    * ``action_type`` in ``indeterminate_action_types`` → ``INDETERMINATE``;
    * ``action_type`` in ``constrained_action_types`` → ``AUTHORIZED_WITH_CONSTRAINTS``
      carrying the configured constraints/obligations;
    * otherwise → ``AUTHORIZED``.
    """

    def __init__(
        self,
        *,
        denied_action_types: frozenset[str] = frozenset(),
        constrained_action_types: frozenset[str] = frozenset(),
        indeterminate_action_types: frozenset[str] = frozenset(),
        constraints: tuple[str, ...] = ("rate_limited",),
        obligations: tuple[str, ...] = ("log_to_audit",),
        validity: timedelta = timedelta(hours=1),
        control_plane_ref: str = "offline-cp",
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._denied = denied_action_types
        self._constrained = constrained_action_types
        self._indeterminate = indeterminate_action_types
        self._constraints = constraints
        self._obligations = obligations
        self._validity = validity
        self._ref = control_plane_ref
        self._new_id = id_factory
        self._clock = clock

    def authorize(
        self,
        action_request: ActionRequest,
        cer: ContextEnvelopeRecord,
    ) -> ActionAuthorizationResponse:
        now = self._clock()  # deterministic when an explicit clock is injected
        outcome, constraints, obligations = self._classify(action_request, cer, now)
        return ActionAuthorizationResponse(
            authorization_id=self._new_id("authz"),
            action_request_id=action_request.action_request_id,
            cer_id=cer.cer_id, outcome=outcome, constraints=constraints,
            obligations=obligations, authorized_at=now,
            expires_at=None if outcome is AuthorizationOutcome.EXPIRED
            else now + self._validity,
            control_plane_ref=self._ref,
            reason_codes=(outcome.value,),
            policy_versions=tuple(
                f"{r.ref_id}:{r.version}" for r in cer.policy_context.policy_refs),
            correlation_id=cer.correlation_id)

    def _classify(self, request: ActionRequest, cer: ContextEnvelopeRecord,
                  now: datetime):
        if cer.expires_at is not None and cer.expires_at < now:
            return AuthorizationOutcome.EXPIRED, (), ()
        if request.action_type in self._denied:
            return AuthorizationOutcome.DENIED, (), ()
        if request.action_type in self._indeterminate:
            return AuthorizationOutcome.INDETERMINATE, (), ()
        if request.action_type in self._constrained:
            return (AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS,
                    self._constraints, self._obligations)
        return AuthorizationOutcome.AUTHORIZED, (), self._obligations
