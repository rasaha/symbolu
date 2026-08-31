"""Receipt issuance — the only route from an admission to a signature.

ADR §8 role 4 is "evidence-verification receipt issuer — **TAP**, under a
configured authority key", and it "must never also be the producer of the
evidence it attests". :class:`ReceiptIssuer` is that role, and it is a separate
object from the verification authority for the reason §8 gives: "no row may
absorb another".

What issuance may act on
------------------------
Exactly one thing: an
:class:`~.verification.EvidenceVerificationDetermination` whose outcome is
``ADMITTED``. Because a determination can only be built by
:class:`~.verification.EvidenceVerificationAuthority` — its constructor demands
a private token the curated API does not export — there is no route by which a
caller reaches issuance with a hand-made success.

The issuer additionally re-checks what it was handed, rather than trusting the
determination's own summary:

* the outcome is ``ADMITTED`` and a payload is present;
* the payload's ``verifier_authority_id`` and ``verifier_key_id`` are the
  signer's own advertised coordinates — a receipt may not be signed by a key it
  does not name (§9 row 14);
* the payload's protocol id and version are the determination's;
* the payload's request digest is the determination's.

Every one of those is already true for a determination this package produced.
They are re-checked anyway, because ADR §8.1 requires the authority to
"independently re-check" rather than assume, and because a future signer
substituted at the composition root is exactly the case where an assumption
would be wrong.

Issuance is not verification
----------------------------
A signature proves that a key signed a frame. It does **not** prove the key was
trusted: that is :class:`~.reverification.SignedReceiptVerifier`'s question, and
this module deliberately cannot answer it — it holds no trust-anchor resolver
and never resolves one. §13.3: "there is no 'trusted but unsigned' state", and
symmetrically there is no *signed-therefore-trusted* state either.
"""

from __future__ import annotations

from ..contracts._validation import require_exact_type
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.reasons import TrustedEvidenceRefusalReason
from .envelope import (
    SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
    SignedEvidenceVerificationReceipt,
    signed_receipt_input_bytes,
)
from .profile import TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN, decode_signature
from .signing import _SIGNING_INPUT_TOKEN, ReceiptSignerPort, ReceiptSigningInput
from .verification import (
    EvidenceAdmissionOutcome,
    EvidenceVerificationDetermination,
)

__all__ = ["ReceiptIssuer"]

_R = TrustedEvidenceRefusalReason


def _fail(message: str, reason: TrustedEvidenceRefusalReason):
    error = TrustedEvidenceContractError(message)
    error.reason = reason
    return error


