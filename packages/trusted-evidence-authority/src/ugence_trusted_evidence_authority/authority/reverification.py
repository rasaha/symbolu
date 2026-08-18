"""Independent re-verification of a signed receipt envelope (ADR §13.3).

ADR §13.3 requires that "independent verification must be possible: a third
party holding the receipt and the public verification functions can recompute
the digest and check the signature **without authority internals**". This module
is that third party's tool, and it lives up to the word *independent*:

* it holds **no signing key** and has no method that produces a signature;
* it holds **no** verification authority, no protocol and no determination;
* it never consults the issuer, and never trusts anything the envelope asserts
  about itself;
* it reconstructs the signed bytes from the envelope's own fields and the
  payload it carries, resolves the named anchor at an exact coordinate, and
  checks the signature.

Every input it needs is public: the envelope, a trust-anchor resolver, an
evaluation instant, and the caller's expected coordinates.

Success is computed, never stored
---------------------------------
:class:`ReceiptVerification` has no settable ``verified`` field. Its
:attr:`~ReceiptVerification.verified` is a read-only property derived from
:attr:`~ReceiptVerification.outcome`, and the only code that can build a
``VERIFIED`` outcome is the one path in :meth:`SignedReceiptVerifier.verify`
that reaches an actual ``Ed25519`` signature check returning ``True``. ADR §10.1
and §10.5 forbid consumers from treating a caller-settable boolean, or a
structurally valid receipt whose key did not verify, as proof; here neither
exists to be mistaken for one.

Current trust, and the retroactive-revocation rule
--------------------------------------------------
The delegated question — whether re-verification asks "was this trusted when
signed?" or "is this trusted now?" — is settled by ADR §13.3 itself: "key
revocation is checked **at verification time**; a receipt signed by a key that
was later revoked is **not silently honoured**."

TEV-2 therefore answers **only the current question**, and answers it
conservatively:

* the key's validity window, its revocation, its disabled state and the
  receipt's own validity interval are **all** evaluated at the caller-supplied
  ``evaluated_at``, never at the payload's ``verified_at``;
* a key revoked as of ``evaluated_at`` cannot establish current trust, whatever
  instant the signature was produced at. A previously-valid receipt therefore
  stops verifying once its key is revoked — a signature is not grandfathered.

The refusal keeps enough typed evidence to be explained rather than merely
asserted: :attr:`ReceiptVerification.refusal_reason` names
``TRUSTED_EVIDENCE_KEY_REVOKED``, and the result carries the evaluation instant
and the resolved coordinate, so a reader can see the receipt was signed before
the revocation and is refused because trust is being asked about *now*.

**Historical re-verification is deliberately not offered.** Asking "was this
trusted at some past instant T" needs a ratified as-of-T trust semantics — which
anchor set was configured then, which revocations were known then — and no
merged clause defines one for evidence. ADR §17.1's historical resolution is a
*Benchmark Registry* concept and is BR-2's, not TEV-2's. Offering a
plausible-looking historical answer would resolve a question the ADR retains
elsewhere, so the API offers none rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from ..contracts._validation import (
    require_aware_datetime,
    require_canonical_str,
    require_exact_type,
    require_identifier,
)
from ..contracts.enums import DeclaredVerificationOutcome, EvidenceTrustStage
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.reasons import TrustedEvidenceRefusalReason
from .envelope import SignedEvidenceVerificationReceipt
from .trust import (
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorResolution,
    TrustAnchorResolverPort,
)

__all__ = [
    "ReceiptVerificationOutcome",
    "ReceiptVerification",
    "SignedReceiptVerifier",
]

_R = TrustedEvidenceRefusalReason


def _fail(message: str, reason: TrustedEvidenceRefusalReason):
    error = TrustedEvidenceContractError(message)
    error.reason = reason
    return error


class ReceiptVerificationOutcome(str, Enum):
    """The result of independently re-verifying a signed receipt envelope.

    Two members, for the same reason
    :class:`~.verification.EvidenceAdmissionOutcome` has two: E-9 admits no
    third state, §11 makes indeterminacy a refusal, and a success-shaped
    ``UNKNOWN``/``PARTIAL``/``PENDING``/``BEST_EFFORT`` member would be read
    optimistically by exactly the consumer §10 is written to protect.

    A distinct type from ``EvidenceAdmissionOutcome`` on purpose: "the authority
    admitted this evidence" and "this signature verifies under a trusted key
    right now" are different findings, and a distinct enum makes substituting
    one for the other a type error rather than a plausible mistake.
    """

    #: The signature verified under a resolved, entitled, in-window, unrevoked
    #: trust anchor, and every coordinate the caller required matched.
    #: **This is not an authorization** (§13.2, E-12).
    VERIFIED = "VERIFIED"
    #: Fail-closed, with exactly one stable typed reason (E-9).
    REFUSED = "REFUSED"


@dataclass(frozen=True)
class ReceiptVerification:
    """The typed outcome of one independent re-verification.

    Carries the evaluation instant and the resolved coordinate alongside the
    outcome, so a refusal can be *explained* — "refused at this instant, under
    this coordinate, for this reason" — rather than merely reported. That is
    what lets a caller distinguish "this was never valid" from "this was valid
    and its key has since been revoked" without the package having to soften
    the refusal.

    There is no ``verified`` field. :attr:`verified` is a read-only property
    over :attr:`outcome`, and a caller cannot construct a ``VERIFIED`` outcome
    that a signature check did not produce: constructing this object requires
    the private verification token, which the curated API does not export.
    """

    outcome: ReceiptVerificationOutcome
    evaluated_at: datetime
    coordinate: TrustAnchorCoordinate
    envelope_digest: str
    payload_canonical_digest: str
    refusal_reason: Optional[TrustedEvidenceRefusalReason] = None
    trust_anchor_digest: str = ""
    verification_token: object = None

    def __post_init__(self) -> None:
        if self.verification_token is not _VERIFICATION_TOKEN:
            raise _fail(
                "ReceiptVerification cannot be constructed directly. A "
                "verification outcome is produced only by "
                "SignedReceiptVerifier.verify(); a caller-built VERIFIED result "
                "would be exactly the manufactured verification ADR §8.1.5 "
                "prohibits and §10.5 enumerates as a non-proof",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        require_exact_type(
            self.outcome, ReceiptVerificationOutcome, "ReceiptVerification.outcome"
        )
        require_aware_datetime(self.evaluated_at, "ReceiptVerification.evaluated_at")
        require_exact_type(
            self.coordinate, TrustAnchorCoordinate, "ReceiptVerification.coordinate"
        )
        require_identifier(self.envelope_digest, "ReceiptVerification.envelope_digest")
        require_identifier(
            self.payload_canonical_digest, "ReceiptVerification.payload_canonical_digest"
        )
        require_canonical_str(
            self.trust_anchor_digest,
            "ReceiptVerification.trust_anchor_digest",
            allow_empty=True,
        )
        verified = self.outcome is ReceiptVerificationOutcome.VERIFIED
        if verified and self.refusal_reason is not None:
            raise _fail(
                "a VERIFIED receipt verification carries a refusal reason",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        if not verified and self.refusal_reason is None:
            raise _fail(
                "a REFUSED receipt verification must carry a stable typed "
                "reason (ADR E-9)",
                _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
            )
        if self.refusal_reason is not None:
            require_exact_type(
                self.refusal_reason,
                TrustedEvidenceRefusalReason,
                "ReceiptVerification.refusal_reason",
            )

    @property
    def verified(self) -> bool:
        """Whether the signature verified under a currently-trusted anchor.

        Derived from :attr:`outcome`, never stored and never caller-settable.

        ``True`` means, and means only: a trust anchor resolved at the exact
        coordinate, was entitled to issue receipts, was in its validity window,
        was not disabled, was not revoked at :attr:`evaluated_at`, and its
        public key verified the reconstructed signature frame; and the payload
        digest, the caller's expected coordinates and the receipt's own validity
        all agreed.

        It does **not** mean the evidence is true, that a claim is economically
        valuable, that attribution holds, or that anything is authorized. ADR
        §13.2 and E-12: a receipt "never authorizes deployment, never authorizes
        runtime action, never proves a claim is economically valuable, never
        proves causal attribution". A verified receipt is a verified receipt.
        """

        return self.outcome is ReceiptVerificationOutcome.VERIFIED

    @property
    def established_trust_stages(self) -> tuple:
        """The ADR §12 stages a *verified* envelope establishes about itself.

        A verified envelope establishes that the receipt is structurally sound
        and cryptographically authentic under a currently-trusted authority key
        — stages 1 and 2 **of the receipt**. It is empty for a refusal.

        It deliberately does **not** re-assert the stages the *payload* declares
        about the *evidence*. Those were established by the verifying authority
        at ``verified_at``, are recorded in
        ``payload.declared_cleared_stages``, and are now attested by a signature
        rather than re-derived: this verifier never saw the evidence. §12 stage
        6 is absent here as everywhere, and always will be.
        """

        if not self.verified:
            return ()
        return (
            EvidenceTrustStage.STRUCTURALLY_CONSTRUCTIBLE,
            EvidenceTrustStage.CRYPTOGRAPHICALLY_AUTHENTIC,
        )

    # No ``canonical_bytes`` / ``canonical_digest``, for the same reason
    # :class:`~.verification.EvidenceVerificationDetermination` has none: this
    # is an in-process finding carrying a private token, and the encoder's
    # total-field-inclusion rule admits no exception. The auditable artifact is
    # :class:`~.audit.EvidenceVerificationAuditRecord`.


#: The private verification token — see :class:`ReceiptVerification`.
_VERIFICATION_TOKEN = object()


class SignedReceiptVerifier:
    """Independently re-verify a signed receipt envelope. Holds no key.

    Wired with a :class:`~.trust.TrustAnchorResolverPort` and nothing else. Pass
    :class:`~.trust.DenyAllTrustAnchorDirectory` where no trust is configured
    and every re-verification denies, which is ADR E-8's production default made
    explicit rather than implicit.
    """

    __slots__ = ("_trust_anchors",)

    def __init__(self, *, trust_anchors: TrustAnchorResolverPort) -> None:
        if not hasattr(trust_anchors, "resolve"):
            raise _fail(
                "SignedReceiptVerifier.trust_anchors must implement "
                "TrustAnchorResolverPort.resolve; ADR E-8 makes an unconfigured "
                "verifier a denial, not an absent check — pass "
                "DenyAllTrustAnchorDirectory() to deny explicitly",
                _R.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED,
            )
        object.__setattr__(self, "_trust_anchors", trust_anchors)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"SignedReceiptVerifier is immutable; cannot set {name!r}. "
            "Re-pointing a configured verifier's trust anchors would bypass "
            "the composition root (ADR E-5)."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"SignedReceiptVerifier is immutable; cannot delete {name!r}"
        )

    def verify(
        self,
        envelope: SignedEvidenceVerificationReceipt,
        *,
        evaluated_at: datetime,
        expected_tenant_id: str = "",
        expected_assessment_context_ref: str = "",
        expected_subject_ref: str = "",
        expected_assessed_system_binding_digest: str = "",
        expected_assessment_purpose_ref: str = "",
        expected_usage_scope_ref: str = "",
        expected_verification_protocol_id: str = "",
        expected_verification_protocol_version: str = "",
        expected_evidence_content_digest: str = "",
    ) -> ReceiptVerification:
        """Re-verify ``envelope`` for current trust at ``evaluated_at``.

        The ordered checks, each fail-closed with one stable typed reason:

         1. **envelope structure** — the ratified schema, domain and profile;
         2. **payload digest** — recomputed from the payload and compared;
         3. **signed-input reconstruction** — rebuilt from the envelope's own
            fields, never from anything the caller supplies;
         4. **trust-anchor resolution** — exact
            ``(signer_authority_id, signing_key_id, RECEIPT_ISSUANCE)``;
         5. **capability** — a producing key can never satisfy this (E-3);
         6. **profile agreement** — anchor profile versus envelope profile;
         7. **key lifecycle at** ``evaluated_at`` — revoked, disabled, not yet
            valid, expired;
         8. **signature** — the one load-bearing cryptographic gate;
         9. **payload/envelope coherence** — the payload's own authority, key
            and outcome agree with the envelope that carries it;
        10. **receipt validity at** ``evaluated_at`` — half-open, §13.1.6;
        11. **caller coordinates** — every non-empty ``expected_*`` argument.

        Every ``expected_*`` argument defaults to ``""`` meaning *not checked*.
        That default is a deliberate, documented weakening for the case where a
        caller genuinely holds only the envelope — the "third party" of §13.3 —
        and it is why a verified result is **not** a scope decision. A consumer
        binding evidence to its own tenant, context, subject, system, purpose or
        scope must pass those coordinates; §26.5's replay detection is only
        mechanical for coordinates someone actually asserts. The README and the
        probe both state this in terms, and the anti-replay tests exercise both
        the checked and unchecked forms.
        """

        require_exact_type(
            envelope,
            SignedEvidenceVerificationReceipt,
            "SignedReceiptVerifier.verify.envelope",
        )
        require_aware_datetime(
            evaluated_at, "SignedReceiptVerifier.verify.evaluated_at"
        )
        payload = envelope.payload
        coordinate = TrustAnchorCoordinate(
            authority_id=envelope.signer_authority_id,
            key_id=envelope.signing_key_id,
            capability=TrustAnchorCapability.RECEIPT_ISSUANCE,
        )
        envelope_digest = envelope.envelope_digest()
        payload_digest = payload.canonical_digest()

        def refuse(reason, anchor_digest: str = "") -> ReceiptVerification:
            return ReceiptVerification(
                outcome=ReceiptVerificationOutcome.REFUSED,
                evaluated_at=evaluated_at,
                coordinate=coordinate,
                envelope_digest=envelope_digest,
                payload_canonical_digest=payload_digest,
                refusal_reason=reason,
                trust_anchor_digest=anchor_digest,
                verification_token=_VERIFICATION_TOKEN,
            )

        # 2. payload digest — recomputed, never believed. (Structure, step 1,
        #    was enforced at construction: an envelope cannot exist malformed.)
        if envelope.payload_canonical_digest != payload_digest:
            return refuse(_R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH)

        # 4. trust-anchor resolution at the exact coordinate.
        resolution = self._trust_anchors.resolve(coordinate)
        if type(resolution) is not TrustAnchorResolution:
            return refuse(_R.TRUSTED_EVIDENCE_VERIFIER_UNAVAILABLE)
        if resolution.anchor is None:
            return refuse(resolution.refusal_reason)
        anchor = resolution.anchor
        anchor_digest = anchor.canonical_digest()

        # 5. capability — E-3 enforced structurally, re-checked explicitly.
        if anchor.capability is not TrustAnchorCapability.RECEIPT_ISSUANCE:
            return refuse(_R.TRUSTED_EVIDENCE_KEY_CAPABILITY_MISMATCH, anchor_digest)

        # 6. profile agreement — no negotiation, no downgrade.
        if anchor.signature_profile != envelope.signature_profile:
            return refuse(
                _R.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED, anchor_digest
            )

        # 7. key lifecycle at the caller's instant — revocation checked first.
        lifecycle_refusal = anchor.lifecycle_refusal_at(evaluated_at)
        if lifecycle_refusal is not None:
            return refuse(lifecycle_refusal, anchor_digest)

        # 8. the signature — the one load-bearing cryptographic gate.
        if not anchor.verification_key().verify(
            envelope.signed_input_bytes(), envelope.signature_bytes()
        ):
            return refuse(_R.TRUSTED_EVIDENCE_SIGNATURE_INVALID, anchor_digest)

        # 9. payload/envelope coherence. The signature already binds these, so
        #    a mismatch here is unreachable for an intact envelope — it is
        #    checked anyway so a future change to the signed frame cannot
        #    silently open a re-labelling route.
        if payload.verifier_authority_id != envelope.signer_authority_id:
            return refuse(_R.TRUSTED_EVIDENCE_AUTHORITY_MISMATCH, anchor_digest)
        if payload.verifier_key_id != envelope.signing_key_id:
            return refuse(_R.TRUSTED_EVIDENCE_KEY_ID_MISMATCH, anchor_digest)
        if payload.declared_outcome is not DeclaredVerificationOutcome.DECLARED_ADMITTED:
            return refuse(
                _R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED, anchor_digest
            )

        # 10. the receipt's own half-open validity at evaluated_at (§13.1.6).
        if (
            payload.receipt_valid_from is not None
            and evaluated_at < payload.receipt_valid_from
        ):
            return refuse(_R.TRUSTED_EVIDENCE_RECEIPT_NOT_YET_VALID, anchor_digest)
        if (
            payload.receipt_valid_to is not None
            and evaluated_at >= payload.receipt_valid_to
        ):
            return refuse(_R.TRUSTED_EVIDENCE_RECEIPT_EXPIRED, anchor_digest)

        # 11. the caller's own coordinates, where supplied.
        scope = payload.scope
        for expected, actual, reason in (
            (expected_tenant_id, scope.tenant_id, _R.TRUSTED_EVIDENCE_TENANT_MISMATCH),
            (
                expected_assessment_context_ref,
                scope.assessment_context_ref,
                _R.TRUSTED_EVIDENCE_CONTEXT_MISMATCH,
            ),
            (
                expected_subject_ref,
                scope.subject_ref,
                _R.TRUSTED_EVIDENCE_SUBJECT_MISMATCH,
            ),
            (
                expected_assessed_system_binding_digest,
                scope.assessed_system_binding_digest,
                _R.TRUSTED_EVIDENCE_SYSTEM_BINDING_MISMATCH,
            ),
            (
                expected_assessment_purpose_ref,
                scope.assessment_purpose_ref,
                _R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
            ),
            (
                expected_usage_scope_ref,
                scope.usage_scope_ref,
                _R.TRUSTED_EVIDENCE_PURPOSE_SCOPE_MISMATCH,
            ),
            (
                expected_evidence_content_digest,
                payload.evidence_content_digest,
                _R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH,
            ),
            (
                expected_verification_protocol_id,
                payload.verification_protocol_id,
                _R.TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED,
            ),
            (
                expected_verification_protocol_version,
                payload.verification_protocol_version,
                _R.TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH,
            ),
        ):
            if expected and expected != actual:
                return refuse(reason, anchor_digest)

        return ReceiptVerification(
            outcome=ReceiptVerificationOutcome.VERIFIED,
            evaluated_at=evaluated_at,
            coordinate=coordinate,
            envelope_digest=envelope_digest,
            payload_canonical_digest=payload_digest,
            trust_anchor_digest=anchor_digest,
            verification_token=_VERIFICATION_TOKEN,
        )

    def __repr__(self) -> str:
        return "SignedReceiptVerifier(trust_anchors=<configured>)"
