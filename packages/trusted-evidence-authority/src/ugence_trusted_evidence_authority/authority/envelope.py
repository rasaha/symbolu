"""The two signed artifacts, and the exact bytes each signature covers.

TEV-2 signs two different things, and the ADR keeps them apart:

* :class:`SignedEvidenceSubmission` — a **producer's** signature over an
  evidence item. Verifying it establishes ADR §12 **stage 2**, "does a trusted
  key's signature verify over the exact content digest?".
* :class:`SignedEvidenceVerificationReceipt` — the **verifying authority's**
  signature over a TEV-1 receipt payload. This is the ADR E-11 artifact: "a
  signed, immutable evidence-verification receipt".

Each has its own signing domain (:mod:`.profile`), so §13.3's rule that "a
signature valid in one domain must not verify in another" holds by construction,
and ADR E-3's producer/verifier separation is additionally enforced by
:class:`~.trust.TrustAnchorCapability`.

The envelope wraps the TEV-1 payload; it does not modify it
------------------------------------------------------------
:class:`SignedEvidenceVerificationReceipt` **holds** an
:class:`~..contracts.receipts.EvidenceVerificationReceiptPayload` unchanged. No
signature field was retrofitted into the payload, no payload field was added,
removed, reordered or re-typed, and the payload's canonical bytes, canonical
digest and permanently ``STRUCTURAL_UNVERIFIED`` status are exactly what TEV-1
merged. §13.3's "signature fields never participate in the content digest, but
the digest is bound **through** the signed payload" is satisfied literally: the
content digest is the payload digest, computed over payload bytes that contain
no signature, and the signature covers a frame that binds that digest *and* the
payload bytes themselves.

Nothing here is a verification result
-------------------------------------
An envelope is an **artifact**, not a verdict. It carries no ``verified`` field,
no ``trusted`` field, no ``authentic`` field and no authenticity flag of any
kind, because §10.1 and §10.5 rule that a caller-settable boolean and "a
structurally valid receipt whose signature, key, or trust anchor did not verify"
are both non-proofs. Whether an envelope is trustworthy is answered **only** by
:class:`~.reverification.SignedReceiptVerifier`, by resolving a trust anchor and
checking the signature — and that answer is computed on demand, never stored.

Possession of one of these objects establishes nothing (§8.1.3). Constructing
one establishes nothing. And per §13.2 and E-12, a verified one authorizes
nothing: not deployment, not runtime action, not policy sufficiency, not
economic value, not causal attribution.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts._validation import (
    require_digest,
    require_exact_type,
    require_identifier,
)
from ..contracts.canonical import (
    EVIDENCE_IDENTITY_DIGEST_DOMAIN,
    EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN,
    SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN,
    SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN,
    TRUSTED_EVIDENCE_CANONICALIZATION_VERSION,
    canonical_bytes,
    canonical_digest,
)
from ..contracts.errors import TrustedEvidenceContractError
from ..contracts.identity import CanonicalEvidenceIdentity
from ..contracts.reasons import TrustedEvidenceRefusalReason
from ..contracts.receipts import EvidenceVerificationReceiptPayload
from .profile import (
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
    TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN,
    TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN,
    decode_signature,
    framed_signed_input,
)

__all__ = [
    "SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1",
    "SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1",
    "SIGNED_EVIDENCE_SUBMISSION_DIGEST_DOMAIN",
    "SIGNED_RECEIPT_ENVELOPE_DIGEST_DOMAIN",
    "SignedEvidenceSubmission",
    "SignedEvidenceVerificationReceipt",
    "signed_evidence_input_bytes",
    "signed_receipt_input_bytes",
]

_R = TrustedEvidenceRefusalReason

#: Envelope schema version for a producer-signed evidence submission (§22.1).
SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1 = (
    "ugence.trusted-evidence-authority/signed-evidence-submission/v1"
)

#: Envelope schema version for the authority-signed receipt (§13.3, §22.1).
SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1 = (
    "ugence.trusted-evidence-authority/signed-receipt-envelope/v1"
)

# The two digest domains for these artifacts live in
# :mod:`..contracts.canonical` with every other domain tag — one module owns
# domain selection, so a second definition here could drift from the one the
# encoder actually frames. They are imported above and re-exported below.


def _fail(message: str, reason: TrustedEvidenceRefusalReason):
    error = TrustedEvidenceContractError(message)
    error.reason = reason
    return error


def _utf8(value: str) -> bytes:
    return value.encode("utf-8")


# --------------------------------------------------------------------------- #
# Signed-input reconstruction — public, pure, and independently reproducible
# --------------------------------------------------------------------------- #


def signed_evidence_input_bytes(
    *,
    evidence: CanonicalEvidenceIdentity,
    producer_authority_id: str,
    producer_key_id: str,
    signature_profile: str = TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
) -> bytes:
    """The exact bytes a producer's evidence signature covers.

    Eight framed elements, in this fixed order:

    ===  ==================================================================
      0  :data:`~.profile.TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN`
      1  the submission schema version
      2  the signature profile
      3  the canonicalization version
      4  the evidence-identity digest domain
      5  the producer authority id
      6  the producer key id
      7  the evidence identity's canonical bytes
    ===  ==================================================================

    Element 0 makes an evidence signature unusable as a receipt signature, and
    element 4 makes it unusable in any other digest domain. Element 7 is the
    full canonical byte sequence rather than only its digest, so the signature
    commits to the evidence itself and not merely to a hash a caller supplied.
    The evidence content digest is inside those canonical bytes (§9 row 3), so
    it is bound without being restated.

    Pure and total: same inputs, same bytes, on any machine, with no clock and
    no ambient state. A third party can reproduce this frame from the docstring
    alone.
    """

    require_exact_type(
        evidence, CanonicalEvidenceIdentity, "signed_evidence_input_bytes.evidence"
    )
    require_identifier(
        producer_authority_id, "signed_evidence_input_bytes.producer_authority_id"
    )
    require_identifier(producer_key_id, "signed_evidence_input_bytes.producer_key_id")
    _require_ratified_profile(
        signature_profile, "signed_evidence_input_bytes.signature_profile"
    )
    return framed_signed_input(
        (
            _utf8(TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN),
            _utf8(SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1),
            _utf8(signature_profile),
            _utf8(TRUSTED_EVIDENCE_CANONICALIZATION_VERSION),
            _utf8(EVIDENCE_IDENTITY_DIGEST_DOMAIN),
            _utf8(producer_authority_id),
            _utf8(producer_key_id),
            canonical_bytes(evidence),
        )
    )


def signed_receipt_input_bytes(
    *,
    payload: EvidenceVerificationReceiptPayload,
    signer_authority_id: str,
    signing_key_id: str,
    signature_profile: str = TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
) -> bytes:
    """The exact bytes an authority's receipt signature covers.

    Eleven framed elements, in this fixed order:

    ===  ==================================================================
      0  :data:`~.profile.TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN`
      1  the receipt envelope schema version
      2  the signature profile
      3  the canonicalization version
      4  the receipt-payload digest domain
      5  the signer authority id
      6  the signing key id
      7  the verification protocol id (from the payload)
      8  the verification protocol version (from the payload)
      9  the payload canonical digest, as lowercase hex
     10  the payload canonical bytes
    ===  ==================================================================

    Elements 5-8 are drawn from, or checked against, the payload, so a signature
    cannot be re-labelled with a different authority, key, or protocol without
    invalidating it — closing the authority-substitution, key-id-substitution
    and cross-protocol replay routes at the cryptographic layer rather than only
    at the field-comparison layer.

    Elements 9 and 10 bind the payload **twice**: once by digest and once by its
    full canonical bytes. The digest alone would let a second-preimage argument
    carry weight it should not have to; the bytes alone would leave the
    envelope's declared digest field unbound to the signature. Binding both
    means a swapped payload, a swapped payload digest, or a payload/digest pair
    that disagree are all signature failures, not merely field mismatches.

    Nothing self-referential is bound. The envelope digest is **not** an element
    — it is computed *over* the signature, so including it would be exactly the
    fixed-point digest ADR §13.3 and §22.6 prohibit.
    """

    require_exact_type(
        payload,
        EvidenceVerificationReceiptPayload,
        "signed_receipt_input_bytes.payload",
    )
    require_identifier(
        signer_authority_id, "signed_receipt_input_bytes.signer_authority_id"
    )
    require_identifier(signing_key_id, "signed_receipt_input_bytes.signing_key_id")
    _require_ratified_profile(
        signature_profile, "signed_receipt_input_bytes.signature_profile"
    )
    payload_bytes = canonical_bytes(payload)
    payload_digest = canonical_digest(payload)
    return framed_signed_input(
        (
            _utf8(TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN),
            _utf8(SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1),
            _utf8(signature_profile),
            _utf8(TRUSTED_EVIDENCE_CANONICALIZATION_VERSION),
            _utf8(EVIDENCE_VERIFICATION_RECEIPT_PAYLOAD_DIGEST_DOMAIN),
            _utf8(signer_authority_id),
            _utf8(signing_key_id),
            _utf8(payload.verification_protocol_id),
            _utf8(payload.verification_protocol_version),
            _utf8(payload_digest),
            payload_bytes,
        )
    )


def _require_ratified_profile(value: object, name: str) -> str:
    if value != TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1:
        raise _fail(
            f"{name} must be exactly {TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1!r}; "
            "TEV-2 ships one strict profile, and an unrecognized algorithm "
            "identifier is a refusal rather than a best-effort attempt "
            "(ADR §22.8)",
            _R.TRUSTED_EVIDENCE_SIGNATURE_PROFILE_UNSUPPORTED,
        )
    return value


# --------------------------------------------------------------------------- #
# The two immutable signed artifacts
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SignedEvidenceSubmission:
    """A producer's signature over an evidence item (ADR §12 stage 2 input).

    The evidence itself is an unchanged TEV-1
    :class:`~..contracts.identity.CanonicalEvidenceIdentity`; this type wraps it
    rather than extending it, for the same reason the receipt envelope wraps the
    receipt payload — TEV-1's shapes and digests are frozen.

    Construction validates structure and encoding only. It does **not** check
    the signature: that requires a trust anchor, which requires a resolver,
    which is :class:`~.verification.EvidenceVerificationAuthority`'s to consult.
    A constructed submission is therefore an unverified claim by a producer, and
    ADR E-3 is explicit that a producer's own assertion establishes nothing.
    """

    envelope_schema: str
    evidence: CanonicalEvidenceIdentity
    evidence_identity_digest: str
    producer_authority_id: str
    producer_key_id: str
    signature_profile: str
    signed_input_domain: str
    signature: str

    def __post_init__(self) -> None:
        if self.envelope_schema != SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1:
            raise _fail(
                "SignedEvidenceSubmission.envelope_schema must be exactly "
                f"{SIGNED_EVIDENCE_SUBMISSION_SCHEMA_V1!r}",
                _R.TRUSTED_EVIDENCE_ENVELOPE_MALFORMED,
            )
        if self.signed_input_domain != TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN:
            raise _fail(
                "SignedEvidenceSubmission.signed_input_domain must be exactly "
                f"{TRUSTED_EVIDENCE_SIGNED_EVIDENCE_INPUT_DOMAIN!r}; naming the "
                "receipt domain here would be a cross-domain substitution "
                "attempt (ADR §26.6)",
                _R.TRUSTED_EVIDENCE_ENVELOPE_MALFORMED,
            )
        require_exact_type(
            self.evidence,
            CanonicalEvidenceIdentity,
            "SignedEvidenceSubmission.evidence",
        )
        require_identifier(
            self.producer_authority_id,
            "SignedEvidenceSubmission.producer_authority_id",
        )
        require_identifier(
            self.producer_key_id, "SignedEvidenceSubmission.producer_key_id"
        )
        _require_ratified_profile(
            self.signature_profile, "SignedEvidenceSubmission.signature_profile"
        )
        require_digest(
            self.evidence_identity_digest,
            "SignedEvidenceSubmission.evidence_identity_digest",
        )
        # Recomputed, never believed: a caller-declared digest that disagrees
        # with the artifact it names is the substitution route this closes.
        actual = canonical_digest(self.evidence)
        if actual != self.evidence_identity_digest:
            raise _fail(
                "SignedEvidenceSubmission.evidence_identity_digest does not "
                "equal the digest of the evidence it carries; the digest is "
                "always recomputed from the artifact and never taken on trust",
                _R.TRUSTED_EVIDENCE_CONTENT_DIGEST_MISMATCH,
            )
        decode_signature(self.signature, "SignedEvidenceSubmission.signature")

    @property
    def signature_encoding(self) -> str:
        """The one ratified encoding. A read-only property, not a caller field."""

        return TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1

    def signed_input_bytes(self) -> bytes:
        """Reconstruct the exact bytes this submission's signature must cover."""

        return signed_evidence_input_bytes(
            evidence=self.evidence,
            producer_authority_id=self.producer_authority_id,
            producer_key_id=self.producer_key_id,
            signature_profile=self.signature_profile,
        )

    def signature_bytes(self) -> bytes:
        """Decode the signature from its one canonical encoding."""

        return decode_signature(self.signature, "SignedEvidenceSubmission.signature")

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over."""

        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the complete submission, signature included.

        An audit handle for "this exact submission", **not** the content digest
        of §13.3 — that is the evidence's own digest, computed over bytes which
        contain no signature. This digest is never a signing input, so nothing
        here is self-referential (§22.5, §22.6).
        """

        return canonical_digest(self)