class ReceiptIssuer:
    """Turns an admitted determination into the ADR E-11 signed receipt.

    Wired at the composition root with a :class:`~.signing.ReceiptSignerPort`.
    It performs no verification, resolves no trust anchor, and admits nothing:
    handed a refused determination it raises rather than issuing anything,
    because §13.3's "no unsigned 'trusted' receipts" has a mirror — TEV-2 mints
    no receipt for something it did not admit.
    """

    __slots__ = ("_signer",)

    def __init__(self, *, signer: ReceiptSignerPort) -> None:
        for name in (
            "signer_authority_id",
            "signing_key_id",
            "signature_profile",
            "sign_receipt",
        ):
            if not hasattr(signer, name):
                raise _fail(
                    "ReceiptIssuer.signer must implement ReceiptSignerPort "
                    f"(missing {name!r})",
                    _R.TRUSTED_EVIDENCE_MALFORMED_CONTRACT,
                )
        object.__setattr__(self, "_signer", signer)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"ReceiptIssuer is immutable; cannot set {name!r}. Swapping the "
            "signer of a configured issuer would re-point an already-trusted "
            "issuance path (ADR E-5)."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"ReceiptIssuer is immutable; cannot delete {name!r}")

    @property
    def signer_authority_id(self) -> str:
        return self._signer.signer_authority_id

    @property
    def signing_key_id(self) -> str:
        return self._signer.signing_key_id

    def issue(
        self, determination: EvidenceVerificationDetermination
    ) -> SignedEvidenceVerificationReceipt:
        """Sign an admitted determination's payload and return the envelope.

        Raises for a refused determination, for a determination whose payload
        names coordinates the configured signer cannot answer for, and for a
        signer that returns a malformed signature. It never returns an
        unverified-but-plausible envelope: the return type exists only when a
        real signature was produced over the reconstructed frame.

        The signature returned by the signer is decoded before the envelope is
        built, so a signer that returns uppercase hex, base64, a truncated
        string or a non-string fails here rather than producing an envelope that
        would fail obscurely at re-verification.
        """

        require_exact_type(
            determination,
            EvidenceVerificationDetermination,
            "ReceiptIssuer.issue.determination",
        )
        if determination.outcome is not EvidenceAdmissionOutcome.ADMITTED:
            raise _fail(
                "ReceiptIssuer refuses to sign a "
                f"{determination.outcome.value} determination; a receipt "
                "attests an admission, and TEV-2 issues no artifact for a "
                "refusal (ADR E-11, §13.3)",
                _R.TRUSTED_EVIDENCE_VERIFICATION_NOT_PERFORMED,
            )
        payload = determination.receipt_payload
        signer = self._signer
        if payload.verifier_authority_id != signer.signer_authority_id:
            raise _fail(
                "the admitted payload names verifier authority "
                f"{payload.verifier_authority_id!r} but the configured signer "
                f"speaks for {signer.signer_authority_id!r}; a receipt may not "
                "be signed by an authority it does not name (ADR §9 row 14)",
                _R.TRUSTED_EVIDENCE_AUTHORITY_MISMATCH,
            )
        if payload.verifier_key_id != signer.signing_key_id:
            raise _fail(
                "the admitted payload names verifier key "
                f"{payload.verifier_key_id!r} but the configured signer holds "
                f"{signer.signing_key_id!r}; a receipt may not be signed by a "
                "key it does not name (ADR §9 row 14)",
                _R.TRUSTED_EVIDENCE_KEY_ID_MISMATCH,
            )
        if payload.verification_protocol_id != determination.verification_protocol_id:
            raise _fail(
                "the admitted payload and its determination name different "
                "verification protocols",
                _R.TRUSTED_EVIDENCE_PROTOCOL_UNSUPPORTED,
            )
        if (
            payload.verification_protocol_version
            != determination.verification_protocol_version
        ):
            raise _fail(
                "the admitted payload and its determination name different "
                "verification protocol versions",
                _R.TRUSTED_EVIDENCE_PROTOCOL_VERSION_MISMATCH,
            )
        if (
            payload.verification_request_digest
            != determination.verification_request_digest
        ):
            raise _fail(
                "the admitted payload and its determination name different "
                "verification requests",
                _R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH,
            )

        profile = signer.signature_profile
        signed_input = signed_receipt_input_bytes(
            payload=payload,
            signer_authority_id=signer.signer_authority_id,
            signing_key_id=signer.signing_key_id,
            signature_profile=profile,
        )
        signature = signer.sign_receipt(
            ReceiptSigningInput(
                signed_input=signed_input,
                signer_authority_id=signer.signer_authority_id,
                signing_key_id=signer.signing_key_id,
                signature_profile=profile,
                issuance_token=_SIGNING_INPUT_TOKEN,
            )
        )
        decode_signature(signature, "ReceiptIssuer.issue.signature")
        return SignedEvidenceVerificationReceipt(
            envelope_schema=SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1,
            payload=payload,
            payload_canonical_digest=payload.canonical_digest(),
            signature_profile=profile,
            signed_input_domain=TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
            signer_authority_id=signer.signer_authority_id,
            signing_key_id=signer.signing_key_id,
            signature=signature,
        )

    def __repr__(self) -> str:
        return (
            "ReceiptIssuer(authority="
            f"{self._signer.signer_authority_id!r}, "
            f"key={self._signer.signing_key_id!r})"
        )
