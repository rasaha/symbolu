"""The verification seam: one port, one pure result, one verifier.

The verifier answers exactly one question — *did the party the attestation
names, under the role it names, sign these exact bytes with a key the Trusted
Evidence Authority's anchors currently trust for that role?* — and returns
the answer as a typed value. It never raises for an invalid input, because a
raised exception tempts a caller to treat a swallowed one as a pass.

What a ``VERIFIED`` result establishes is **provenance and integrity**, and it
says so on its face. It carries no field that can be read as "the effect
occurred": :attr:`EffectAttestationVerificationResult.factual_correctness_established`
is permanently ``False``, on a verified result as on a refused one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ugence_governance_contracts import ExecutionObservation
from ugence_trusted_evidence_authority import (
    TrustAnchorRecord,
    TrustAnchorResolution,
    TrustedEvidenceRefusalReason,
    decode_signature,
)

from .attestation import (
    EffectAttestation,
    effect_attestation_signing_bytes,
    effect_attestation_signing_payload,
    observation_digest,
)
from .canonical import (
    canonical_digest,
    is_canonical_digest,
    require_aware_utc,
    require_canonical_identifier,
    require_exact_type,
)
from .errors import EffectAttestationConfigurationError as _ConfigError
from .errors import EffectAttestationContractError as _Error
from .identifiers import (
    EFFECT_ATTESTATION_ESTABLISHES,
    EFFECT_ATTESTATION_SCHEMA_VERSION,
    EFFECT_ATTESTATION_SIGNATURE_ALGORITHM,
    EFFECT_ATTESTATION_SIGNATURE_ENCODING,
    EFFECT_ATTESTATION_SIGNATURE_PROFILE,
    EFFECT_ATTESTATION_SIGNING_DOMAIN,
)
from .outcomes import EffectAttestationRefusalReason as _Reason
from .outcomes import EffectAttestationVerificationOutcome as _Outcome
from .roles import EFFECT_ATTESTER_ROLE_ESTABLISHES, EffectAttesterRole, capability_for_role
from .trust import (
    anchor_coordinate_digest,
    anchor_lifecycle_refusal,
    anchor_record_digest,
    anchor_verification_key,
    effect_attester_coordinate,
    require_production_resolver,
)

__all__ = [
    "EffectAttestationVerificationResult",
    "EffectAttestationVerifierPort",
    "Ed25519EffectAttestationVerifier",
]


@dataclass(frozen=True)
class EffectAttestationVerificationResult:
    """The pure, evidence-bound answer to one verification at one instant.

    Binds what was asked (role, tenant, observation digest), what was claimed
    (attester identity and key, payload digest), what was consulted (the exact
    coordinate and, when one resolved, the anchor revision), when, and the
    outcome with its one typed reason. Nothing here is an authorization, an
    admission, a reconciliation verdict or a statement that the effect is real.
    """

    outcome: _Outcome
    refusal_reason: Optional[_Reason]
    attester_role: EffectAttesterRole
    attester_identity: str
    attester_key_id: str
    tenant_id: str
    observation_digest: str
    signing_payload_digest: Optional[str]
    anchor_coordinate_digest: str
    anchor_record_digest: Optional[str]
    evaluated_at: datetime
    detail: str = ""

    def __post_init__(self) -> None:
        require_exact_type("outcome", self.outcome, _Outcome)
        if (self.outcome is _Outcome.VERIFIED) != (self.refusal_reason is None):
            raise _Error(
                "a VERIFIED result carries no refusal reason and a REFUSED result carries "
                "exactly one; there is no third state"
            )
        if self.refusal_reason is not None:
            require_exact_type("refusal_reason", self.refusal_reason, _Reason)
        require_exact_type("attester_role", self.attester_role, EffectAttesterRole)
        require_canonical_identifier("attester_identity", self.attester_identity)
        require_canonical_identifier("attester_key_id", self.attester_key_id)
        require_canonical_identifier("tenant_id", self.tenant_id)
        if not is_canonical_digest(self.observation_digest):
            raise _Error("observation_digest must be a canonical sha256: digest")
        if not is_canonical_digest(self.anchor_coordinate_digest):
            raise _Error("anchor_coordinate_digest must be a canonical sha256: digest")
        if self.outcome is _Outcome.VERIFIED:
            if not is_canonical_digest(self.signing_payload_digest):
                raise _Error("a VERIFIED result must bind the signing-payload digest")
            if not is_canonical_digest(self.anchor_record_digest):
                raise _Error("a VERIFIED result must bind the anchor revision it trusted")
        else:
            for name, value in (
                ("signing_payload_digest", self.signing_payload_digest),
                ("anchor_record_digest", self.anchor_record_digest),
            ):
                if value is not None and not is_canonical_digest(value):
                    raise _Error(f"{name} must be a canonical digest or None")
        require_aware_utc("evaluated_at", self.evaluated_at)
        require_exact_type("detail", self.detail, str)

    @property
    def establishes(self) -> str:
        """Always ``PROVENANCE_AND_INTEGRITY_ONLY``. There is no other value."""

        return EFFECT_ATTESTATION_ESTABLISHES

    @property
    def role_establishes(self) -> str:
        """What this role's verified signature does and does not prove (SE-2)."""

        return EFFECT_ATTESTER_ROLE_ESTABLISHES[self.attester_role]

    @property
    def factual_correctness_established(self) -> bool:
        """Permanently ``False``. A verified signature proves who signed what;
        it never proves the observed effect is true (ADR §4, first bullet)."""

        return False


