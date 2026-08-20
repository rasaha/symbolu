"""The producer-signing boundary — narrow by construction, and outside the Controller.

Where this sits, and why the Controller gains nothing
-----------------------------------------------------
The Cloud Scaling Controller remains an advisory, key-free leaf at 0.4.0. It holds no
private key, no signer, no crypto dependency and no trust-anchor resolution, and this
package adds none to it: nothing here imports a controller module, and the controller
declares no dependency on this distribution. The attestation is produced **at** the
controller's output boundary by a signer that lives in *this* distribution and is wired by
the deployment — never **by** the controller. The controller's own statement stands
unchanged: its recommendation digest is not a signature, not an authorization and not a
proof of effect.

There is no "sign arbitrary bytes" capability
---------------------------------------------
The obvious signer port is ``sign(payload: bytes) -> str``. It is not the shape used here,
because it is a public oracle: anything a caller can serialize, a configured signer would
sign, and a signature is only worth something if the set of things it can cover is closed.

Instead a signer receives a :class:`ProducerAttestationSigningInput` — a token-guarded,
package-minted value object. There is exactly one route to one:

    validated attestation body  ->  :func:`mint_producer_attestation`  ->  signature

:func:`mint_producer_attestation` builds the canonical payload from components it has
itself validated, stamps the package-private token, and hands the result to the signer.
A caller cannot construct that token and therefore cannot reach a signature over bytes of
their choosing. Following the Trusted Evidence Authority's ``ReceiptSigningInput`` pattern.

*Stated plainly rather than overclaimed:* in-process code that reaches into a private
module attribute is not defended against, and no Python-level mechanism defends against it.
What is closed is the **public API** route. The load-bearing secret remains the signing key.

What a signer cannot do
-----------------------
A signer receives finished bytes and returns an encoded signature. It cannot choose or
alter any recommendation fact, cannot widen the tenant or subject identity, cannot select
the signing purpose or schema tag, cannot mint authorization and cannot issue an envelope —
none of those are inputs it receives or outputs it returns. It may refuse; it may not
redirect. A signer that signs under a key other than the one it advertises produces a
signature that will not verify against the advertised coordinate's anchor, which is a
refusal, not a silent success.

No private key material reaches a contract object, a canonical dict, a digest, a ``repr``,
an exception message or a record. No production private key exists anywhere in this
repository: the only key material in the distribution is the test seed used by the suite,
and the one shipped signer is marked :attr:`is_reference_signer` so a production
composition root refuses it structurally rather than by convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, runtime_checkable

from ugence_trusted_evidence_authority import (
    TrustAnchorCapability,
    TrustAnchorRecord,
    TrustedEvidenceSigningKey,
    encode_public_key,
    encode_signature,
)

from .attestation import ProducerAttestationV2, producer_attestation_signing_payload
from .canonical import (
    canonical_bytes,
    canonical_digest,
    require_aware_utc,
    require_canonical_digest,
    require_canonical_identifier,
    require_exact_type,
)
from .errors import ProducerAttestationConfigurationError as _ConfigError
from .errors import ProducerAttestationSigningBoundaryError as _BoundaryError
from .identifiers import (
    PRODUCER_ATTESTATION_CAPABILITY,
    PRODUCER_ATTESTATION_SIGNATURE_ALGORITHM,
    PRODUCER_ATTESTATION_SIGNATURE_ENCODING,
    PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
    PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
)

__all__ = [
    "ProducerAttestationSigningInput",
    "ProducerAttestationSignerPort",
    "REFERENCE_GRADE_SIGNERS",
    "ReferenceEd25519ProducerAttestationSigner",
    "mint_producer_attestation",
]

#: The private capability token. Not exported, not in ``__all__``, not reachable from the
#: curated API. Holding it is what distinguishes a signing input the package built from one
#: a caller assembled.
_SIGNING_INPUT_TOKEN = object()


@dataclass(frozen=True)
class ProducerAttestationSigningInput:
    """A package-minted instruction to sign one specific producer-attestation payload.

    Not a contract: it carries ``bytes``, which the canonical encoder rejects outright, so
    it can never be canonicalized, digested, stored in an artifact or serialized into
    anything. It exists only to travel from :func:`mint_producer_attestation` to a
    :class:`ProducerAttestationSignerPort` and be discarded.

    Direct construction is refused. ``issuance_token`` must be the package's private token;
    ``None``, ``True``, a look-alike sentinel, a string and every other object raise. That
    is what makes "sign these bytes" unreachable from outside.
    """

    signed_input: bytes
    producer_id: str
    issuer: str
    producer_key_id: str
    signature_profile: str
    issuance_token: object = None

    def __post_init__(self) -> None:
        if self.issuance_token is not _SIGNING_INPUT_TOKEN:
            raise _BoundaryError(
                "ProducerAttestationSigningInput cannot be constructed directly. A "
                "signing input is minted only by mint_producer_attestation(), from a "
                "payload this package built out of components it validated itself — "
                "there is no supported route from caller-chosen bytes to a producer "
                "signature."
            )
        if type(self.signed_input) is not bytes:
            raise _BoundaryError(
                "ProducerAttestationSigningInput.signed_input must be exactly bytes "
                f"(got {type(self.signed_input).__name__})"
            )
        if len(self.signed_input) == 0:
            raise _BoundaryError(
                "ProducerAttestationSigningInput.signed_input must not be empty; a "
                "signature over nothing covers nothing"
            )
        require_canonical_identifier(
            "ProducerAttestationSigningInput.producer_id", self.producer_id
        )
        require_canonical_identifier(
            "ProducerAttestationSigningInput.issuer", self.issuer
        )
        require_canonical_identifier(
            "ProducerAttestationSigningInput.producer_key_id", self.producer_key_id
        )
        if self.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE:
            raise _BoundaryError(
                "ProducerAttestationSigningInput.signature_profile must be exactly "
                f"{PRODUCER_ATTESTATION_SIGNATURE_PROFILE!r}"
            )

    def __repr__(self) -> str:
        """Byte length only. The frame itself is never rendered into a log."""

        return (
            "ProducerAttestationSigningInput(issuer="
            f"{self.issuer!r}, key={self.producer_key_id!r}, "
            f"{len(self.signed_input)} bytes)"
        )


@runtime_checkable
class ProducerAttestationSignerPort(Protocol):
    """Produce a producer's signature over a package-minted attestation payload.

    The signer names the issuer and key it speaks for, so the minting routine can bind
    those coordinates **into the signed bytes** before signing, rather than trusting the
    signer to have signed what it says. An HSM- or KMS-backed signer implements this same
    port and drops in without any caller change.
    """

    #: ``True`` only for a reference/test signer. A production composition root refuses one.
    is_reference_signer: bool

    @property
    def producer_id(self) -> str:
        """The producer identity this signer speaks for."""
        ...

    @property
    def issuer(self) -> str:
        """The issuing authority — the authority half of the anchor coordinate."""
        ...

    @property
    def producer_key_id(self) -> str:
        """The exact key identifier a verifier will resolve."""
        ...

    @property
    def signature_profile(self) -> str:
        """The one ratified profile. There is no second value to return."""
        ...

    def sign_producer_attestation(
        self, signing_input: ProducerAttestationSigningInput
    ) -> str:
        """Return the signature in the one canonical encoding."""
        ...


class ReferenceEd25519ProducerAttestationSigner:
    """The **reference** :class:`ProducerAttestationSignerPort`. Test and local use only.

    Structurally distinguishable from a production signer by
    :attr:`is_reference_signer`, which :func:`mint_producer_attestation` refuses in
    production mode. It exists so the suite and a local composition root can mint genuine
    signatures; it is not a production key custodian and does not pretend to be.

    Holds a :class:`TrustedEvidenceSigningKey` and nothing else, and that class holds only
    a maintained backend key object — never the caller's raw seed bytes. There is no
    accessor returning private material from either object, neither can be pickled or
    copied, and ``__setattr__`` raises after construction so a signing key cannot be
    swapped out from under a configured deployment.
    """

    __slots__ = ("_producer_id", "_issuer", "_producer_key_id", "_signing_key")

    #: Structurally marks this as reference grade. Read as a class attribute by the
    #: production guard, so a subclass cannot hide it behind an instance property.
    is_reference_signer: bool = True

    def __init__(
        self,
        *,
        producer_id: str,
        issuer: str,
        producer_key_id: str,
        signing_key: TrustedEvidenceSigningKey,
    ) -> None:
        require_canonical_identifier(
            "ReferenceEd25519ProducerAttestationSigner.producer_id", producer_id
        )
        require_canonical_identifier(
            "ReferenceEd25519ProducerAttestationSigner.issuer", issuer
        )
        require_canonical_identifier(
            "ReferenceEd25519ProducerAttestationSigner.producer_key_id", producer_key_id
        )
        require_exact_type(
            "ReferenceEd25519ProducerAttestationSigner.signing_key",
            signing_key,
            TrustedEvidenceSigningKey,
        )
        object.__setattr__(self, "_producer_id", producer_id)
        object.__setattr__(self, "_issuer", issuer)
        object.__setattr__(self, "_producer_key_id", producer_key_id)
        object.__setattr__(self, "_signing_key", signing_key)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"ReferenceEd25519ProducerAttestationSigner is immutable; cannot set {name!r}. "
            "Rebinding the signing key or its advertised coordinates after configuration "
            "would let a caller re-point an already-configured signer."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"ReferenceEd25519ProducerAttestationSigner is immutable; cannot delete {name!r}"
        )

    @property
    def producer_id(self) -> str:
        return self._producer_id

    @property
    def issuer(self) -> str:
        return self._issuer

    @property
    def producer_key_id(self) -> str:
        return self._producer_key_id

    @property
    def signature_profile(self) -> str:
        return PRODUCER_ATTESTATION_SIGNATURE_PROFILE

    def sign_producer_attestation(
        self, signing_input: ProducerAttestationSigningInput
    ) -> str:
        """Sign the package-minted payload, returning canonical lowercase base16.

        Refuses an input addressed to a different issuer or key than this signer holds: a
        signer must never produce a signature labelled with coordinates it cannot answer
        for, because a verifier would then resolve the *labelled* anchor and check a
        signature made by a different key.
        """

        require_exact_type(
            "ReferenceEd25519ProducerAttestationSigner.signing_input",
            signing_input,
            ProducerAttestationSigningInput,
        )
        if signing_input.issuer != self._issuer:
            raise _BoundaryError(
                "this signer refuses a signing input addressed to issuer "
                f"{signing_input.issuer!r}; it speaks for {self._issuer!r}"
            )
        if signing_input.producer_key_id != self._producer_key_id:
            raise _BoundaryError(
                "this signer refuses a signing input addressed to key "
                f"{signing_input.producer_key_id!r}; it holds {self._producer_key_id!r}"
            )
        if signing_input.producer_id != self._producer_id:
            raise _BoundaryError(
                "this signer refuses a signing input addressed to producer "
                f"{signing_input.producer_id!r}; it speaks for {self._producer_id!r}"
            )
        return encode_signature(self._signing_key.sign(signing_input.signed_input))

    def trust_anchor(
        self,
        *,
        trust_anchor_set_id: str,
        trust_anchor_set_version: str,
        effective_from: "datetime | None" = None,
        effective_to: "datetime | None" = None,
    ) -> TrustAnchorRecord:
        """Publish this signer's **public** half for registration as a trust anchor.

        A convenience for a reference composition root and for the suite. The result
        carries only public material, and it is always minted with the
        producer-attestation capability — a producer signer cannot publish itself as a
        receipt issuer, which keeps ADR E-3's separation at the one place a key's public
        half is derived from its private half.

        Publishing an anchor is a **configuration** act, not an authorization one:
        registering the record into a directory is the composition root's decision, and
        this method neither performs nor implies it.
        """

        if PRODUCER_ATTESTATION_CAPABILITY is TrustAnchorCapability.RECEIPT_ISSUANCE:
            raise _BoundaryError(
                "refusing to publish a producer signer under the receipt-issuance "
                "capability"
            )
        return TrustAnchorRecord(
            authority_id=self._issuer,
            key_id=self._producer_key_id,
            capability=PRODUCER_ATTESTATION_CAPABILITY,
            public_key=encode_public_key(
                self._signing_key.verification_key.public_key_bytes
            ),
            trust_anchor_set_id=trust_anchor_set_id,
            trust_anchor_set_version=trust_anchor_set_version,
            effective_from=effective_from,
            effective_to=effective_to,
        )

    def __repr__(self) -> str:
        return (
            "ReferenceEd25519ProducerAttestationSigner(issuer="
            f"{self._issuer!r}, key={self._producer_key_id!r}, reference=True)"
        )


#: Signer types this repository documents as reference grade. Refused in production,
#: **including every subclass** — see :func:`mint_producer_attestation`. The exact
#: counterpart of :data:`~ugence_cloud_scaling_producer_attestation.trust.
#: REFERENCE_GRADE_RESOLVERS`, and deliberately spelled the same way, so the two denials
#: cannot drift apart. Composition is not inheritance: a custodian that *holds* one of
#: these is not matched, because it never declared itself reference grade.
REFERENCE_GRADE_SIGNERS: tuple[type, ...] = (ReferenceEd25519ProducerAttestationSigner,)


def mint_producer_attestation(
    *,
    signer: ProducerAttestationSignerPort,
    tenant_id: str,
    subject_id: str,
    recommendation_id: str,
    recommendation_digest: str,
    issued_at: datetime,
    subject_type: str = SUBJECT_TYPE_CAPACITY_SUBJECT,
    production_mode: bool = False,
) -> ProducerAttestationV2:
    """Mint a signed :class:`ProducerAttestationV2` at the Controller output boundary.

    The **only** route to a producer signature in this package. Every component of the
    signed payload is validated here, by this function, before any byte reaches a signer:
    the identifiers are canonical and NFC, the recommendation digest is canonical, the
    instant is timezone-aware, and the schema tag, signing purpose, algorithm, profile and
    encoding are this package's pinned constants and are not parameters at all.

    The issuer, producer and key coordinates are read from the **signer**, so they name the
    key that is actually about to be used and are bound into the bytes before signing. A
    caller cannot present one identity and sign under another.

    ``production_mode=True`` refuses a reference signer, and refuses **every subclass of
    one** — the :data:`REFERENCE_GRADE_SIGNERS` match is by ``isinstance`` and is evaluated
    *before* the :attr:`is_reference_signer` flag, so a subclass that sets the flag to
    ``False`` never reaches the branch that would have admitted it. This mirrors
    :func:`~ugence_cloud_scaling_producer_attestation.trust.require_production_resolver`
    exactly, and for the same reason: a denial matched by exact type is a hole, because the
    subclass inherits the implementation the denial exists to refuse. A custodian that
    *composes* a reference signer rather than inheriting from one is admitted — it never
    declared itself reference grade, and it can hold its key wherever it likes.

    There is no production key in this repository and no route by which this function could
    supply one.
    """

    if signer is None:
        raise _ConfigError("a signer is required; there is no default and no fallback")
    if production_mode and isinstance(signer, REFERENCE_GRADE_SIGNERS):
        reference_type = next(
            base for base in REFERENCE_GRADE_SIGNERS if isinstance(signer, base)
        )
        actual = type(signer).__name__
        via = (
            f"{actual} is {reference_type.__name__}"
            if actual == reference_type.__name__
            else f"{actual} is a subclass of {reference_type.__name__}"
        )
        raise _ConfigError(
            f"production_mode=True refuses {actual}: {via}, which this repository "
            "documents as the REFERENCE signer, for tests and local use only. A subclass "
            "inherits that signer's whole implementation — the same in-memory "
            "TrustedEvidenceSigningKey, built from the same caller-supplied seed — so "
            "setting is_reference_signer=False on one relabels it without changing what "
            "holds the key, and does not lift this refusal. Inject a production key "
            "custodian implementing ProducerAttestationSignerPort over a managed key "
            "service; this repository ships no production key."
        )
    if production_mode and getattr(type(signer), "is_reference_signer", False) is True:
        raise _ConfigError(
            "production_mode=True refuses a reference signer "
            f"({type(signer).__name__}.is_reference_signer is True). Inject a "
            "production key custodian implementing ProducerAttestationSignerPort; this "
            "repository ships no production key."
        )

    producer_id = require_canonical_identifier("signer.producer_id", signer.producer_id)
    issuer = require_canonical_identifier("signer.issuer", signer.issuer)
    producer_key_id = require_canonical_identifier(
        "signer.producer_key_id", signer.producer_key_id
    )
    if signer.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE:
        raise _ConfigError(
            f"signer advertises profile {signer.signature_profile!r}; this package signs "
            f"only under {PRODUCER_ATTESTATION_SIGNATURE_PROFILE!r}"
        )

    payload = producer_attestation_signing_payload(
        producer_id=producer_id,
        issuer=issuer,
        producer_key_id=producer_key_id,
        tenant_id=require_canonical_identifier("tenant_id", tenant_id),
        subject_id=require_canonical_identifier("subject_id", subject_id),
        subject_type=require_canonical_identifier("subject_type", subject_type),
        recommendation_id=require_canonical_identifier(
            "recommendation_id", recommendation_id
        ),
        recommendation_digest=require_canonical_digest(
            "recommendation_digest", recommendation_digest
        ),
        issued_at=require_aware_utc("issued_at", issued_at),
        signing_purpose=PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE,
        signature_algorithm=PRODUCER_ATTESTATION_SIGNATURE_ALGORITHM,
        signature_profile=PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
        signature_encoding=PRODUCER_ATTESTATION_SIGNATURE_ENCODING,
    )

    signing_input = ProducerAttestationSigningInput(
        signed_input=canonical_bytes(payload),
        producer_id=producer_id,
        issuer=issuer,
        producer_key_id=producer_key_id,
        signature_profile=PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
        issuance_token=_SIGNING_INPUT_TOKEN,
    )
    signature = signer.sign_producer_attestation(signing_input)
    if type(signature) is not str:
        raise _BoundaryError(
            "a signer must return the signature as exactly a str "
            f"(got {type(signature).__name__})"
        )

    return ProducerAttestationV2(
        producer_id=payload["producer_id"],
        issuer=payload["issuer"],
        producer_key_id=payload["producer_key_id"],
        tenant_id=payload["tenant_id"],
        subject_id=payload["subject_id"],
        subject_type=payload["subject_type"],
        recommendation_id=payload["recommendation_id"],
        recommendation_digest=payload["recommendation_digest"],
        issued_at=payload["issued_at"],
        signing_purpose=payload["signing_purpose"],
        signature_algorithm=payload["signature_algorithm"],
        signature_profile=payload["signature_profile"],
        signature_encoding=payload["signature_encoding"],
        signature=signature,
        signing_payload_digest=canonical_digest(payload),
    )
