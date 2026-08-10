"""Reuse the canonical Risk Authority enforcement path (RA-4.5 §15).

The composition engine does **not** reimplement envelope verification or the
exact-action matcher. It invokes Risk Authority's own
``ReferenceActionGate`` — the RA-owned cryptographic enforcer that composes the
offline :class:`EnvelopeVerifier` (signature / time / revocation / epoch /
tenant / session) with exact canonical-action scope matching (tenant, actor,
model, purpose, tools±, data±, destination, amount, conditions).

The result is translated into a :class:`RiskAuthorityMachineResult`, the
integration-layer view of the machine-authority verdict. Translation is
**lossless-downward**: an RA ``AUTHORIZED`` becomes ``ALLOW``; anything else
becomes ``DENY`` with the RA reason codes preserved. An enforcement path that
cannot run at all (missing verifier inputs, kernel exception) becomes ``ERROR``
— fail closed, never an authorization.

Note the terminology split (plan §1.4): ``ReferenceActionGate`` here is Risk
Authority's *cryptographic enforcer*, distinct from the ``ugence-actiongate-
provider`` *policy* engine composed additively in
:mod:`ugence_risk_authority_runtime.actiongate_adapter`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from risk_authority.crypto import KeyRing
from risk_authority.domain import (
    ActionGateDecision,
    CanonicalAction,
    RiskAuthorizationEnvelope,
)
from risk_authority.integrations import ActionGatePort, ReferenceActionGate, RuntimeIdentity
from risk_authority.services.revocation import RevocationState

from .contracts import (
    ReasonCode,
    RiskAuthorityDisposition,
    RiskAuthorityMachineResult,
)

__all__ = ["RiskAuthorityEnforcer"]

try:  # pragma: no cover - version presence is environment-dependent
    from risk_authority import __version__ as _RA_VERSION
except Exception:  # pragma: no cover
    _RA_VERSION = ""


class RiskAuthorityEnforcer:
    """Invoke the canonical RA enforcement path and translate the verdict.

    A production deployment can pass any :class:`ActionGatePort` implementation
    (the RA-owned reference gate is the default). The port owns envelope
    verification and exact-action matching; this class only adapts its output
    into the composition vocabulary — it adds no authority of its own.
    """

    def __init__(self, gate: Optional[ActionGatePort] = None) -> None:
        self._gate = gate or ReferenceActionGate()

    def enforce(
        self,
        *,
        authorization_id: str,
        envelope: Optional[RiskAuthorizationEnvelope],
        action: CanonicalAction,
        identity: RuntimeIdentity,
        key_ring: KeyRing,
        revocation_state: RevocationState,
        now: datetime,
        satisfied_conditions: frozenset[str] = frozenset(),
    ) -> RiskAuthorityMachineResult:
        """Return the RA machine-authority verdict for the exact action."""

        if envelope is None:
            # No signed capability exists → no machine authority basis → DENY.
            return RiskAuthorityMachineResult(
                disposition=RiskAuthorityDisposition.DENY,
                reason_codes=(ReasonCode.RA_ENVELOPE_INVALID.value,),
                action_digest=action.digest,
                action=action,
                source_version=_RA_VERSION,
                raw_reason_codes=("unknown envelope",),
            )

        try:
            authorization = self._gate.authorize(
                authorization_id=authorization_id,
                envelope=envelope,
                action=action,
                identity=identity,
                key_ring=key_ring,
                revocation_state=revocation_state,
                now=now,
                satisfied_conditions=satisfied_conditions,
            )
        except Exception as exc:  # noqa: BLE001 - fail closed on any enforcer error
            # The RA enforcement path could not be evaluated. This is NOT an
            # authoritative negative about the request; it is a missing/failed
            # authority input → ERROR (never coerced to ALLOW).
            return RiskAuthorityMachineResult(
                disposition=RiskAuthorityDisposition.ERROR,
                reason_codes=(ReasonCode.RA_UNAVAILABLE.value,),
                envelope_id=envelope.envelope_id,
                action_digest=action.digest,
                action=action,
                scope=envelope.scope,
                expires_at=envelope.expires_at,
                source_version=_RA_VERSION,
                raw_reason_codes=(f"{type(exc).__name__}: {exc}",),
            )

        if authorization.decision is ActionGateDecision.AUTHORIZED:
            return RiskAuthorityMachineResult(
                disposition=RiskAuthorityDisposition.ALLOW,
                reason_codes=(ReasonCode.RA_ALLOW.value,),
                envelope_id=envelope.envelope_id,
                action_digest=action.digest,
                action=action,
                scope=envelope.scope,
                expires_at=envelope.expires_at,
                source_version=_RA_VERSION,
                raw_reason_codes=tuple(authorization.reason_codes),
            )

        # Any non-AUTHORIZED RA verdict is an authoritative DENY. Preserve the RA
        # reason codes so the audit trail shows exactly which check failed
        # (signature, expiry, revocation, epoch, identity, scope, amount, …).
        return RiskAuthorityMachineResult(
            disposition=RiskAuthorityDisposition.DENY,
            reason_codes=(ReasonCode.RA_DENY.value,),
            envelope_id=envelope.envelope_id,
            action_digest=action.digest,
            scope=envelope.scope,
            expires_at=envelope.expires_at,
            source_version=_RA_VERSION,
            raw_reason_codes=tuple(authorization.reason_codes),
        )
