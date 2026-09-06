"""Minting an attestation, and the one reference signer — refused in production.

No production signer exists here. No key is loaded from a file, an environment
variable, a network or a discovery service; no key is generated; no credential
is held. :class:`ReferenceEd25519EffectAttestationSigner` derives a key from a
caller-supplied seed through the Trusted Evidence Authority's signing-key type,
exists so the suite and a local composition root can mint genuine signatures,
and is structurally marked ``is_reference_signer = True`` so
:func:`mint_effect_attestation` refuses it — and every subclass of it — under
``production_mode=True``. An HSM- or KMS-backed custodian implements the same
:class:`EffectAttestationSignerPort` and is the deployment's concern (DD-10b).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ugence_governance_contracts import ExecutionObservation
from ugence_trusted_evidence_authority import (
    TrustAnchorRecord,
    TrustedEvidenceSigningKey,
    encode_public_key,
    encode_signature,
)

from .attestation import (
    EffectAttestation,
    effect_attestation_signing_bytes,
    effect_attestation_signing_payload,
)
from .canonical import require_aware_utc, require_canonical_identifier, require_exact_type
from .errors import EffectAttestationSigningBoundaryError as _BoundaryError
from .identifiers import (
    EFFECT_ATTESTATION_SIGNATURE_ENCODING,
    EFFECT_ATTESTATION_SIGNATURE_PROFILE,
)
from .roles import EffectAttesterRole, capability_for_role, require_role

__all__ = [
    "EffectAttestationSignerPort",
    "ReferenceEd25519EffectAttestationSigner",
    "mint_effect_attestation",
]


@runtime_checkable
class EffectAttestationSignerPort(Protocol):
    """What a key custodian must present to mint an attestation.

    A signer speaks for exactly one ``(identity, key_id, role)``; it is asked to
    sign framed bytes and returns the canonical 128-hex signature. Whether the
    private half lives in memory, an HSM or a KMS is invisible here.
    """

    #: ``True`` only for a reference/test signer. Production minting refuses one.
    is_reference_signer: bool

    @property
    def attester_identity(self) -> str: ...

    @property
    def attester_key_id(self) -> str: ...

    @property
    def attester_role(self) -> EffectAttesterRole: ...

    def sign_effect_attestation(self, signed_bytes: bytes) -> str: ...


class ReferenceEd25519EffectAttestationSigner:
    """A deterministic reference signer, for tests and local composition only.

    Immutable, seed-derived, and marked at **class** level so a subclass cannot
    hide the mark behind an instance property.
    """

    __slots__ = ("_identity", "_key_id", "_role", "_signing_key")

    is_reference_signer: bool = True

    def __init__(
        self,
        seed: bytes,
        *,
        attester_identity: str,
        attester_key_id: str,
        attester_role: EffectAttesterRole,
    ) -> None:
        require_exact_type("seed", seed, bytes)
        object.__setattr__(self, "_identity",
                           require_canonical_identifier("attester_identity", attester_identity))
        object.__setattr__(self, "_key_id",
                           require_canonical_identifier("attester_key_id", attester_key_id))
        object.__setattr__(self, "_role", require_role("attester_role", attester_role))
        object.__setattr__(self, "_signing_key", TrustedEvidenceSigningKey(seed))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ReferenceEd25519EffectAttestationSigner is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("ReferenceEd25519EffectAttestationSigner is immutable")

    def __reduce__(self):
        raise TypeError("a signer is never pickled; a private key is not a value")

    @property
    def attester_identity(self) -> str:
        return self._identity

    @property
    def attester_key_id(self) -> str:
        return self._key_id

    @property
    def attester_role(self) -> EffectAttesterRole:
        return self._role

    def sign_effect_attestation(self, signed_bytes: bytes) -> str:
        require_exact_type("signed_bytes", signed_bytes, bytes)
        return encode_signature(self._signing_key.sign(signed_bytes))

    def trust_anchor(
        self,
        *,
        trust_anchor_set_id: str,
        trust_anchor_set_version: str,
        effective_from: Optional[datetime] = None,
        effective_to: Optional[datetime] = None,
    ) -> TrustAnchorRecord:
        """Publish this signer's **public** half as an anchor under its role's
        capability. Registering it into a directory is the composition root's
        act, not this method's."""

        return TrustAnchorRecord(
            authority_id=self._identity,
            key_id=self._key_id,
            capability=capability_for_role(self._role),
            public_key=encode_public_key(self._signing_key.verification_key.public_key_bytes),
            trust_anchor_set_id=trust_anchor_set_id,
            trust_anchor_set_version=trust_anchor_set_version,
            signature_profile=EFFECT_ATTESTATION_SIGNATURE_PROFILE,
            signature_encoding=EFFECT_ATTESTATION_SIGNATURE_ENCODING,
            effective_from=effective_from,
            effective_to=effective_to,
        )

    def __repr__(self) -> str:
        return (
            f"ReferenceEd25519EffectAttestationSigner(identity={self._identity!r}, "
            f"key_id={self._key_id!r}, role={self._role.value}, reference=True)"
        )


def mint_effect_attestation(
    observation: ExecutionObservation,
    *,
    signer: EffectAttestationSignerPort,
    tenant_id: str,
    attested_at: datetime,
    production_mode: bool = False,
) -> EffectAttestation:
    """Wrap ``observation`` and sign it with ``signer`` under the signer's role.

    Under ``production_mode=True`` a reference signer — by class, by subclass, or
    by the ``is_reference_signer`` mark — is refused before any byte is signed.
    The observation is wrapped as handed in: nothing is added, repaired or
    reinterpreted, and a fact this package cannot canonicalize refuses here.
    """

    if signer is None or not isinstance(signer, EffectAttestationSignerPort):
        raise _BoundaryError("signer must implement EffectAttestationSignerPort")
    if type(production_mode) is not bool:
        raise _BoundaryError("production_mode must be exactly a bool")
    if production_mode and (
        isinstance(signer, ReferenceEd25519EffectAttestationSigner)
        or getattr(signer, "is_reference_signer", True) is not False
    ):
        raise _BoundaryError(
            "production_mode=True refuses a reference signer; a production key custodian "
            "must implement EffectAttestationSignerPort with is_reference_signer=False"
        )
    role = require_role("signer.attester_role", signer.attester_role)
    payload = effect_attestation_signing_payload(
        observation=observation,
        tenant_id=tenant_id,
        attester_role=role,
        attester_identity=signer.attester_identity,
        attester_key_id=signer.attester_key_id,
        attested_at=require_aware_utc("attested_at", attested_at),
    )
    signature = signer.sign_effect_attestation(effect_attestation_signing_bytes(payload))
    return EffectAttestation(
        observation=observation,
        tenant_id=tenant_id,
        attester_role=role,
        attester_identity=signer.attester_identity,
        attester_key_id=signer.attester_key_id,
        attested_at=attested_at,
        signature=signature,
    )
