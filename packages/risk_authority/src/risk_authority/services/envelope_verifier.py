"""Offline envelope verification for the hot path (spec §15, §27, §32).

Verification is pure and offline: it needs only the envelope, a
:class:`KeyRing` of cached verification keys and the local
:class:`RevocationState`. No network, no policy-text parsing. Every failure is
a DENY reason (fail closed). This is the signature/binding half of ActionGate;
the action-matching half lives in ``integrations.actiongate``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ..crypto.keys import KeyRing
from ..domain.envelope import RiskAuthorizationEnvelope
from .revocation import RevocationState

__all__ = ["EnvelopeVerification", "EnvelopeVerifier"]


@dataclass(frozen=True)
class EnvelopeVerification:
    valid: bool
    reasons: tuple[str, ...] = ()

    @classmethod
    def ok(cls) -> "EnvelopeVerification":
        return cls(True, ())

    @classmethod
    def deny(cls, *reasons: str) -> "EnvelopeVerification":
        return cls(False, tuple(reasons))


class EnvelopeVerifier:
    """Verify an envelope's signature, time window, bindings and revocation."""

    def verify(
        self,
        *,
        envelope: RiskAuthorizationEnvelope,
        key_ring: KeyRing,
        revocation_state: RevocationState,
        now: datetime,
        expected_tenant: Optional[str] = None,
        expected_audience: Optional[str] = None,
        expected_session: Optional[str] = None,
    ) -> EnvelopeVerification:
        reasons: list[str] = []

        # 1. Signature / key validity.
        #
        # The key's own validity window is checked BEFORE the signature (issue #1398,
        # F-G item 2), matching the Policy Authority key path. A signature that verifies
        # under an expired or not-yet-valid key is not a weaker pass — it is no pass at
        # all, so there is nothing to gain by computing it first.
        #
        # The key interval and the envelope window in step 3 below now share one shape:
        # half-open, inclusive lower bound, exclusive upper bound. They were briefly
        # different — see ``crypto.keys`` for the superseded reasoning.
        key_record = key_ring.resolve_record(envelope.key_id)
        if key_record is None:
            return EnvelopeVerification.deny(f"unknown key_id {envelope.key_id!r}")
        if not key_record.is_valid_at(now):
            return EnvelopeVerification.deny(
                f"key {envelope.key_id!r} is outside its validity window "
                f"[{key_record.not_before}, {key_record.not_after})")
        verify_key = key_record.verify_key
        if not verify_key.verify(envelope.signing_payload(), envelope.signature):
            # A bad signature is terminal — nothing else in the body is trustworthy.
            return EnvelopeVerification.deny("invalid signature")

        # 2. Tenant / audience / session binding.
        if expected_tenant is not None and envelope.tenant_id != expected_tenant:
            reasons.append(
                f"tenant mismatch: {envelope.tenant_id!r} != {expected_tenant!r}"
            )
        if expected_audience is not None and envelope.audience != expected_audience:
            reasons.append(
                f"audience mismatch: {envelope.audience!r} != {expected_audience!r}"
            )
        if expected_session is not None and envelope.session_id != expected_session:
            reasons.append(
                f"session mismatch: {envelope.session_id!r} != {expected_session!r}"
            )

        # 3. Time window (nbf / exp), half-open ``[not_before, expires_at)``. Must stay
        # equivalent to ``RiskAuthorizationEnvelope.is_temporally_valid``; the conformance
        # suite asserts the two agree at every boundary instant rather than by inspection.
        if now < envelope.not_before:
            reasons.append("envelope not yet valid (nbf)")
        if now >= envelope.expires_at:
            reasons.append("envelope expired (exp)")

        # 4. Revocation / authority epoch.
        revoked = revocation_state.is_revoked(
            tenant_id=envelope.tenant_id,
            envelope_id=envelope.envelope_id,
            subject_id=envelope.subject,
            model_id=envelope.model_id,
            envelope_epoch=envelope.bindings.authority_epoch,
        )
        if revoked is not None:
            reasons.append(revoked)

        if reasons:
            return EnvelopeVerification.deny(*reasons)
        return EnvelopeVerification.ok()
