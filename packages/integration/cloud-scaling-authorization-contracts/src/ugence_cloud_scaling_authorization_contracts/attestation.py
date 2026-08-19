"""``ProducerAttestationEvidence`` — a signature that is carried, never believed.

The Phase 4C adapter closed the *recommendation authenticity* gap by reconciling a
recommendation digest against an independent expectation. It did not establish **who
produced** the recommendation. This artifact carries the producer's own signature over
that digest so Phase 5B can later decide whether to trust it.

Phase 5A's contribution is entirely structural and entirely negative:

* the attestation must be **present** — absence fails candidate construction;
* it must be syntactically well-formed;
* it must bind **the exact ``recommendation_digest``** the projection reconciled;
* it must name a **supported producer-signing purpose**;
* its ``signing_payload_digest`` must equal the digest of its own canonical signing
  payload, recomputed here from the public Risk Authority primitives.

Phase 5A **never** checks the signature bytes against a key, resolves a producer
identity, consults a trust anchor, or checks revocation or freshness. It therefore never
calls the producer trusted, authentic or verified — the vocabulary for saying so does not
exist in this package (see :mod:`.trust`).

Ratified key separation: the producer signs under a **dedicated producer-signing key
purpose**, never Policy Authority's policy-signing identity. The controller is permitted
to sign its own output — a self-signature is a claim of origin, not a grant of trust, and
it becomes meaningful only when an independent Phase 5B verifier validates it under a key
it already trusts for this purpose.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, ClassVar, Final, Mapping

from .canonical import (
    canonical_digest,
    require_canonical_digest,
    require_canonical_identifier,
    require_nfc_text,
)
from .errors import AuthorizationCandidateRejectionReason as _Reason
from .errors import CanonicalFieldError, ExactTypeError, ProducerAttestationError
from .identifiers import SUPPORTED_PRODUCER_SIGNING_PURPOSES
from .trust import PHASE_5A_TRUST_STATE, EvidenceTrustState

__all__ = [
    "PRODUCER_ATTESTATION_SCHEMA_VERSION",
    "SUPPORTED_SIGNATURE_ALGORITHMS",
    "ProducerAttestationEvidence",
]

#: Schema tag for the attestation's canonical signing payload.
PRODUCER_ATTESTATION_SCHEMA_VERSION: Final[str] = (
    "cloud-scaling-producer-attestation-evidence-1"
)

#: The closed set of signature algorithm identifiers Phase 5A will admit **structurally**.
#: Admitting an algorithm name is not a statement that the signature verifies under it.
SUPPORTED_SIGNATURE_ALGORITHMS: Final[frozenset[str]] = frozenset({"ed25519"})


def _require_utc(name: str, value: Any) -> datetime:
    if not isinstance(value, datetime):
        raise CanonicalFieldError(
            f"{name} must be a datetime", _Reason.MALFORMED_CANONICAL_FIELD
        )
    if value.tzinfo is None or value.utcoffset() is None:
        raise CanonicalFieldError(
            f"{name} must be timezone-aware; a naive datetime is rejected rather than "
            "assumed UTC",
            _Reason.MALFORMED_CANONICAL_FIELD,
        )
    return value.astimezone(timezone.utc)


@dataclass(frozen=True)
class ProducerAttestationEvidence:
    """A producer's signature over a recommendation digest. **Evidence, not trust.**

    Holding one of these means a signature was *presented* for this exact recommendation
    under a recognised signing purpose. It means nothing about whether that signature is
    valid, whether the key is entitled, or whether the producer is who it claims to be.
    :attr:`trust_state` is fixed at ``PRESENT_BUT_NOT_TRUST_VERIFIED`` and is a read-only
    property, not a field — there is no verified state to assign.
    """

    producer_id: str
    producer_key_id: str
    signature_algorithm: str
    signature: str
    #: The producer's own label for the recommendation.
    #:
    #: **Accurate statement of the binding.** The recommendation ID *is* transitively
    #: bound by the Phase 4C canonical digest chain — changing it changes
    #: ``recommendation_digest`` and therefore ``request_digest``. What it is *not* is
    #: directly recoverable from the resulting digest, and it is not exposed as an
    #: independently cross-checkable field on the projection or the decision. So Phase
    #: 5A cannot compare a supplied ID against a Phase 4 field, and does not claim to.
    #:
    #: It is bound here, inside the signing payload, so the ID is covered by the
    #: producer's signature and an ID substitution becomes detectable by the Phase 5B
    #: verifier. A caller who substitutes the ID *and* re-derives the chain produces a
    #: different ``recommendation_digest``, which Phase 5A does cross-check; a caller who
    #: substitutes only the ID and keeps a stale digest fails that same check.
    recommendation_id: str
    recommendation_digest: str
    signing_purpose: str
    signing_payload_digest: str
    #: A carried fact, not a trusted timestamp. Phase 5A neither reads a clock nor
    #: compares this to one; freshness is Phase 5B's, under its own trusted clock.
    issued_at: datetime
    schema_version: str = PRODUCER_ATTESTATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.schema_version != PRODUCER_ATTESTATION_SCHEMA_VERSION:
            raise ProducerAttestationError(
                f"schema_version must be {PRODUCER_ATTESTATION_SCHEMA_VERSION!r}",
                _Reason.UNSUPPORTED_SCHEMA_VERSION,
            )
        require_canonical_identifier("producer_id", self.producer_id)
        require_canonical_identifier("producer_key_id", self.producer_key_id)
        require_canonical_identifier("recommendation_id", self.recommendation_id)
        require_nfc_text("signature", self.signature)
        require_canonical_digest("recommendation_digest", self.recommendation_digest)

        algorithm = require_canonical_identifier(
            "signature_algorithm", self.signature_algorithm
        )
        if algorithm not in SUPPORTED_SIGNATURE_ALGORITHMS:
            raise ProducerAttestationError(
                f"unsupported signature_algorithm {algorithm!r}; Phase 5A admits "
                f"{sorted(SUPPORTED_SIGNATURE_ALGORITHMS)} structurally and verifies none "
                "of them",
                _Reason.MALFORMED_PRODUCER_ATTESTATION,
            )

        purpose = require_canonical_identifier("signing_purpose", self.signing_purpose)
        if purpose not in SUPPORTED_PRODUCER_SIGNING_PURPOSES:
            raise ProducerAttestationError(
                f"unsupported signing_purpose {purpose!r}; a producer attestation must "
                "name the dedicated producer-signing purpose and must not reuse a "
                "policy-signing identity",
                _Reason.UNSUPPORTED_SIGNING_PURPOSE,
            )

        _require_utc("issued_at", self.issued_at)
        require_canonical_digest("signing_payload_digest", self.signing_payload_digest)

        # Re-derive the signing-payload digest rather than trusting the value handed in.
        expected = canonical_digest(self.signing_payload())
        if self.signing_payload_digest != expected:
            raise ProducerAttestationError(
                "signing_payload_digest does not equal the digest of the canonical "
                "signing payload",
                _Reason.PRODUCER_ATTESTATION_CONTENT_MISMATCH,
            )

    @property
    def trust_state(self) -> EvidenceTrustState:
        """Always ``PRESENT_BUT_NOT_TRUST_VERIFIED``. A property, so it cannot be set.

        ``object.__setattr__(evidence, "trust_state", ...)`` — the usual frozen-dataclass
        bypass — raises against this data descriptor, and a doctored instance dictionary
        never shadows it.
        """

        return PHASE_5A_TRUST_STATE

    def signing_payload(self) -> dict[str, Any]:
        """The canonical bytes the producer is asserted to have signed.

        The ``signature`` is deliberately **excluded** — a signature cannot cover itself.
        """

        return {
            "schema_version": self.schema_version,
            "producer_id": self.producer_id,
            "producer_key_id": self.producer_key_id,
            "signature_algorithm": self.signature_algorithm,
            "signing_purpose": self.signing_purpose,
            "recommendation_id": self.recommendation_id,
            "recommendation_digest": self.recommendation_digest,
            "issued_at": self.issued_at,
        }

    def to_canonical_dict(self) -> dict[str, Any]:
        """The full canonical form, signature included, for the candidate digest."""

        return {
            **self.signing_payload(),
            "signature": self.signature,
            "signing_payload_digest": self.signing_payload_digest,
            # The trust state is framed in deliberately: a candidate digest computed over
            # this artifact commits to the fact that it was NOT trust-verified.
            "trust_state": self.trust_state.value,
        }

    def digest(self) -> str:
        return canonical_digest(self.to_canonical_dict())

    #: ``ClassVar``, not ``Final``: ``Final`` alone does not make a name a class
    #: variable, so a bare ``Final`` annotation inside a dataclass body becomes a
    #: real **field** — reachable as a constructor keyword, present in
    #: ``dataclasses.fields()`` and part of ``__eq__``. A caller could then hand in
    #: its own key set. ``ClassVar`` is what actually excludes it from the fields.
    _ALLOWED_KEYS: ClassVar[frozenset[str]] = frozenset(
        {
            "schema_version",
            "producer_id",
            "producer_key_id",
            "signature_algorithm",
            "signature",
            "recommendation_id",
            "recommendation_digest",
            "signing_purpose",
            "signing_payload_digest",
            "issued_at",
        }
    )

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ProducerAttestationEvidence":
        """Strict canonical deserializer — the only admitted raw-mapping entry point.

        Refuses unknown fields, missing fields, aliases and duplicate semantic fields, and
        reconstructs the **exact** type. ``trust_state`` is refused as an input: it is
        derived, and accepting it would let a caller present a forged state.
        """

        if type(data) is not dict and not isinstance(data, Mapping):
            raise ExactTypeError(
                "producer attestation data must be a mapping", _Reason.UNSUPPORTED_EXACT_TYPE
            )
        keys = set(data)
        unknown = keys - cls._ALLOWED_KEYS
        if unknown:
            reason = (
                _Reason.FORGED_TRUST_STATE
                if {"trust_state", "verified", "trusted", "authentic"} & unknown
                else _Reason.UNKNOWN_FIELD
            )
            raise CanonicalFieldError(
                f"unknown producer-attestation field(s): {sorted(unknown)}", reason
            )
        missing = cls._ALLOWED_KEYS - {"schema_version"} - keys
        if missing:
            raise CanonicalFieldError(
                f"missing producer-attestation field(s): {sorted(missing)}",
                _Reason.MALFORMED_CANONICAL_FIELD,
            )
        if "schema_version" not in data:
            raise CanonicalFieldError(
                "producer attestation requires an explicit schema_version",
                _Reason.UNSUPPORTED_SCHEMA_VERSION,
            )
        issued_at = data["issued_at"]
        if isinstance(issued_at, str):
            issued_at = _parse_ts(issued_at)
        return cls(
            schema_version=data["schema_version"],
            producer_id=data["producer_id"],
            producer_key_id=data["producer_key_id"],
            signature_algorithm=data["signature_algorithm"],
            signature=data["signature"],
            recommendation_id=data["recommendation_id"],
            recommendation_digest=data["recommendation_digest"],
            signing_purpose=data["signing_purpose"],
            signing_payload_digest=data["signing_payload_digest"],
            issued_at=issued_at,
        )


def _parse_ts(value: str) -> datetime:
    """Parse the canonical ``...Z`` timestamp spelling. No clock is consulted."""

    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
    except (TypeError, ValueError) as exc:
        raise CanonicalFieldError(
            f"issued_at must be a canonical UTC timestamp string: {value!r}",
            _Reason.MALFORMED_CANONICAL_FIELD,
        ) from exc
    return parsed.replace(tzinfo=timezone.utc)
