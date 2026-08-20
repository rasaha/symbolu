"""``ProducerAttestationV2`` — a producer's signature over facts a verifier can reconcile.

Phase 5A's v1 attestation binds the recommendation digest and nothing about *who* the
recommendation is for. That is enough to detect a swapped recommendation and not enough to
detect a swapped **tenant** or **subject**: a genuine attestation minted for one workload
would, under v1's payload, be equally valid alongside a candidate reconciled for another.

v2 closes that by binding the identity facts into the signed bytes:

============================  ==========================================================
``schema_version``            this contract's tag — domain separation, bound first
``signing_purpose``           what the key was used for, never a policy-signing purpose
``producer_id``               who claims to have produced the recommendation
``issuer``                    whose key signed it, and the authority half of the anchor
                              coordinate a verifier resolves
``producer_key_id``           the exact key coordinate a verifier resolves
``signature_algorithm``       the closed admitted algorithm identifier
``signature_profile``         the one ratified Ed25519 profile
``signature_encoding``        the one ratified canonical lowercase base16 encoding
``tenant_id``                 the tenant the recommendation was produced for
``subject_id``                the workload the recommendation was produced for
``subject_type``              the D-4 ratified subject type
``recommendation_id``         the producer's label for the recommendation
``recommendation_digest``     the unkeyed content digest of the recommendation
``issued_at``                 a carried fact — this package reads no clock
============================  ==========================================================

``issuer`` and ``producer_id`` are **separate signed fields**, and the anchor is resolved by
``issuer``. They are deliberately not required to *differ in value*: Phase 5A's ratified
design explicitly permits a producer to sign its own output ("a self-signature is a claim of
origin, not a grant of trust"), and forcing inequality would refuse that ratified case. What
separation buys is that the identity a verifier resolves a key under is stated explicitly and
covered by the signature, rather than being inferred from the producer's own name.

The ``signature`` is **excluded** from the payload it covers — a signature cannot cover
itself. ``signing_payload_digest`` is likewise excluded, and is re-derived at construction
rather than believed, so a self-inconsistent attestation cannot exist as an object.

What holding one of these means
-------------------------------
Nothing, on its own. It is a *claim*: someone asserts a signature over these facts.
Whether the signature is valid, whether the key was configured, entitled, in-window and
unrevoked, and whether the facts match the candidate it travels beside are all decided by
:mod:`.verification` and by nothing else. There is no ``verified`` field to set, no trust
state to assign, and no method on this class that consults a key.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar, Mapping

from ugence_trusted_evidence_authority import decode_signature

from .canonical import (
    canonical_bytes,
    canonical_digest,
    require_aware_utc,
    require_canonical_digest,
    require_canonical_identifier,
)
from .errors import ProducerAttestationCanonicalFieldError as _FieldError
from .errors import ProducerAttestationExactTypeError as _ExactTypeError
from .identifiers import (
    PRODUCER_ATTESTATION_SIGNATURE_ALGORITHM,
    PRODUCER_ATTESTATION_SIGNATURE_ENCODING,
    PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
    PRODUCER_ATTESTATION_V2_SCHEMA_VERSION,
    PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
    SUPPORTED_V2_SIGNATURE_ALGORITHMS,
    SUPPORTED_V2_SIGNING_PURPOSES,
)
from .outcomes import ProducerAuthenticityOutcome as _Outcome

__all__ = ["ProducerAttestationV2", "producer_attestation_signing_payload"]


def producer_attestation_signing_payload(
    *,
    producer_id: str,
    issuer: str,
    producer_key_id: str,
    tenant_id: str,
    subject_id: str,
    subject_type: str,
    recommendation_id: str,
    recommendation_digest: str,
    issued_at: datetime,
    signing_purpose: str,
    signature_algorithm: str,
    signature_profile: str,
    signature_encoding: str,
) -> dict[str, Any]:
    """Build the canonical signing payload from **already validated** components.

    This is the single definition of what a v2 producer signature covers. Both the minting
    path and the verification path call it, so there is exactly one payload shape in the
    package and no second implementation to drift. The verifier calls it with values it
    took from the Phase 5A candidate — not with values it took from the attestation — which
    is what makes its byte comparison an independent recomputation rather than a tautology.
    """

    return {
        "schema_version": PRODUCER_ATTESTATION_V2_SCHEMA_VERSION,
        "signing_purpose": signing_purpose,
        "producer_id": producer_id,
        "issuer": issuer,
        "producer_key_id": producer_key_id,
        "signature_algorithm": signature_algorithm,
        "signature_profile": signature_profile,
        "signature_encoding": signature_encoding,
        "tenant_id": tenant_id,
        "subject_id": subject_id,
        "subject_type": subject_type,
        "recommendation_id": recommendation_id,
        "recommendation_digest": recommendation_digest,
        "issued_at": issued_at,
    }


@dataclass(frozen=True)
class ProducerAttestationV2:
    """A structurally valid, cryptographically **unverified** producer attestation.

    Immutable and exact-typed. Construction validates shape only: it never resolves a key,
    never consults a trust anchor, never reads a clock and never checks a signature against
    anything. A well-formed forgery constructs perfectly, which is the point — it is
    :mod:`.verification` that refuses it, and the forgery-laundering proof depends on this
    class not pre-emptively doing the verifier's job.
    """

    producer_id: str
    issuer: str
    producer_key_id: str
    tenant_id: str
    subject_id: str
    subject_type: str
    recommendation_id: str
    recommendation_digest: str
    signature: str
    signing_payload_digest: str
    #: A carried fact, not a trusted timestamp. Nothing here compares it to a clock.
    issued_at: datetime
    signing_purpose: str = PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE
    signature_algorithm: str = PRODUCER_ATTESTATION_SIGNATURE_ALGORITHM
    signature_profile: str = PRODUCER_ATTESTATION_SIGNATURE_PROFILE
    signature_encoding: str = PRODUCER_ATTESTATION_SIGNATURE_ENCODING
    schema_version: str = PRODUCER_ATTESTATION_V2_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PRODUCER_ATTESTATION_V2_SCHEMA_VERSION:
            raise _FieldError(
                f"schema_version must be exactly "
                f"{PRODUCER_ATTESTATION_V2_SCHEMA_VERSION!r}; Phase 5A's v1 tag names a "
                "different contract and is not verified here",
                _Outcome.UNSUPPORTED_SCHEMA_VERSION,
            )
        for name in (
            "producer_id",
            "issuer",
            "producer_key_id",
            "tenant_id",
            "subject_id",
            "subject_type",
            "recommendation_id",
        ):
            require_canonical_identifier(name, getattr(self, name))
        require_canonical_digest("recommendation_digest", self.recommendation_digest)

        if self.subject_type != SUBJECT_TYPE_CAPACITY_SUBJECT:
            raise _FieldError(
                f"subject_type must be the D-4 ratified {SUBJECT_TYPE_CAPACITY_SUBJECT!r} "
                f"(got {self.subject_type!r})"
            )

        purpose = require_canonical_identifier("signing_purpose", self.signing_purpose)
        if purpose not in SUPPORTED_V2_SIGNING_PURPOSES:
            raise _FieldError(
                f"unsupported signing_purpose {purpose!r}; a v2 producer attestation must "
                "name the dedicated v2 producer-signing purpose and must not reuse a "
                "policy-signing identity or Phase 5A's v1 purpose",
                _Outcome.UNSUPPORTED_SIGNING_PURPOSE,
            )

        algorithm = require_canonical_identifier(
            "signature_algorithm", self.signature_algorithm
        )
        if algorithm not in SUPPORTED_V2_SIGNATURE_ALGORITHMS:
            raise _FieldError(
                f"unsupported signature_algorithm {algorithm!r}; the admitted set is "
                f"{sorted(SUPPORTED_V2_SIGNATURE_ALGORITHMS)} and there is no negotiation",
                _Outcome.UNSUPPORTED_ALGORITHM,
            )

        if self.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE:
            raise _FieldError(
                "signature_profile must be exactly "
                f"{PRODUCER_ATTESTATION_SIGNATURE_PROFILE!r}",
                _Outcome.UNSUPPORTED_PROFILE,
            )
        if self.signature_encoding != PRODUCER_ATTESTATION_SIGNATURE_ENCODING:
            raise _FieldError(
                "signature_encoding must be exactly "
                f"{PRODUCER_ATTESTATION_SIGNATURE_ENCODING!r}",
                _Outcome.UNSUPPORTED_ENCODING,
            )

        # Pinned encoding, refused rather than coerced. ``decode_signature`` is TEV's
        # public canonical-base16 decoder: exactly 128 lowercase hex characters for the
        # 64 Ed25519 signature bytes. Uppercase, a ``0x`` prefix, base64, whitespace and
        # every wrong length are rejections, never normalizations.
        if type(self.signature) is not str:
            raise _FieldError(
                f"signature must be exactly a str (got {type(self.signature).__name__})",
                _Outcome.MALFORMED_SIGNATURE,
            )
        try:
            decode_signature(self.signature, "ProducerAttestationV2.signature")
        except Exception as exc:
            raise _FieldError(
                f"signature is not canonical lowercase base16 of an Ed25519 signature: "
                f"{exc}",
                _Outcome.MALFORMED_SIGNATURE,
            ) from None

        object.__setattr__(self, "issued_at", require_aware_utc("issued_at", self.issued_at))
        require_canonical_digest("signing_payload_digest", self.signing_payload_digest)

        # Re-derived, never believed: an attestation whose stated payload digest does not
        # equal the digest of its own payload cannot exist as an object.
        expected = canonical_digest(self.signing_payload())
        if self.signing_payload_digest != expected:
            raise _FieldError(
                "signing_payload_digest does not equal the digest of the canonical "
                "signing payload; the attestation is self-inconsistent",
                _Outcome.PAYLOAD_MISMATCH,
            )

    # -- the signed bytes ------------------------------------------------------------- #

    def signing_payload(self) -> dict[str, Any]:
        """The canonical payload this attestation claims a producer signed.

        ``signature`` and ``signing_payload_digest`` are both excluded: a signature cannot
        cover itself, and a digest of the payload cannot be inside the payload.
        """

        return producer_attestation_signing_payload(
            producer_id=self.producer_id,
            issuer=self.issuer,
            producer_key_id=self.producer_key_id,
            tenant_id=self.tenant_id,
            subject_id=self.subject_id,
            subject_type=self.subject_type,
            recommendation_id=self.recommendation_id,
            recommendation_digest=self.recommendation_digest,
            issued_at=self.issued_at,
            signing_purpose=self.signing_purpose,
            signature_algorithm=self.signature_algorithm,
            signature_profile=self.signature_profile,
            signature_encoding=self.signature_encoding,
        )

    def signed_bytes(self) -> bytes:
        """The exact bytes a verifier checks the signature against."""

        return canonical_bytes(self.signing_payload())

    def signature_bytes(self) -> bytes:
        """The decoded 64-byte signature. Refuses every non-canonical spelling."""

        return decode_signature(self.signature, "ProducerAttestationV2.signature")

    def to_canonical_dict(self) -> dict[str, Any]:
        """The complete canonical form, signature included. Not a trust statement."""

        return {
            **self.signing_payload(),
            "signature": self.signature,
            "signing_payload_digest": self.signing_payload_digest,
        }

    def digest(self) -> str:
        """This attestation's own canonical digest. An identity, not an endorsement."""

        return canonical_digest(self.to_canonical_dict())

    #: ``ClassVar``, not ``Final``: a bare ``Final`` annotation inside a dataclass body
    #: becomes a real field, reachable as a constructor keyword and part of ``__eq__``.
    #: A caller could then hand in its own key set. ``ClassVar`` is what excludes it.
    _ALLOWED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "signing_purpose",
            "producer_id",
            "issuer",
            "producer_key_id",
            "signature_algorithm",
            "signature_profile",
            "signature_encoding",
            "tenant_id",
            "subject_id",
            "subject_type",
            "recommendation_id",
            "recommendation_digest",
            "issued_at",
            "signature",
            "signing_payload_digest",
        }
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProducerAttestationV2":
        """Strict canonical deserializer — the only admitted raw-mapping entry point.

        Refuses unknown fields, missing fields and aliases, and reconstructs the **exact**
        type. There is deliberately no field a caller could supply that asserts trust, so
        there is nothing here for a forged mapping to claim.
        """

        if not isinstance(data, Mapping):
            raise _ExactTypeError(
                "producer-attestation data must be a mapping "
                f"(got {type(data).__name__})"
            )
        keys = set(data)
        unknown = keys - cls._ALLOWED_KEYS
        if unknown:
            raise _FieldError(
                f"unknown producer-attestation field(s): {sorted(unknown)}; a v2 "
                "attestation carries no trust, verification or authority field, so a "
                "mapping offering one is refused rather than ignored"
            )
        missing = cls._ALLOWED_KEYS - keys
        if missing:
            raise _FieldError(
                f"missing producer-attestation field(s): {sorted(missing)}"
            )
        issued_at = data["issued_at"]
        if isinstance(issued_at, str):
            issued_at = _parse_canonical_timestamp(issued_at)
        return cls(
            schema_version=data["schema_version"],
            signing_purpose=data["signing_purpose"],
            producer_id=data["producer_id"],
            issuer=data["issuer"],
            producer_key_id=data["producer_key_id"],
            signature_algorithm=data["signature_algorithm"],
            signature_profile=data["signature_profile"],
            signature_encoding=data["signature_encoding"],
            tenant_id=data["tenant_id"],
            subject_id=data["subject_id"],
            subject_type=data["subject_type"],
            recommendation_id=data["recommendation_id"],
            recommendation_digest=data["recommendation_digest"],
            issued_at=issued_at,
            signature=data["signature"],
            signing_payload_digest=data["signing_payload_digest"],
        )


def _parse_canonical_timestamp(value: str) -> datetime:
    """Parse the canonical ``...Z`` spelling. No clock is consulted."""

    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except (TypeError, ValueError) as exc:
        raise _FieldError(
            f"issued_at must be a canonical UTC timestamp string: {value!r}"
        ) from exc
    return parsed.replace(tzinfo=timezone.utc)
