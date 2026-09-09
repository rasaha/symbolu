"""Reuse the canonical Risk Authority enforcement path (RA-4.5 §15).

The composition engine does **not** reimplement envelope verification or the
exact-action matcher. It invokes an RA-owned :class:`ActionGatePort` — the
cryptographic enforcer that composes the offline :class:`EnvelopeVerifier`
(signature / time / revocation / epoch / tenant / session) with exact
canonical-action scope matching (tenant, actor, model, purpose, tools±, data±,
destination, amount, conditions). ``ReferenceActionGate`` is one such port, for
conformance use only; as of 0.2.0 it is never reached implicitly.

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
from .verified import VerifiedRiskAuthorityResult, verify_and_bind

__all__ = ["RiskAuthorityEnforcer", "EnforcerConfigurationError"]


class EnforcerConfigurationError(Exception):
    """The enforcer was constructed without an explicit, posture-declared gate.

    Replaces the pre-0.2.0 silent ``gate or ReferenceActionGate()`` default (ADR §8/D-E).
    A warning was deliberately rejected: it would have preserved the ambiguity it warns
    about, and the ambiguity is the defect.
    """

try:  # pragma: no cover - version presence is environment-dependent
    from risk_authority import __version__ as _RA_VERSION
except Exception:  # pragma: no cover
    _RA_VERSION = ""


class RiskAuthorityEnforcer:
    """Invoke the canonical RA enforcement path and translate the verdict.

    The gate is **explicit as of 0.2.0** — there is no implicit reference default
    (ADR §8/D-E). Build one through :meth:`production` (which refuses a reference
    gate and requires ``is_production_authoritative=True``) or :meth:`reference`
    (labelled conformance use, never production). The port owns envelope
    verification and exact-action matching; this class only adapts its output
    into the composition vocabulary — it adds no authority of its own.

    Two methods, two purposes: :meth:`enforce` returns the bare
    :class:`RiskAuthorityMachineResult` and is the pre-0.2.0 shape, kept for
    reference and non-authoritative composition. :meth:`derive` runs the gate and
    then binds its answer to the verified envelope, returning the
    :class:`VerifiedRiskAuthorityResult` the production composition path requires.
    """

    def __init__(self, gate: ActionGatePort, *, production: bool = False) -> None:
        """Construct with an explicit gate. Prefer :meth:`production` or :meth:`reference`.

        Direct construction is retained so an existing external caller that already passes
        a gate keeps working; the removed behavior is the *implicit* one. ``production``
        defaults to ``False``, so a direct construction is never silently production-grade.
        """

        if gate is None:
            raise EnforcerConfigurationError(
                "RiskAuthorityEnforcer requires an explicit ActionGatePort as of 0.2.0. "
                "Use RiskAuthorityEnforcer.production(gate=...) for production enforcement "
                "or RiskAuthorityEnforcer.reference() for conformance/test use. The former "
                "implicit ReferenceActionGate default was never production-eligible.")
        self._gate = gate
        self._production = bool(production)

    # ------------------------------------------------------------------ factories
    @classmethod
    def production(cls, *, gate: ActionGatePort) -> "RiskAuthorityEnforcer":
        """A production enforcer. Fails closed on any reference-grade gate (ADR §8/D-E).

        Mirrors the refusals ``ActionAdmissionSeam.production`` already applies in the RA
        0.8 kernel, deliberately without adopting that seam (ADR §3).
        """

        if isinstance(gate, ReferenceActionGate):
            raise EnforcerConfigurationError(
                "production enforcer refuses ReferenceActionGate and any subclass of it; "
                "the reference gate is a conformance component, never production enforcement")
        if getattr(gate, "is_production_authoritative", False) is not True or not callable(
            getattr(gate, "authorize", None)
        ):
            raise EnforcerConfigurationError(
                "production enforcer requires an ActionGatePort declaring "
                "is_production_authoritative=True; silence is refusal")
        return cls(gate, production=True)

    @classmethod
    def reference(cls, *, gate: Optional[ActionGatePort] = None) -> "RiskAuthorityEnforcer":
        """A labelled conformance enforcer over the in-package reference gate. Never production.

        Everything it derives is stamped ``production=False`` and is refused by the
        verified production composition path.
        """

        return cls(gate if gate is not None else ReferenceActionGate(), production=False)

    @property
    def is_production(self) -> bool:
        return self._production

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

    # ------------------------------------------------------------------ D-A derivation
    def derive(
        self,
        *,
        authorization_id: str,
        envelope: RiskAuthorizationEnvelope,
        action: CanonicalAction,
        identity: RuntimeIdentity,
        key_ring: KeyRing,
        revocation_state: RevocationState,
        now: datetime,
        satisfied_conditions: frozenset[str] = frozenset(),
    ) -> "VerifiedRiskAuthorityResult":
        """Run the gate, then verify and bind its answer to the envelope (ADR §8/D-A).

        This is the only route to a :class:`VerifiedRiskAuthorityResult`. ``now`` is the
        composition root's trusted instant; nothing here reads a clock.

        Unlike :meth:`enforce`, this does not swallow a gate exception into an ``ERROR``
        verdict — a gate that raises produced no authorization to bind, so there is nothing
        to derive from and the caller must handle it. Composition-level fail-closed
        behavior for that case lives in the composition path, not here.
        """

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
        return verify_and_bind(
            envelope=envelope,
            authorization=authorization,
            action=action,
            identity=identity,
            key_ring=key_ring,
            revocation_state=revocation_state,
            now=now,
            source_version=_RA_VERSION,
            production=self._production,
        )
