"""Signing a comparison result, and the one reference signer — refused in production.

No production signer exists here. No key is loaded from a file, an environment
variable, a network or a discovery service; no key is generated; no credential
is held. :class:`ReferenceEd25519ComparisonResultSigner` derives a key from a
caller-supplied seed through the Trusted Evidence Authority's signing-key type,
exists so the suite and a local composition root can produce genuine
signatures, and is structurally marked ``is_reference_signer = True`` so
:func:`sign_comparison_result` refuses it — and every subclass of it — under
``production_mode=True``. An HSM- or KMS-backed custodian implements the same
:class:`ComparisonResultSignerPort` at the study harness's composition root
and is outside this slice (ADR §3, "who holds the key").
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ugence_reasoning_method_governance.api import ReadinessComparisonResult
from ugence_trusted_evidence_authority import (
    TrustAnchorRecord,
    TrustedEvidenceSigningKey,
    encode_public_key,
    encode_signature,
)

from .attestation import (
    SignedComparisonResult,
    comparison_result_signing_bytes,
    comparison_result_signing_payload,
)
from .canonical import require_aware_utc, require_canonical_identifier, require_exact_type
from .errors import ComparisonResultAttestationContractError as _Error
from .errors import ComparisonResultAttestationSigningBoundaryError as _BoundaryError
from .identifiers import (
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE,
)
from .roles import ComparisonResultAttesterRole, capability_for_role, require_role

__all__ = [
    "ComparisonResultSignerPort",
    "ReferenceEd25519ComparisonResultSigner",
    "sign_comparison_result",
]


@runtime_checkable
class ComparisonResultSignerPort(Protocol):
    """What a key custodian must present to sign a comparison result.

    A signer speaks for exactly one ``(identity, key_id, role)``; it is asked to
    sign framed bytes and returns the canonical 128-hex signature. Whether the
    private half lives in memory, an HSM or a KMS is invisible here.
    """

    #: ``True`` only for a reference/test signer. Production signing refuses one.
    is_reference_signer: bool

    @property
    def signer_identity(self) -> str: ...

    @property
    def signer_key_id(self) -> str: ...

    @property
    def signer_role(self) -> ComparisonResultAttesterRole: ...

    def sign_comparison_result(self, signed_bytes: bytes) -> str: ...


class ReferenceEd25519ComparisonResultSigner:
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
        signer_identity: str,
        signer_key_id: str,
        signer_role: ComparisonResultAttesterRole,
    ) -> None:
        require_exact_type("seed", seed, bytes)
        object.__setattr__(self, "_identity",
                           require_canonical_identifier("signer_identity", signer_identity))
        object.__setattr__(self, "_key_id",
                           require_canonical_identifier("signer_key_id", signer_key_id))
        object.__setattr__(self, "_role", require_role("signer_role", signer_role))
        object.__setattr__(self, "_signing_key", TrustedEvidenceSigningKey(seed))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("ReferenceEd25519ComparisonResultSigner is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("ReferenceEd25519ComparisonResultSigner is immutable")

    def __reduce__(self):
        raise TypeError("a signer is never pickled; a private key is not a value")

    @property
    def signer_identity(self) -> str:
        return self._identity

    @property
    def signer_key_id(self) -> str:
        return self._key_id

    @property
    def signer_role(self) -> ComparisonResultAttesterRole:
        return self._role

    def sign_comparison_result(self, signed_bytes: bytes) -> str:
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
            signature_profile=COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE,
            signature_encoding=COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING,
            effective_from=effective_from,
            effective_to=effective_to,
        )

    def __repr__(self) -> str:
        return (
            f"ReferenceEd25519ComparisonResultSigner(identity={self._identity!r}, "
            f"key_id={self._key_id!r}, role={self._role.value}, reference=True)"
        )


def sign_comparison_result(
    result: ReadinessComparisonResult,
    *,
    signer: ComparisonResultSignerPort,
    signed_at: datetime,
    production_mode: bool = False,
) -> SignedComparisonResult:
    """Wrap ``result`` and sign it with ``signer`` under the signer's role.

    Under ``production_mode=True`` a reference signer — by class, by subclass, or
    by the ``is_reference_signer`` mark — is refused before any byte is signed.
    The result is wrapped as handed in: nothing is added, repaired or
    reinterpreted, and a result this package cannot canonicalize, or whose
    engine identity the signer does not hold, refuses here.
    """

    if signer is None or not isinstance(signer, ComparisonResultSignerPort):
        raise _BoundaryError("signer must implement ComparisonResultSignerPort")
    if type(production_mode) is not bool:
        raise _BoundaryError("production_mode must be exactly a bool")
    if production_mode and (
        isinstance(signer, ReferenceEd25519ComparisonResultSigner)
        or getattr(signer, "is_reference_signer", True) is not False
    ):
        raise _BoundaryError(
            "production_mode=True refuses a reference signer; a production key custodian "
            "must implement ComparisonResultSignerPort with is_reference_signer=False"
        )
    role = require_role("signer.signer_role", signer.signer_role)
    try:
        payload = comparison_result_signing_payload(
            result=result,
            signer_role=role,
            signer_identity=signer.signer_identity,
            signer_key_id=signer.signer_key_id,
            signed_at=require_aware_utc("signed_at", signed_at),
        )
    except _Error as exc:
        if "signer_identity must equal the result's engine_identity" in str(exc):
            raise _BoundaryError(str(exc)) from exc
        raise
    signature = signer.sign_comparison_result(comparison_result_signing_bytes(payload))
    return SignedComparisonResult(
        result=result,
        signer_role=role,
        signer_identity=signer.signer_identity,
        signer_key_id=signer.signer_key_id,
        signed_at=signed_at,
        signature=signature,
    )
