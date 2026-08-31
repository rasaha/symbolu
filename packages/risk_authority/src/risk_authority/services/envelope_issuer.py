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

from ..crypto.keys import SigningKeyRecord
from ..crypto.signing import SIGNATURE_ALG
from ..domain.decision import RiskDecision
from ..domain.envelope import (
    EnvelopeBindings,
    EnvelopeConditions,
    RiskAuthorizationEnvelope,
)
from ..domain.errors import MonotonicityViolationError, RiskAuthorityError
from ..domain.scope import Scope, subset_violations
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
        key_record: SigningKeyRecord,
        revocation_state: RevocationState,
        now: datetime,
        model_digest: str = "",
        envelope_scope: Optional[Scope] = None,
        conditions: Optional[EnvelopeConditions] = None,
        ttl: timedelta = DEFAULT_ENVELOPE_TTL,
        not_before: Optional[datetime] = None,
    ) -> RiskAuthorizationEnvelope:
        """Issue a signed envelope derived monotonically from ``decision``.

        Refuses to issue if the decision does not grant authority, or if the
        requested envelope scope exceeds the decision scope.
        """

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
            ),
            key_id=key_record.key_id,
            signature_alg=SIGNATURE_ALG,
        )

        signature = key_record.signing_key.sign(unsigned.signing_payload())

        from dataclasses import replace

        return replace(unsigned, signature=signature)
