"""The immutable effect-attestation wrapper (SE-3), and the payload it signs.

An :class:`EffectAttestation` binds one **complete** canonical
``ExecutionObservation`` — held by exact type, never copied field by field
into a competing shape — together with the attester's identity, role, key
reference, algorithm, schema/domain version and signature. It adds, repairs
and reinterprets nothing: every observation fact is read from the wrapped
object when the payload is built, and a fact this package cannot canonicalize
(a non-string parameter, a non-NFC string) is refused rather than rendered.

Two derived values are **never stored**: the observation digest and the
signing-payload digest are recomputed from the wrapped object every time they
are read, so there is no caller-supplied spelling of either to disagree with
the object it claims to identify.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final

from ugence_governance_contracts import ExecutionBusinessOutcome, ExecutionObservation

from .canonical import (
    canonical_digest,
    framed_signing_bytes,
    require_aware_utc,
    require_canonical_identifier,
    require_exact_type,
    require_nfc_text,
    require_string_mapping,
)
from .errors import EffectAttestationContractError as _Error
from .identifiers import (
    EFFECT_ATTESTATION_SCHEMA_VERSION,
    EFFECT_ATTESTATION_SIGNATURE_ALGORITHM,
    EFFECT_ATTESTATION_SIGNATURE_ENCODING,
    EFFECT_ATTESTATION_SIGNATURE_PROFILE,
    EFFECT_ATTESTATION_SIGNING_DOMAIN,
)
from .roles import EffectAttesterRole, require_role

__all__ = [
    "EffectAttestation",
    "canonical_observation",
    "observation_digest",
    "effect_attestation_signing_payload",
    "effect_attestation_signing_bytes",
    "EFFECT_ATTESTATION_SIGNED_FIELDS",
]

#: The fields the signature covers, in canonical (sorted) key order, stated once
#: so a reader and a test can see that ``signature`` itself is not among them.
EFFECT_ATTESTATION_SIGNED_FIELDS: Final[tuple] = (
    "attested_at",
    "attester_identity",
    "attester_key_id",
    "attester_role",
    "observation",
    "observation_digest",
    "schema_version",
    "signature_algorithm",
    "signature_encoding",
    "signature_profile",
    "signing_domain",
    "tenant_id",
)

_SIGNATURE_HEX_LENGTH: Final[int] = 128
_HEX_ALPHABET: Final[frozenset] = frozenset("0123456789abcdef")


def canonical_observation(observation: ExecutionObservation) -> dict:
    """The complete canonical projection of one exact ``ExecutionObservation``.

    Every declared field, none added, none dropped, none reinterpreted:
    ``business_outcome`` by its enum value, ``observed_parameters`` as an
    exact string-to-string mapping, ``final`` as an exact ``bool``, and the
    three strings as NFC text (empty admitted, because the contract admits
    empty). A value outside those shapes is a refusal, not a rendering.
    """

    require_exact_type("observation", observation, ExecutionObservation)
    require_exact_type("observation.business_outcome", observation.business_outcome,
                       ExecutionBusinessOutcome)
    require_exact_type("observation.final", observation.final, bool)
    return {
        "business_outcome": observation.business_outcome.value,
        "final": observation.final,
        "fingerprint": require_nfc_text("observation.fingerprint", observation.fingerprint,
                                        allow_empty=True),
        "observed_parameters": require_string_mapping(
            "observation.observed_parameters", observation.observed_parameters
        ),
        "provider_trace_id": require_nfc_text(
            "observation.provider_trace_id", observation.provider_trace_id, allow_empty=True
        ),
        "reason": require_nfc_text("observation.reason", observation.reason, allow_empty=True),
    }


def observation_digest(observation: ExecutionObservation) -> str:
    """``sha256:`` digest of :func:`canonical_observation`."""

    return canonical_digest(canonical_observation(observation))


def effect_attestation_signing_payload(
    *,
    observation: ExecutionObservation,
    tenant_id: str,
    attester_role: EffectAttesterRole,
    attester_identity: str,
    attester_key_id: str,
    attested_at: datetime,
    schema_version: str = EFFECT_ATTESTATION_SCHEMA_VERSION,
    signing_domain: str = EFFECT_ATTESTATION_SIGNING_DOMAIN,
    signature_algorithm: str = EFFECT_ATTESTATION_SIGNATURE_ALGORITHM,
    signature_profile: str = EFFECT_ATTESTATION_SIGNATURE_PROFILE,
    signature_encoding: str = EFFECT_ATTESTATION_SIGNATURE_ENCODING,
) -> dict:
    """The exact canonical object a signer signs and a verifier recomputes.

    Built from the arguments **only**. The verifier calls this with the
    observation *it* holds and the metadata the attestation claims, so a
    substituted observation or a lifted signature differs in bytes before it
    differs in anything else.
    """

    canonical = canonical_observation(observation)
    return {
        "attested_at": require_aware_utc("attested_at", attested_at),
        "attester_identity": require_canonical_identifier("attester_identity", attester_identity),
        "attester_key_id": require_canonical_identifier("attester_key_id", attester_key_id),
        "attester_role": require_role("attester_role", attester_role).value,
        "observation": canonical,
        "observation_digest": canonical_digest(canonical),
        "schema_version": require_canonical_identifier("schema_version", schema_version),
        "signature_algorithm": require_canonical_identifier(
            "signature_algorithm", signature_algorithm
        ),
        "signature_encoding": require_canonical_identifier(
            "signature_encoding", signature_encoding
        ),
        "signature_profile": require_canonical_identifier("signature_profile", signature_profile),
        "signing_domain": require_canonical_identifier("signing_domain", signing_domain),
        "tenant_id": require_canonical_identifier("tenant_id", tenant_id),
    }


def effect_attestation_signing_bytes(payload: dict) -> bytes:
    """The framed bytes that are actually signed: domain prefix, then payload."""

    require_exact_type("payload", payload, dict)
    return framed_signing_bytes(payload["signing_domain"], payload)


def _require_signature_encoding(name: str, value: object) -> str:
    text = require_nfc_text(name, value)
    if len(text) != _SIGNATURE_HEX_LENGTH or not set(text) <= _HEX_ALPHABET:
        raise _Error(
            f"{name} must be exactly {_SIGNATURE_HEX_LENGTH} lowercase hex characters "
            "(64 bytes); uppercase, prefixed, padded, short and long spellings are refused"
        )
    return text


@dataclass(frozen=True)
class EffectAttestation:
    """One signed statement by one attester, under one role, about one observation.

    Immutable, exact-typed, and self-describing: every identifier that decides
    how it is verified is a field here and inside the signed bytes. It does
    **not** carry the anchor, the public key, a verification outcome or any
    claim about whether the effect occurred.
    """

    #: The complete wrapped observation. Exact type; never a look-alike.
    observation: ExecutionObservation
    #: The tenant the observation belongs to. Signed and compared exactly.
    tenant_id: str
    #: Under which role the attester signs (SE-2). Signed and coordinate-bound.
    attester_role: EffectAttesterRole
    #: The attester's identity — the anchor's ``authority_id``.
    attester_identity: str
    #: The attester's key reference — the anchor's ``key_id``.
    attester_key_id: str
    #: When the attester says it signed. Caller-supplied; never a clock read here.
    attested_at: datetime
    #: The detached signature, exactly 128 lowercase hex characters.
    signature: str
    #: Contract identifiers, all pinned and all signed.
    schema_version: str = EFFECT_ATTESTATION_SCHEMA_VERSION
    signing_domain: str = EFFECT_ATTESTATION_SIGNING_DOMAIN
    signature_algorithm: str = EFFECT_ATTESTATION_SIGNATURE_ALGORITHM
    signature_profile: str = EFFECT_ATTESTATION_SIGNATURE_PROFILE
    signature_encoding: str = EFFECT_ATTESTATION_SIGNATURE_ENCODING

    def __post_init__(self) -> None:
        # Building the payload validates every field, including the wrapped
        # observation's canonical form, without storing anything derived.
        effect_attestation_signing_payload(
            observation=self.observation,
            tenant_id=self.tenant_id,
            attester_role=self.attester_role,
            attester_identity=self.attester_identity,
            attester_key_id=self.attester_key_id,
            attested_at=self.attested_at,
            schema_version=self.schema_version,
            signing_domain=self.signing_domain,
            signature_algorithm=self.signature_algorithm,
            signature_profile=self.signature_profile,
            signature_encoding=self.signature_encoding,
        )
        _require_signature_encoding("signature", self.signature)

    def signing_payload(self) -> dict:
        """The canonical payload, rebuilt from this object's fields every time."""

        return effect_attestation_signing_payload(
            observation=self.observation,
            tenant_id=self.tenant_id,
            attester_role=self.attester_role,
            attester_identity=self.attester_identity,
            attester_key_id=self.attester_key_id,
            attested_at=self.attested_at,
            schema_version=self.schema_version,
            signing_domain=self.signing_domain,
            signature_algorithm=self.signature_algorithm,
            signature_profile=self.signature_profile,
            signature_encoding=self.signature_encoding,
        )

    def signed_bytes(self) -> bytes:
        """The framed bytes this attestation claims were signed."""

        return effect_attestation_signing_bytes(self.signing_payload())

    @property
    def observation_digest(self) -> str:
        """Recomputed from the wrapped observation; never stored."""

        return observation_digest(self.observation)

    @property
    def signing_payload_digest(self) -> str:
        """Recomputed from the payload; never stored."""

        return canonical_digest(self.signing_payload())
