"""Budget authority — a procurement control plane behind the kernel port.

``BudgetAuthorityAdapter`` implements the kernel :class:`ActionControlPlanePort`.
The kernel's :class:`ActionAuthorizationService` remains the authorization
*engine*; this adapter supplies the procurement *policy* it consults — spending
limits, an approval threshold requiring conditions, and supplier/budget
restrictions — expressed entirely through the existing port. There is no
procurement-specific authorization engine.

Deterministic and offline: the decision is a pure function of the action
request, its CER, and the configured limits.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ugence_decision_authority.api.common import Clock, IdFactory, new_id, utc_now
from ugence_decision_authority.api.contracts import ActionAuthorizationResponse, AuthorizationOutcome


class BudgetAuthorityAdapter:
    """Procurement authorization policy expressed through the control-plane port.

    Rules (evaluated in order, no randomness):

    * CER already past ``expires_at`` → ``EXPIRED``;
    * a restricted supplier or budget → ``DENIED``;
    * ``amount`` above ``hard_limit`` → ``DENIED``;
    * ``amount`` above ``approval_threshold`` →
      ``AUTHORIZED_WITH_CONSTRAINTS`` (senior-approval obligation attached);
    * otherwise → ``AUTHORIZED``.

    ``amount`` is read from the action request's ``requested_parameters``
    (missing/non-numeric ⇒ treated as ``0``).
    """

    def __init__(
        self,
        *,
        hard_limit: int = 10_000_000,
        approval_threshold: int = 1_000_000,
        restricted_suppliers: frozenset[str] = frozenset(),
        restricted_budgets: frozenset[str] = frozenset(),
        constraints: tuple[str, ...] = ("senior_approval_required",),
        obligations: tuple[str, ...] = ("log_to_audit", "notify_finance"),
        validity: timedelta = timedelta(hours=1),
        control_plane_ref: str = "procurement-budget-authority",
        id_factory: IdFactory = new_id,
        clock: Clock = utc_now,
    ) -> None:
        self._hard_limit = hard_limit
        self._approval_threshold = approval_threshold
        self._restricted_suppliers = restricted_suppliers
        self._restricted_budgets = restricted_budgets
        self._constraints = constraints
        self._obligations = obligations
        self._validity = validity
        self._ref = control_plane_ref
        self._new_id = id_factory
        self._clock = clock

    def authorize(self, action_request, cer) -> ActionAuthorizationResponse:
        now = self._clock()
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

    def _classify(self, request, cer, now: datetime):
        if cer.expires_at is not None and cer.expires_at < now:
            return AuthorizationOutcome.EXPIRED, (), ()
        params = request.requested_parameters or {}
        supplier = params.get("supplier_id", "")
        budget = params.get("budget_id", "")
        if supplier in self._restricted_suppliers or budget in self._restricted_budgets:
            return AuthorizationOutcome.DENIED, (), ()
        amount = self._amount(params)
        if amount > self._hard_limit:
            return AuthorizationOutcome.DENIED, (), ()
        if amount > self._approval_threshold:
            return (AuthorizationOutcome.AUTHORIZED_WITH_CONSTRAINTS,
                    self._constraints, self._obligations)
        return AuthorizationOutcome.AUTHORIZED, (), self._obligations

    @staticmethod
    def _amount(params) -> int:
        raw = params.get("amount", "0")
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0
