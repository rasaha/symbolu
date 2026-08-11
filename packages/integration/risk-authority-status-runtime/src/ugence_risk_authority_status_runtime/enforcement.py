"""Status-aware enforcement + last-mile re-verification (RA-6 §8, §15).

Two read-only compositions around the **existing** offline verifier/gate — RA-6
adds no authority, mints no artifact, and never writes:

* :class:`StatusAwareActionGate` — wraps the leaf's ``ReferenceActionGate`` (the
  RA cryptographic enforcer) with the RA-6 tiered-staleness policy. It applies
  the freshness gate FIRST (uninitialized / stale-beyond-bound ⇒ DENY before any
  envelope trust is extended), then runs the unchanged gate against the
  snapshot's ``RevocationState``. This preserves the existing envelope checks
  (signature / nbf / expiry / tenant / session / epoch / targeted revocation)
  and *adds* the initialized/stale distinctions the hot path previously lacked.

* :func:`make_pre_effect_recheck` — the last-mile TOCTOU close (RA-6 §8). For a
  **consequential/irreversible** action it re-runs the offline authority-status
  check against the freshest snapshot immediately before the commit point. It is
  *validity re-verification, not reauthorization*: no RA reasoning, no lease, no
  nonce, no polling. The returned callable matches the Agent Runtime's neutral
  ``authority_recheck`` seam so it plugs into ``validate_clearance`` without the
  runtime importing Risk Authority.

Both are READ ONLY: they never advance an epoch, revoke, reassess, or mint
authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional, Tuple

from risk_authority.crypto.keys import KeyRing
from risk_authority.domain.actions import ActionAuthorization, CanonicalAction
from risk_authority.domain.enums import ActionGateDecision, RiskClass
from risk_authority.domain.envelope import RiskAuthorizationEnvelope
from risk_authority.integrations.actiongate import (
    ActionGatePort,
    ReferenceActionGate,
    RuntimeIdentity,
)
from risk_authority.integrations.authority_lifecycle import AuthorityStatusReader
from risk_authority.services.authority_status import (
    ALLOW_WITH_BOUNDED_STALE_STATUS,
    DENY,
    AuthorityStatus,
    StalenessPolicy,
    check_authority_status,
    evaluate_status_freshness,
)

__all__ = [
    "StatusAwareGateResult",
    "StatusAwareActionGate",
    "PreEffectContext",
    "make_pre_effect_recheck",
]


@dataclass(frozen=True)
class StatusAwareGateResult:
    """A gate result annotated with the RA-6 authority-status verdict."""

    decision: ActionGateDecision
    status: AuthorityStatus
    reason_codes: Tuple[str, ...]
    authorization: Optional[ActionAuthorization]

    @property
    def bounded_stale(self) -> bool:
        return self.status.outcome == ALLOW_WITH_BOUNDED_STALE_STATUS


class StatusAwareActionGate:
    """Compose the RA cryptographic enforcer with RA-6 tiered staleness (read-only)."""

    def __init__(
        self,
        reader: AuthorityStatusReader,
        *,
        policy: StalenessPolicy,
        gate: Optional[ActionGatePort] = None,
    ) -> None:
        self._reader = reader
        self._policy = policy
        self._gate = gate or ReferenceActionGate()

    def authorize(
        self,
        *,
        authorization_id: str,
        envelope: RiskAuthorizationEnvelope,
        action: CanonicalAction,
        identity: RuntimeIdentity,
        key_ring: KeyRing,
        tier: Optional[RiskClass],
        now: datetime,
        satisfied_conditions: frozenset[str] = frozenset(),
    ) -> StatusAwareGateResult:
        snapshot = self._reader.snapshot(tenant_id=envelope.tenant_id)

        # 1. Freshness gate FIRST: uninitialized / stale-beyond-bound ⇒ DENY,
        #    fail closed, without extending any trust to the envelope. This is the
        #    distinction the bare RevocationState hot path could not make (R-1).
        freshness = evaluate_status_freshness(
            snapshot=snapshot,
            tenant_id=envelope.tenant_id,
            tier=tier,
            now=now,
            policy=self._policy,
        )
        if freshness.outcome == DENY:
            return StatusAwareGateResult(
                decision=ActionGateDecision.DENIED,
                status=freshness,
                reason_codes=freshness.reasons,
                authorization=None,
            )

        # 2. Unchanged RA enforcement against the snapshot's RevocationState:
        #    signature / nbf / expiry / tenant / session / epoch / targeted
        #    revocation + exact-action scope matching (RA-4.5 semantics intact).
        authorization = self._gate.authorize(
            authorization_id=authorization_id,
            envelope=envelope,
            action=action,
            identity=identity,
            key_ring=key_ring,
            revocation_state=snapshot.revocation_state,
            now=now,
            satisfied_conditions=satisfied_conditions,
        )
        return StatusAwareGateResult(
            decision=authorization.decision,
            status=freshness,
            reason_codes=tuple(authorization.reason_codes),
            authorization=authorization,
        )


@dataclass(frozen=True)
class PreEffectContext:
    """What the last-mile recheck needs to re-verify a consequential action.

    Resolved from the runtime's proposal/evaluation by a deployment-supplied
    resolver. Carries the signed envelope and the case-derived risk tier (the
    envelope schema is frozen, so the tier is supplied out of band from the case
    record — unknown ⇒ CRITICAL/fail-closed, per the freshness policy).
    """

    envelope: RiskAuthorizationEnvelope
    tier: Optional[RiskClass]
    expected_tenant: Optional[str] = None
    expected_session: Optional[str] = None
    expected_audience: Optional[str] = None


def make_pre_effect_recheck(
    *,
    reader: AuthorityStatusReader,
    policy: StalenessPolicy,
    key_ring: KeyRing,
    clock: Callable[[], datetime],
    resolve: Callable[[object, object], Optional[PreEffectContext]],
    sync: Optional[Callable[[], None]] = None,
) -> Callable[[object, object, float], Tuple[bool, Tuple[str, ...]]]:
    """Build a neutral ``authority_recheck`` callable for the Agent Runtime seam.

    The returned function signature is ``(evaluation, proposal, now_float) ->
    (ok, reason_codes)`` — exactly what ``validate_clearance`` invokes immediately
    before provider invocation. It re-runs :func:`check_authority_status` at the
    commit-point clock against the freshest snapshot:

      * ``resolve`` maps the neutral (evaluation, proposal) to the signed envelope
        + tier; if it returns ``None`` the action is not authority-bound and the
        recheck is a pass-through (``ok=True``) — non-consequential low-latency
        behavior is preserved for anything outside RA-6's scope.
      * ``sync`` (optional) refreshes the local cache from the store before the
        read, so a revocation/epoch-advance that landed after the initial CLEAR
        is observed at the commit point (closes the last-mile window; §8).

    It performs no reauthorization and mints nothing. On any status DENY it fails
    closed with the RA-6 reason codes.
    """

    def _recheck(evaluation: object, proposal: object, now_float: float) -> Tuple[bool, Tuple[str, ...]]:
        ctx = resolve(evaluation, proposal)
        if ctx is None:
            return True, ()  # not an authority-bound consequential action
        if sync is not None:
            sync()
        snapshot = reader.snapshot(tenant_id=ctx.envelope.tenant_id)
        status = check_authority_status(
            envelope=ctx.envelope,
            key_ring=key_ring,
            snapshot=snapshot,
            tier=ctx.tier,
            now=clock(),
            policy=policy,
            expected_tenant=ctx.expected_tenant,
            expected_session=ctx.expected_session,
            expected_audience=ctx.expected_audience,
        )
        if status.outcome == DENY:
            return False, ("RA6_PRE_EFFECT_AUTHORITY_INVALID",) + tuple(status.reasons)
        return True, ()

    return _recheck
