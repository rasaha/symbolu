"""The authoritative producer-authenticity verification routine.

The whole point, in one sentence
--------------------------------
The verifier **recomputes** the signed payload from facts it takes out of the Phase 5A
candidate — never from the attestation — and refuses unless the recomputed bytes are
identical to the bytes the attestation claims were signed. That is what separates this from
a verifier that merely checks a signature over whatever it was handed: a self-consistent
forgery whose signature verifies under its own key still fails, because its key is not
configured at the coordinate it names, and a genuine attestation for a *different*
recommendation, tenant or subject fails at the recomputation before a key is even resolved.

Ordered, stop at the first failing group, deterministic
-------------------------------------------------------
Identical inputs always yield the identical outcome, and no later group can rescue an
earlier failure:

#. **exact-type admission** — candidate, attestation and ``as_of``;
#. **contract admission** — schema tag, signing purpose, algorithm, profile, encoding;
#. **reconciliation** — recommendation id and digest, tenant, subject, subject type, taken
   from the candidate and compared against the attestation's claims;
#. **payload recomputation** — rebuild the canonical payload from the reconciled facts and
   require byte equality with the attestation's own signing payload;
#. **anchor resolution** — at the exact ``(issuer, key_id, capability)`` coordinate;
#. **anchor identity re-check** — the resolver may not answer a question it was not asked;
#. **anchor lifecycle** — revoked, disabled, not-yet-valid, expired, at the injected instant;
#. **profile and encoding agreement** — attestation against the resolved anchor;
#. **signature decoding** — canonical lowercase base16 of exactly the Ed25519 length;
#. **signature verification** — under the anchor's strictly validated public key.

Only after all ten does a :class:`~.verified.VerifiedProducerAttestation` exist.

No placeholder, no optionality
------------------------------
The resolver and the signature verifier are **required** constructor arguments with no
defaults. There is no verifier in this distribution that returns success unconditionally,
no permissive fallback, no hardcoded trusted key, no caller-supplied trust anchor and no
path that converts an exception into a success — an unexpected exception becomes
``VERIFICATION_UNAVAILABLE``, which is a refusal. The only shipped "no anchors" posture is
``DenyAllTrustAnchorDirectory``, which refuses everything.

No clock
--------
``as_of`` is an injected timezone-aware instant. Nothing here reads a wall clock, and a
naive datetime is refused rather than assumed to be UTC.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ugence_cloud_scaling_authorization_contracts import CapacityAuthorizationCandidate
from ugence_trusted_evidence_authority import (
    TrustAnchorRecord,
    TrustAnchorResolution,
    decode_signature,
)

from .attestation import ProducerAttestationV2, producer_attestation_signing_payload
from .canonical import canonical_bytes, canonical_digest, require_aware_utc
from .errors import ProducerAttestationConfigurationError as _ConfigError
from .identifiers import (
    PRODUCER_ATTESTATION_CAPABILITY,
    PRODUCER_ATTESTATION_SIGNATURE_ENCODING,
    PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
    PRODUCER_ATTESTATION_V2_SCHEMA_VERSION,
    SUPPORTED_V2_SIGNATURE_ALGORITHMS,
    SUPPORTED_V2_SIGNING_PURPOSES,
    VERIFICATION_PROFILE,
    VERIFICATION_PROFILE_VERSION,
)
from .outcomes import ProducerAuthenticityOutcome as _Outcome
from .trust import (
    anchor_coordinate_digest,
    anchor_lifecycle_outcome,
    anchor_record_digest,
    anchor_verification_key,
    producer_anchor_coordinate,
    require_production_resolver,
)
from .verified import VerifiedProducerAttestation, _VERIFICATION_TOKEN

__all__ = [
    "ProducerSignatureVerifierPort",
    "Ed25519ProducerSignatureVerifier",
    "ProducerAttestationRefusal",
    "ProducerAuthenticityResult",
    "ProducerAttestationVerifier",
]


@runtime_checkable
class ProducerSignatureVerifierPort(Protocol):
    """Check one Ed25519 signature against one resolved anchor's public key.

    Deliberately the narrowest possible surface: it receives an anchor, the exact bytes and
    the encoded signature, and returns a bool. It resolves nothing, decides nothing about
    trust, reads no clock and cannot admit anything on its own — every gate around it has
    already run by the time it is called, and its ``False`` is final.
    """

    #: Must be ``True`` for a verifier admitted under ``production_mode=True``.
    is_production_authoritative: bool

    def verify_producer_signature(
        self, *, anchor: TrustAnchorRecord, signed_input: bytes, signature: str
    ) -> bool:
        """``True`` only if the maintained backend accepts the signature."""
        ...


class Ed25519ProducerSignatureVerifier:
    """The production-grade Ed25519 signature check, over maintained backends.

    Not a reference stub and not a test double: it performs the real signature equation
    through the Trusted Evidence Authority's ``TrustedEvidenceVerificationKey``, which wraps
    ``cryptography``/OpenSSL for verification and libsodium for strict point validation.
    There is no branch in this class that returns ``True`` without the backend having
    accepted the signature, and no exception path that becomes a success: every malformed
    input and every backend rejection yields ``False``.
    """

    __slots__ = ()

    #: Production-grade. This is the real signature check, not a placeholder.
    is_production_authoritative: bool = True

    def verify_producer_signature(
        self, *, anchor: TrustAnchorRecord, signed_input: bytes, signature: str
    ) -> bool:
        if type(signed_input) is not bytes or len(signed_input) == 0:
            return False
        try:
            signature_bytes = decode_signature(
                signature, "Ed25519ProducerSignatureVerifier.signature"
            )
        except Exception:
            return False
        try:
            key = anchor_verification_key(anchor)
        except Exception:
            return False
        return key.verify(signed_input, signature_bytes) is True

    def __repr__(self) -> str:
        return "Ed25519ProducerSignatureVerifier()"


@dataclass(frozen=True)
class ProducerAttestationRefusal:
    """One typed refusal. The outcome is the answer; the message is for humans only.

    ``detail`` never carries the distinguishing information: two different failures are
    told apart by :attr:`outcome`, never by parsing prose. Tests assert on the member.
    """

    outcome: _Outcome
    detail: str = ""

    def __post_init__(self) -> None:
        if type(self.outcome) is not _Outcome:
            raise TypeError(
                "ProducerAttestationRefusal.outcome must be exactly a "
                f"ProducerAuthenticityOutcome (got {type(self.outcome).__name__})"
            )
        if self.outcome is _Outcome.VERIFIED:
            raise ValueError(
                "VERIFIED is not a refusal; a successful verification returns a "
                "VerifiedProducerAttestation, never a refusal carrying a success member"
            )


@dataclass(frozen=True)
class ProducerAuthenticityResult:
    """The typed outcome of one verification. Exactly one of the two branches is present.

    There is **no boolean success flag**. A caller must branch on which of
    :attr:`verified_attestation` and :attr:`refusal` is present, and the presence of an
    artifact is decided by this module, never supplied by a caller. Carrying both would be
    a verified refusal, and carrying neither would be an untyped silence; both are refused
    at construction, so neither state exists to read optimistically.
    """

    verified_attestation: Optional[VerifiedProducerAttestation] = None
    refusal: Optional[ProducerAttestationRefusal] = None

    def __post_init__(self) -> None:
        if (self.verified_attestation is None) == (self.refusal is None):
            raise ValueError(
                "a ProducerAuthenticityResult must carry exactly one of a verified "
                "attestation or a typed refusal"
            )
        if self.verified_attestation is not None and (
            type(self.verified_attestation) is not VerifiedProducerAttestation
        ):
            raise TypeError(
                "ProducerAuthenticityResult.verified_attestation must be exactly a "
                "VerifiedProducerAttestation"
            )
        if self.refusal is not None and (
            type(self.refusal) is not ProducerAttestationRefusal
        ):
            raise TypeError(
                "ProducerAuthenticityResult.refusal must be exactly a "
                "ProducerAttestationRefusal"
            )

    @property
    def outcome(self) -> _Outcome:
        """The typed outcome, whichever branch is present. Derived, never stored."""

        if self.refusal is not None:
            return self.refusal.outcome
        return _Outcome.VERIFIED


class ProducerAttestationVerifier:
    """The authoritative producer-authenticity verifier. Nothing else mints a verified artifact.

    Both collaborators are **required** keyword arguments with no defaults, so there is no
    posture in which this class verifies against something it was not given. Under
    ``production_mode=True`` the resolver must be production-authoritative (or the ratified
    deny-all posture) and the signature verifier must declare itself production-authoritative;
    both are checked at construction, so a reference component cannot reach a determination.
    """

    __slots__ = ("_resolver", "_signature_verifier", "_production_mode")

    def __init__(
        self,
        *,
        trust_anchor_resolver,
        signature_verifier,
        production_mode: bool = False,
    ) -> None:
        if trust_anchor_resolver is None:
            raise _ConfigError(
                "a trust-anchor resolver is required; there is no default resolver, no "
                "ambient anchor store and no permissive fallback"
            )
        if signature_verifier is None:
            raise _ConfigError(
                "a signature verifier is required; there is no default verifier and no "
                "posture in which the signature check is skipped"
            )
        if not hasattr(trust_anchor_resolver, "resolve"):
            raise _ConfigError(
                "the trust-anchor resolver must implement resolve(coordinate) -> "
                "TrustAnchorResolution"
            )
        if not hasattr(signature_verifier, "verify_producer_signature"):
            raise _ConfigError(
                "the signature verifier must implement verify_producer_signature(...)"
            )
        if production_mode:
            require_production_resolver(trust_anchor_resolver)
            if (
                getattr(signature_verifier, "is_production_authoritative", False)
                is not True
            ):
                raise _ConfigError(
                    "a production ProducerSignatureVerifierPort must be "
                    "production-authoritative (is_production_authoritative=True); a "
                    "reference or permissive verifier cannot establish producer "
                    f"authenticity in production (got {type(signature_verifier).__name__})"
                )
        object.__setattr__(self, "_resolver", trust_anchor_resolver)
        object.__setattr__(self, "_signature_verifier", signature_verifier)
        object.__setattr__(self, "_production_mode", bool(production_mode))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError(
            f"ProducerAttestationVerifier is immutable; cannot set {name!r}. Rebinding "
            "the resolver or the signature verifier after construction is exactly the "
            "component-swap the production guard exists to prevent."
        )

    def __delattr__(self, name: str) -> None:
        raise AttributeError(
            f"ProducerAttestationVerifier is immutable; cannot delete {name!r}"
        )

    @property
    def production_mode(self) -> bool:
        return self._production_mode

    # -- the authoritative routine ---------------------------------------------------- #

    def verify(
        self,
        *,
        candidate: CapacityAuthorizationCandidate,
        attestation: Optional[ProducerAttestationV2],
        as_of: datetime,
    ) -> ProducerAuthenticityResult:
        """Verify one producer attestation against one Phase 5A candidate at ``as_of``.

        Returns a typed result. Never raises for an invalid input: an invalid input is an
        expected answer to the question, and raising would tempt a caller into treating a
        swallowed exception as a pass. An unexpected internal failure becomes
        ``VERIFICATION_UNAVAILABLE`` — still a refusal, never a success.
        """

        try:
            return self._verify(candidate=candidate, attestation=attestation, as_of=as_of)
        except Exception as exc:  # noqa: BLE001 - deliberate fail-closed terminal
            # An exception is never converted into a success. It is converted into a
            # refusal, and the refusal names that no determination was reached.
            return _refuse(
                _Outcome.VERIFICATION_UNAVAILABLE,
                f"verification could not reach a determination: {type(exc).__name__}",
            )

    def _verify(
        self,
        *,
        candidate: CapacityAuthorizationCandidate,
        attestation: Optional[ProducerAttestationV2],
        as_of: datetime,
    ) -> ProducerAuthenticityResult:
        # === 1. exact-type admission =====================================================
        if attestation is None:
            return _refuse(
                _Outcome.ATTESTATION_ABSENT,
                "no producer attestation was supplied; absence is a refusal",
            )
        if type(attestation) is not ProducerAttestationV2:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "attestation must be exactly ProducerAttestationV2",
            )
        if type(candidate) is not CapacityAuthorizationCandidate:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "candidate must be exactly CapacityAuthorizationCandidate",
            )
        if type(as_of) is not datetime or as_of.tzinfo is None or as_of.utcoffset() is None:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "as_of must be an exact timezone-aware datetime; this package reads no "
                "clock and refuses a naive instant rather than assuming UTC",
            )
        instant = require_aware_utc("as_of", as_of)

        # === 2. contract admission =======================================================
        if attestation.schema_version != PRODUCER_ATTESTATION_V2_SCHEMA_VERSION:
            return _refuse(
                _Outcome.UNSUPPORTED_SCHEMA_VERSION,
                "the attestation names a schema tag this verifier does not implement",
            )
        if attestation.signing_purpose not in SUPPORTED_V2_SIGNING_PURPOSES:
            return _refuse(
                _Outcome.UNSUPPORTED_SIGNING_PURPOSE,
                "the attestation names a signing purpose outside the closed producer set",
            )
        if attestation.signature_algorithm not in SUPPORTED_V2_SIGNATURE_ALGORITHMS:
            return _refuse(
                _Outcome.UNSUPPORTED_ALGORITHM,
                "the attestation names an algorithm outside the closed admitted set",
            )
        if attestation.signature_profile != PRODUCER_ATTESTATION_SIGNATURE_PROFILE:
            return _refuse(
                _Outcome.UNSUPPORTED_PROFILE,
                "the attestation names a signature profile this verifier does not admit",
            )
        if attestation.signature_encoding != PRODUCER_ATTESTATION_SIGNATURE_ENCODING:
            return _refuse(
                _Outcome.UNSUPPORTED_ENCODING,
                "the attestation names a signature encoding this verifier does not admit",
            )

        # === 3. reconciliation against the candidate's own reconciled facts ==============
        # Every value below is read from the CANDIDATE. Nothing in this block reads the
        # corresponding value from the attestation except to compare against it.
        if attestation.recommendation_id != candidate.recommendation_id:
            return _refuse(
                _Outcome.RECOMMENDATION_ID_MISMATCH,
                "the attestation names a different recommendation than the candidate",
            )
        if attestation.recommendation_digest != candidate.recommendation_digest:
            return _refuse(
                _Outcome.RECOMMENDATION_DIGEST_MISMATCH,
                "the attestation binds a different recommendation digest than the "
                "candidate reconciled",
            )
        if attestation.tenant_id != candidate.tenant_id:
            return _refuse(
                _Outcome.WRONG_TENANT,
                "the attestation names a different tenant than the candidate reconciled",
            )
        if attestation.subject_id != candidate.subject_id:
            return _refuse(
                _Outcome.WRONG_SUBJECT,
                "the attestation names a different subject than the candidate reconciled",
            )
        if attestation.subject_type != candidate.subject_type:
            return _refuse(
                _Outcome.WRONG_SUBJECT,
                "the attestation names a different subject type than the candidate",
            )

        # === 4. payload recomputation and byte equality ==================================
        # Rebuilt from the CANDIDATE's reconciled facts plus this package's pinned
        # constants. The producer/issuer/key coordinates are the attestation's claim about
        # WHO signed — they are what the anchor is resolved by, and a wrong claim fails at
        # resolution, not here.
        recomputed = producer_attestation_signing_payload(
            producer_id=attestation.producer_id,
            issuer=attestation.issuer,
            producer_key_id=attestation.producer_key_id,
            tenant_id=candidate.tenant_id,
            subject_id=candidate.subject_id,
            subject_type=candidate.subject_type,
            recommendation_id=candidate.recommendation_id,
            recommendation_digest=candidate.recommendation_digest,
            issued_at=attestation.issued_at,
            signing_purpose=attestation.signing_purpose,
            signature_algorithm=attestation.signature_algorithm,
            signature_profile=attestation.signature_profile,
            signature_encoding=attestation.signature_encoding,
        )
        recomputed_bytes = canonical_bytes(recomputed)
        if recomputed_bytes != attestation.signed_bytes():
            return _refuse(
                _Outcome.PAYLOAD_MISMATCH,
                "the independently recomputed signing payload is not byte-identical to "
                "the representation the attestation claims was signed",
            )
        if canonical_digest(recomputed) != attestation.signing_payload_digest:
            return _refuse(
                _Outcome.PAYLOAD_MISMATCH,
                "the recomputed payload digest does not equal the attestation's own",
            )

        # === 5. anchor resolution at the exact coordinate ================================
        coordinate = producer_anchor_coordinate(
            issuer=attestation.issuer, producer_key_id=attestation.producer_key_id
        )
        try:
            resolution = self._resolver.resolve(coordinate)
        except Exception as exc:  # noqa: BLE001 - a resolver that raises is unavailable
            return _refuse(
                _Outcome.VERIFICATION_UNAVAILABLE,
                f"the trust-anchor resolver raised {type(exc).__name__}",
            )
        if type(resolution) is not TrustAnchorResolution:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "the resolver returned something other than a TrustAnchorResolution",
            )
        anchor = resolution.anchor
        if anchor is None:
            return _refuse(
                _Outcome.ANCHOR_UNKNOWN,
                "no trust anchor is configured at the exact coordinate the attestation "
                "names",
            )
        if type(anchor) is not TrustAnchorRecord:
            return _refuse(
                _Outcome.UNSUPPORTED_EXACT_TYPE,
                "the resolver returned something other than a TrustAnchorRecord",
            )

        # === 6. anchor identity re-check — a resolver may not answer another question ====
        if anchor.authority_id != attestation.issuer:
            return _refuse(
                _Outcome.WRONG_AUTHORITY,
                "the resolved anchor belongs to a different authority than the "
                "attestation's issuer",
            )
        if anchor.key_id != attestation.producer_key_id:
            return _refuse(
                _Outcome.ANCHOR_UNKNOWN,
                "the resolved anchor carries a different key id than was resolved for",
            )
        if anchor.capability is not PRODUCER_ATTESTATION_CAPABILITY:
            return _refuse(
                _Outcome.WRONG_CAPABILITY,
                "the resolved anchor is not entitled to the producer-attestation "
                "capability",
            )

        # === 7. anchor lifecycle at the injected instant =================================
        lifecycle = anchor_lifecycle_outcome(anchor, instant)
        if lifecycle is not None:
            return _refuse(lifecycle, "the resolved anchor is not usable at as_of")

        # === 8. profile and encoding agreement with the resolved anchor ==================
        if anchor.signature_profile != attestation.signature_profile:
            return _refuse(
                _Outcome.UNSUPPORTED_PROFILE,
                "the resolved anchor's signature profile disagrees with the attestation's",
            )
        if anchor.signature_encoding != attestation.signature_encoding:
            return _refuse(
                _Outcome.UNSUPPORTED_ENCODING,
                "the resolved anchor's signature encoding disagrees with the "
                "attestation's",
            )

        # === 9. signature decoding — canonical spelling only =============================
        try:
            decode_signature(attestation.signature, "attestation.signature")
        except Exception:
            return _refuse(
                _Outcome.MALFORMED_SIGNATURE,
                "the signature is not canonical lowercase base16 of an Ed25519 signature",
            )

        # === 10. the signature check itself ==============================================
        try:
            accepted = self._signature_verifier.verify_producer_signature(
                anchor=anchor,
                signed_input=recomputed_bytes,
                signature=attestation.signature,
            )
        except Exception as exc:  # noqa: BLE001 - a verifier that raises is unavailable
            return _refuse(
                _Outcome.VERIFICATION_UNAVAILABLE,
                f"the signature verifier raised {type(exc).__name__}",
            )
        if accepted is not True:
            return _refuse(
                _Outcome.SIGNATURE_INVALID,
                "the signature did not verify under the resolved anchor's public key",
            )

        # === every gate succeeded — and only now does an artifact exist ==================
        artifact = _mint_verified_artifact(
            candidate=candidate,
            attestation=attestation,
            anchor=anchor,
            coordinate_digest=anchor_coordinate_digest(coordinate),
            verified_as_of=instant,
        )
        return ProducerAuthenticityResult(verified_attestation=artifact)

    def __repr__(self) -> str:
        return (
            "ProducerAttestationVerifier(resolver="
            f"{type(self._resolver).__name__}, verifier="
            f"{type(self._signature_verifier).__name__}, "
            f"production_mode={self._production_mode})"
        )


def _refuse(outcome: _Outcome, detail: str) -> ProducerAuthenticityResult:
    """Every refusal path in this module goes through here. No path returns success."""

    return ProducerAuthenticityResult(
        refusal=ProducerAttestationRefusal(outcome=outcome, detail=detail)
    )


def _mint_verified_artifact(
    *,
    candidate: CapacityAuthorizationCandidate,
    attestation: ProducerAttestationV2,
    anchor: TrustAnchorRecord,
    coordinate_digest: str,
    verified_as_of: datetime,
) -> VerifiedProducerAttestation:
    """Assemble the verified artifact. Reached only after every gate above has succeeded."""

    payload = {
        "candidate_digest": candidate.candidate_digest,
        "recommendation_id": candidate.recommendation_id,
        "recommendation_digest": candidate.recommendation_digest,
        "tenant_id": candidate.tenant_id,
        "subject_id": candidate.subject_id,
        "subject_type": candidate.subject_type,
        "attestation_digest": attestation.digest(),
        "verified_producer_id": attestation.producer_id,
        "verified_issuer": attestation.issuer,
        "verified_key_id": attestation.producer_key_id,
        "trust_anchor_coordinate_digest": coordinate_digest,
        "trust_anchor_record_digest": anchor_record_digest(anchor),
        "trust_anchor_capability": anchor.capability.value,
        "signature_profile": attestation.signature_profile,
        "signature_encoding": attestation.signature_encoding,
        "attestation_issued_at_fact": attestation.issued_at,
        "verified_as_of_fact": verified_as_of,
        "anchor_effective_from_fact": anchor.effective_from,
        "anchor_effective_to_fact": anchor.effective_to,
        "verification_profile": VERIFICATION_PROFILE,
        "verification_profile_version": VERIFICATION_PROFILE_VERSION,
        "outcome": _Outcome.VERIFIED.value,
        "grants_authority": False,
    }
    return VerifiedProducerAttestation(
        **{k: v for k, v in payload.items() if k not in ("outcome", "grants_authority")},
        artifact_digest=canonical_digest(payload),
        construction_token=_VERIFICATION_TOKEN,
    )