@dataclass(frozen=True)
class SignedEvidenceVerificationReceipt:
    """The ADR E-11 artifact: a signed, immutable evidence-verification receipt.

    ============================  =========================================
    ``envelope_schema``           §22.1 — the envelope's own version
    ``payload``                   the **unmodified** TEV-1 receipt payload
    ``payload_canonical_digest``  §13.3 — recomputed, never believed
    ``signature_profile``         DD-9 — the one ratified profile
    ``signed_input_domain``       §26.6 — which byte space was signed
    ``signer_authority_id``       §9 row 14 — who signed
    ``signing_key_id``            §9 row 14 — with which exact key
    ``signature``                 one canonical encoding, 128 hex chars
    ============================  =========================================

    **No issuance-time field.** ADR §13.1.5 requires "an explicit
    timezone-aware ``verified_at``", and the payload already carries exactly
    that; §9 rows 5 and 6 are the two ratified instants and neither is an
    envelope-issuance time. Minting a third instant would fix a coordinate the
    ADR has not ratified, so the envelope binds none.

    **No mutable map, no free-form metadata, no extension field.** Every field
    is a scalar or a frozen contract, and the canonical encoder rejects mappings
    outright, so there is nowhere for an unbound coordinate to hide.

    **No authenticity flag.** There is no ``verified``, ``trusted``,
    ``authentic`` or ``admitted`` field, and no property that returns one. The
    only route to a trust answer is
    :class:`~.reverification.SignedReceiptVerifier`, which resolves a trust
    anchor and checks the signature. §13.3: "a receipt that is unsigned, or
    whose signature does not verify against a configured trust anchor, is
    **not** a receipt. There is no 'trusted but unsigned' state."

    Immutability and append-only re-verification are §13.1.7: "re-verification
    issues a **new** receipt; receipts are immutable and append-only". This
    dataclass is frozen and nothing in the package mutates one.
    """

    envelope_schema: str
    payload: EvidenceVerificationReceiptPayload
    payload_canonical_digest: str
    signature_profile: str
    signed_input_domain: str
    signer_authority_id: str
    signing_key_id: str
    signature: str

    def __post_init__(self) -> None:
        if self.envelope_schema != SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1:
            raise _fail(
                "SignedEvidenceVerificationReceipt.envelope_schema must be "
                f"exactly {SIGNED_RECEIPT_ENVELOPE_SCHEMA_V1!r}",
                _R.TRUSTED_EVIDENCE_ENVELOPE_MALFORMED,
            )
        if self.signed_input_domain != TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN:
            raise _fail(
                "SignedEvidenceVerificationReceipt.signed_input_domain must be "
                f"exactly {TRUSTED_EVIDENCE_SIGNED_RECEIPT_INPUT_DOMAIN!r}; "
                "naming the evidence domain here would be a cross-domain "
                "substitution attempt (ADR §26.6)",
                _R.TRUSTED_EVIDENCE_ENVELOPE_MALFORMED,
            )
        require_exact_type(
            self.payload,
            EvidenceVerificationReceiptPayload,
            "SignedEvidenceVerificationReceipt.payload",
        )
        require_identifier(
            self.signer_authority_id,
            "SignedEvidenceVerificationReceipt.signer_authority_id",
        )
        require_identifier(
            self.signing_key_id, "SignedEvidenceVerificationReceipt.signing_key_id"
        )
        _require_ratified_profile(
            self.signature_profile,
            "SignedEvidenceVerificationReceipt.signature_profile",
        )
        require_digest(
            self.payload_canonical_digest,
            "SignedEvidenceVerificationReceipt.payload_canonical_digest",
        )
        actual = canonical_digest(self.payload)
        if actual != self.payload_canonical_digest:
            raise _fail(
                "SignedEvidenceVerificationReceipt.payload_canonical_digest does "
                "not equal the digest of the payload it carries; the digest is "
                "always recomputed from the payload and never taken on trust, so "
                "a swapped payload and a swapped digest are both caught here "
                "before any signature is even considered",
                _R.TRUSTED_EVIDENCE_PAYLOAD_DIGEST_MISMATCH,
            )
        decode_signature(
            self.signature, "SignedEvidenceVerificationReceipt.signature"
        )

    @property
    def signature_encoding(self) -> str:
        """The one ratified encoding. A read-only property, not a caller field."""

        return TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1

    def signed_input_bytes(self) -> bytes:
        """Reconstruct the exact bytes this receipt's signature must cover.

        Rebuilt from the envelope's own fields and the payload it carries — the
        independent-verification requirement of §13.3, available to anyone
        holding the envelope and this module.
        """

        return signed_receipt_input_bytes(
            payload=self.payload,
            signer_authority_id=self.signer_authority_id,
            signing_key_id=self.signing_key_id,
            signature_profile=self.signature_profile,
        )

    def signature_bytes(self) -> bytes:
        """Decode the signature from its one canonical encoding."""

        return decode_signature(
            self.signature, "SignedEvidenceVerificationReceipt.signature"
        )

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`envelope_digest` is computed over."""

        return canonical_bytes(self)

    def envelope_digest(self) -> str:
        """Deterministic sha-256 over the complete envelope, signature included.

        An audit handle for "this exact signed artifact". It is **not** the
        content digest §13.3 excludes signatures from — that is
        :attr:`payload_canonical_digest`, computed over payload bytes which
        contain no signature. This digest is never a signing input and is not
        stored in the envelope, so it is not self-referential and introduces no
        fixed point (§22.5, §22.6).
        """

        return canonical_digest(self)