@runtime_checkable
class EffectAttestationVerifierPort(Protocol):
    """The seam a composition root injects. Implemented here by exactly one class."""

    def verify(
        self,
        *,
        attestation: Optional[EffectAttestation],
        expected_role: EffectAttesterRole,
        expected_tenant_id: str,
        expected_observation: ExecutionObservation,
        as_of: datetime,
        expected_anchor_record_digest: Optional[str] = None,
    ) -> EffectAttestationVerificationResult:
        ...


class Ed25519EffectAttestationVerifier:
    """The one verifier. Resolves through an injected TEA resolver; verifies
    through TEA's strictly validated verification key (SE-4, SE-5).

    ``production_mode=True`` refuses a reference-grade resolver at construction,
    so a reference directory cannot reach a determination in production.
    """

    __slots__ = ("_resolver", "_production_mode")

    #: This verifier performs the real check; it is never a placeholder.
    is_production_authoritative: bool = True

    def __init__(self, *, trust_anchor_resolver, production_mode: bool = False) -> None:
        if trust_anchor_resolver is None:
            raise _ConfigError(
                "a trust-anchor resolver is required; there is no default resolver, no "
                "ambient anchor store and no permissive fallback"
            )
        if not hasattr(trust_anchor_resolver, "resolve"):
            raise _ConfigError(
                "the trust-anchor resolver must implement resolve(coordinate) -> "
                "TrustAnchorResolution"
            )
        if type(production_mode) is not bool:
            raise _ConfigError("production_mode must be exactly a bool")
        if production_mode:
            require_production_resolver(trust_anchor_resolver)
        object.__setattr__(self, "_resolver", trust_anchor_resolver)
        object.__setattr__(self, "_production_mode", production_mode)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(f"Ed25519EffectAttestationVerifier is immutable; cannot set {name!r}")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"Ed25519EffectAttestationVerifier is immutable; cannot delete {name!r}")

    @property
    def production_mode(self) -> bool:
        return self._production_mode

    # ------------------------------------------------------------------ seam
    def verify(
        self,
        *,
        attestation: Optional[EffectAttestation],
        expected_role: EffectAttesterRole,
        expected_tenant_id: str,
        expected_observation: ExecutionObservation,
        as_of: datetime,
        expected_anchor_record_digest: Optional[str] = None,
    ) -> EffectAttestationVerificationResult:
        """Verify one attestation against the caller's own facts at ``as_of``.

        The caller's ``expected_role``, ``expected_tenant_id`` and
        ``expected_observation`` are the ground truth every claim in the
        attestation is reconciled against; the attestation supplies only the
        claim about **who signed**, which the anchor resolution then tests.
        Returns a typed result and never raises for an invalid input.
        """

        # The result must be able to name what was asked even when the
        # attestation is absent or malformed, so the caller's own facts are
        # admitted first, and a caller-side contract violation raises: it is
        # a programming error, not external trust state.
        role = require_exact_type("expected_role", expected_role, EffectAttesterRole)
        tenant = require_canonical_identifier("expected_tenant_id", expected_tenant_id)
        require_exact_type("expected_observation", expected_observation, ExecutionObservation)
        instant = require_aware_utc("as_of", as_of)
        expected_digest = observation_digest(expected_observation)
        if expected_anchor_record_digest is not None and not is_canonical_digest(
            expected_anchor_record_digest
        ):
            raise _Error("expected_anchor_record_digest must be a canonical digest or None")

        claimed_identity = "unattested"
        claimed_key = "unattested"
        coordinate_digest = canonical_digest({"unresolved": True})
        if type(attestation) is EffectAttestation:
            claimed_identity = attestation.attester_identity
            claimed_key = attestation.attester_key_id
            coordinate_digest = anchor_coordinate_digest(
                effect_attester_coordinate(
                    role=role, attester_identity=claimed_identity, attester_key_id=claimed_key
                )
            )

        def refuse(reason: _Reason, detail: str, *, payload_digest=None, anchor_digest=None):
            return EffectAttestationVerificationResult(
                outcome=_Outcome.REFUSED,
                refusal_reason=reason,
                attester_role=role,
                attester_identity=claimed_identity,
                attester_key_id=claimed_key,
                tenant_id=tenant,
                observation_digest=expected_digest,
                signing_payload_digest=payload_digest,
                anchor_coordinate_digest=coordinate_digest,
                anchor_record_digest=anchor_digest,
                evaluated_at=instant,
                detail=detail,
            )

        try:
            return self._verify(
                attestation, role, tenant, expected_observation, instant,
                expected_anchor_record_digest, expected_digest, refuse,
            )
        except Exception as exc:  # noqa: BLE001 - the fail-closed terminal
            return refuse(
                _Reason.VERIFICATION_UNAVAILABLE,
                f"verification could not reach a determination: {type(exc).__name__}",
            )

    def _verify(self, attestation, role, tenant, expected_observation, instant,
                expected_anchor_record_digest, expected_digest, refuse):
        # === 1. the attestation itself ===============================================
        if attestation is None:
            return refuse(_Reason.ATTESTATION_ABSENT, "no attestation was supplied; absence is a refusal")
        if type(attestation) is not EffectAttestation:
            return refuse(_Reason.UNSUPPORTED_EXACT_TYPE, "attestation must be exactly EffectAttestation")

        # === 2. contract admission ===================================================
        if attestation.schema_version != EFFECT_ATTESTATION_SCHEMA_VERSION:
            return refuse(_Reason.UNSUPPORTED_SCHEMA_VERSION, "unsupported schema version")
        if attestation.signing_domain != EFFECT_ATTESTATION_SIGNING_DOMAIN:
            return refuse(_Reason.UNSUPPORTED_SIGNING_DOMAIN, "unsupported signing domain")
        if attestation.signature_algorithm != EFFECT_ATTESTATION_SIGNATURE_ALGORITHM:
            return refuse(_Reason.UNSUPPORTED_ALGORITHM, "unsupported signature algorithm")
        if attestation.signature_profile != EFFECT_ATTESTATION_SIGNATURE_PROFILE:
            return refuse(_Reason.UNSUPPORTED_PROFILE, "unsupported signature profile")
        if attestation.signature_encoding != EFFECT_ATTESTATION_SIGNATURE_ENCODING:
            return refuse(_Reason.UNSUPPORTED_ENCODING, "unsupported signature encoding")

        # === 3. reconciliation against the caller's own facts ========================
        if attestation.attester_role is not role:
            return refuse(_Reason.ROLE_MISMATCH,
                          "the attestation was signed under a different role than the one expected")
        if attestation.tenant_id != tenant:
            return refuse(_Reason.WRONG_TENANT, "the attestation names a different tenant")
        if attestation.observation_digest != expected_digest:
            return refuse(_Reason.OBSERVATION_MISMATCH,
                          "the wrapped observation is not the observation the caller holds")

        # === 4. anchor resolution at the exact coordinate ============================
        coordinate = effect_attester_coordinate(
            role=role,
            attester_identity=attestation.attester_identity,
            attester_key_id=attestation.attester_key_id,
        )
        try:
            resolution = self._resolver.resolve(coordinate, as_of=instant)
        except Exception as exc:  # noqa: BLE001 - a resolver that raises is unavailable
            return refuse(_Reason.ANCHOR_UNAVAILABLE,
                          f"the trust-anchor resolver raised {type(exc).__name__}")
        if type(resolution) is not TrustAnchorResolution:
            return refuse(_Reason.ANCHOR_UNAVAILABLE,
                          "the resolver returned something other than a TrustAnchorResolution")
        if resolution.coordinate != coordinate:
            return refuse(_Reason.ANCHOR_COORDINATE_MISMATCH,
                          "the resolver answered a coordinate it was not asked")
        if resolution.refusal_reason is not None:
            if resolution.refusal_reason in (
                TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TRUST_ANCHOR_MISSING,
                TrustedEvidenceRefusalReason.TRUSTED_EVIDENCE_TRUST_ANCHOR_NOT_CONFIGURED,
            ):
                return refuse(_Reason.ANCHOR_UNKNOWN, "no anchor is configured at the exact coordinate")
            return refuse(_Reason.ANCHOR_UNAVAILABLE,
                          f"the resolver refused: {resolution.refusal_reason.value}")
        anchor = resolution.anchor
        if type(anchor) is not TrustAnchorRecord:
            return refuse(_Reason.ANCHOR_UNAVAILABLE, "the resolution carries no exact anchor record")
        # Re-check the record itself against the asked coordinate: a record swapped
        # into a genuine resolution after construction must not verify.
        if (
            anchor.authority_id != coordinate.authority_id
            or anchor.key_id != coordinate.key_id
            or anchor.capability is not coordinate.capability
        ):
            return refuse(_Reason.ANCHOR_COORDINATE_MISMATCH,
                          "the resolved record does not answer the asked coordinate")
        if anchor.capability is not capability_for_role(role):
            return refuse(_Reason.WRONG_CAPABILITY,
                          "the anchor is not filed under this role's capability")
        revision = anchor_record_digest(anchor)

        # === 5. lifecycle at the trusted instant =====================================
        lifecycle = anchor_lifecycle_refusal(anchor, instant)
        if lifecycle is not None:
            return refuse(lifecycle, "the anchor is not usable at the trusted instant",
                          anchor_digest=revision)
        if expected_anchor_record_digest is not None and revision != expected_anchor_record_digest:
            return refuse(_Reason.ANCHOR_REVISION_MISMATCH,
                          "the resolved anchor revision is not the one the caller expected",
                          anchor_digest=revision)

        # === 6. key admission, payload recomputation, signature ======================
        try:
            key = anchor_verification_key(anchor)
        except Exception as exc:  # noqa: BLE001 - a key that fails the point check
            return refuse(_Reason.KEY_MATERIAL_INVALID,
                          f"the anchor's public key was refused at admission: {type(exc).__name__}",
                          anchor_digest=revision)
        payload = effect_attestation_signing_payload(
            observation=expected_observation,
            tenant_id=tenant,
            attester_role=role,
            attester_identity=attestation.attester_identity,
            attester_key_id=attestation.attester_key_id,
            attested_at=attestation.attested_at,
            schema_version=attestation.schema_version,
            signing_domain=attestation.signing_domain,
            signature_algorithm=attestation.signature_algorithm,
            signature_profile=attestation.signature_profile,
            signature_encoding=attestation.signature_encoding,
        )
        recomputed = effect_attestation_signing_bytes(payload)
        payload_digest = canonical_digest(payload)
        if recomputed != attestation.signed_bytes():
            return refuse(_Reason.PAYLOAD_MISMATCH,
                          "the independently recomputed signing payload is not byte-identical "
                          "to the one the attestation claims was signed",
                          payload_digest=payload_digest, anchor_digest=revision)
        try:
            signature = decode_signature(attestation.signature, "signature")
        except Exception as exc:  # noqa: BLE001
            return refuse(_Reason.MALFORMED_SIGNATURE,
                          f"the signature could not be decoded: {type(exc).__name__}",
                          payload_digest=payload_digest, anchor_digest=revision)
        if key.verify(recomputed, signature) is not True:
            return refuse(_Reason.SIGNATURE_INVALID,
                          "the signature did not verify under the resolved anchor",
                          payload_digest=payload_digest, anchor_digest=revision)

        return EffectAttestationVerificationResult(
            outcome=_Outcome.VERIFIED,
            refusal_reason=None,
            attester_role=role,
            attester_identity=attestation.attester_identity,
            attester_key_id=attestation.attester_key_id,
            tenant_id=tenant,
            observation_digest=expected_digest,
            signing_payload_digest=payload_digest,
            anchor_coordinate_digest=anchor_coordinate_digest(coordinate),
            anchor_record_digest=revision,
            evaluated_at=instant,
            detail=EFFECT_ATTESTER_ROLE_ESTABLISHES[role],
        )

    def __repr__(self) -> str:
        return (
            f"Ed25519EffectAttestationVerifier(resolver={type(self._resolver).__name__}, "
            f"production_mode={self._production_mode})"
        )
