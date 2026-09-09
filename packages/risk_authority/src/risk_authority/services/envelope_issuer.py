"""Envelope issuance and the monotonicity validator (spec §12, user brief §9–10).

The envelope is *derived* from the decision. It cannot carry authority the
decision did not grant: :func:`validate_envelope_subset` proves
``Scope_envelope ⊆ Scope_decision`` on every dimension before signing, and the
issuer refuses to sign otherwise (spec §29 envelope monotonicity, AC-04). This
is one of the strongest invariants in the package and has an explicit test.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..crypto.keys import SigningKeyRecord, key_window_valid_at
from ..crypto.signing import SIGNATURE_ALG
from ..domain.decision import RiskDecision
from ..domain.envelope import (
    ArtifactBinding,
    EnvelopeBindings,
    EnvelopeConditions,
    RiskAuthorizationEnvelope,
)
from ..domain.errors import MonotonicityViolationError, RiskAuthorityError
from ..domain.scope import Scope, subset_violations
from .envelope_signer import EnvelopeSignerPort, signer_window
from .revocation import RevocationState

__all__ = ["EnvelopeIssuer", "validate_envelope_subset", "DEFAULT_ENVELOPE_TTL"]

# Spec Appendix C: 30 minutes default, risk-tier configurable.
DEFAULT_ENVELOPE_TTL = timedelta(minutes=30)


def validate_envelope_subset(envelope_scope: Scope, decision_scope: Scope) -> None:
    """Raise :class:`MonotonicityViolationError` if the envelope is broader."""

    violations = subset_violations(envelope_scope, decision_scope)
    if violations:
        raise MonotonicityViolationError(violations)


class EnvelopeIssuer:
    """Build and sign RiskAuthorizationEnvelopes from binding decisions."""

    def __init__(self, *, issuer: str = "ugence-risk-authority") -> None:
        self._issuer = issuer

    def issue(
        self,
        *,
        envelope_id: str,
        decision: RiskDecision,
        audience: str,
        subject: str,
        model_id: str,
        session_id: str,
        nonce: str,
        key_record: Optional[SigningKeyRecord] = None,
        revocation_state: RevocationState,
        now: datetime,
        model_digest: str = "",
        envelope_scope: Optional[Scope] = None,
        conditions: Optional[EnvelopeConditions] = None,
        ttl: timedelta = DEFAULT_ENVELOPE_TTL,
        not_before: Optional[datetime] = None,
        signer: Optional[EnvelopeSignerPort] = None,
        artifact_bindings: tuple[ArtifactBinding, ...] = (),
    ) -> RiskAuthorizationEnvelope:
        """Issue a signed envelope derived monotonically from ``decision``.

        Refuses to issue if the decision does not grant authority, or if the
        requested envelope scope exceeds the decision scope. Exactly one of
        ``key_record`` (legacy in-process key) or ``signer`` (Phase 5
        :class:`EnvelopeSignerPort`) must be supplied; the issuer computes the
        signing payload either way and the signer never sees other bytes.
        """

        if (key_record is None) == (signer is None):
            raise RiskAuthorityError("issue requires exactly one of key_record or signer")

        if not decision.grants_authority:
            raise RiskAuthorityError(
                f"decision {decision.decision_id} outcome {decision.outcome.value} "
                "does not grant authority; no envelope may be issued"
            )

        # Time binding (spec §29): an envelope may never be minted from a decision
        # whose own validity window has elapsed. Without this an expired decision
        # would be re-minted into fresh runtime authority with a new TTL.
        if decision.expires_at is not None and now > decision.expires_at:
            raise RiskAuthorityError(
                f"decision {decision.decision_id} expired at "
                f"{decision.expires_at.isoformat()}; no envelope may be issued from "
                "an expired decision"
            )

        # Default to the exact decision scope; a caller may narrow it.
        scope = (envelope_scope or decision.scope).normalized()
        validate_envelope_subset(scope, decision.scope.normalized())

        epoch = revocation_state.current_epoch(decision.tenant_id)

        unsigned = RiskAuthorizationEnvelope(
            envelope_id=envelope_id,
            issuer=self._issuer,
            audience=audience,
            subject=subject,
            tenant_id=decision.tenant_id,
            session_id=session_id,
            nonce=nonce,
            issued_at=now,
            not_before=not_before or now,
            expires_at=now + ttl,
            decision_id=decision.decision_id,
            model_id=model_id,
            scope=scope,
            conditions=conditions or EnvelopeConditions(),
            bindings=EnvelopeBindings(
                workflow_ir_digest=decision.workflow_ir_digest,
                evidence_snapshot_digest=decision.evidence_snapshot_digest,
                model_digest=model_digest or decision.model_digest,
                authority_epoch=epoch,
                artifact_bindings=tuple(artifact_bindings),
            ),
            key_id=signer.key_id if signer is not None else key_record.key_id,
            signature_alg=signer.signature_alg if signer is not None else SIGNATURE_ALG,
        )

        # Key validity window, enforced independently of the verifier (issue #1398,
        # F-G item 2). An expired or not-yet-valid key must not be able to sign, and this
        # check must not rely on some later verification catching it: the issuer is where
        # the signing key is actually held. ``now`` is the injected trusted instant, the
        # same one stamped into ``issued_at`` above.
        #
        # Both paths are covered. The in-process ``key_record`` carries its own window;
        # an external ``signer`` declares one through the additive
        # ``WindowedEnvelopeSignerPort`` capability, and a signer that declares none is
        # unbounded-valid, so no existing implementation changes behavior.
        if signer is not None:
            signer_not_before, signer_not_after = signer_window(signer)
            if not key_window_valid_at(
                now, not_before=signer_not_before, not_after=signer_not_after
            ):
                raise RiskAuthorityError(
                    f"signer key {signer.key_id!r} is outside its validity window "
                    f"[{signer_not_before}, {signer_not_after}) at {now}")
        elif not key_record.is_valid_at(now):
            raise RiskAuthorityError(
                f"signing key {key_record.key_id!r} is outside its validity window "
                f"[{key_record.not_before}, {key_record.not_after}) at {now}")

        payload = unsigned.signing_payload()
        if signer is not None:
            signature = signer.sign(payload)
            if not isinstance(signature, (bytes, bytearray)) or not signature:
                raise RiskAuthorityError("signer returned an empty or non-bytes signature")
            signature = bytes(signature)
        else:
            signature = key_record.signing_key.sign(payload)

        from dataclasses import replace

        return replace(unsigned, signature=signature)
