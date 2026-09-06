"""The verification seam: one port, one pure result, one verifier.

The verifier answers exactly one question — *did the party the signed result
names, under the role it names, sign these exact bytes with a key the Trusted
Evidence Authority's anchors currently trust for that role?* — and returns
the answer as a typed value. It never raises for an invalid input, because a
raised exception tempts a caller to treat a swallowed one as a pass.

What a ``VERIFIED`` result establishes is **provenance and integrity**, and it
says so on its face. It carries no field that can be read as "the comparison
is correct": :attr:`ComparisonResultVerificationResult.factual_correctness_established`
is permanently ``False``, on a verified result as on a refused one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable

from ugence_reasoning_method_governance.api import ReadinessComparisonResult
from ugence_trusted_evidence_authority import (
    TrustAnchorRecord,
    TrustAnchorResolution,
    TrustedEvidenceRefusalReason,
    decode_signature,
)

from .attestation import (
    SignedComparisonResult,
    canonical_comparison_result,
    comparison_result_signing_bytes,
    comparison_result_signing_payload,
    recomputed_result_digest,
)
from .canonical import (
    canonical_digest,
    is_canonical_digest,
    require_aware_utc,
    require_canonical_identifier,
    require_exact_type,
)
from .errors import ComparisonResultAttestationConfigurationError as _ConfigError
from .errors import ComparisonResultAttestationContractError as _Error
from .identifiers import (
    COMPARISON_RESULT_ATTESTATION_ESTABLISHES,
    COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_ALGORITHM,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE,
    COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN,
)
from .outcomes import ComparisonResultRefusalReason as _Reason
from .outcomes import ComparisonResultVerificationOutcome as _Outcome
from .roles import (
    COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES,
    ComparisonResultAttesterRole,
    capability_for_role,
)
from .trust import (
    TRUST_ANCHOR_SET_REASONS,
    anchor_coordinate_digest,
    anchor_lifecycle_refusal,
    anchor_record_digest,
    anchor_verification_key,
    comparison_result_signer_coordinate,
    declares_production_posture,
    require_production_resolver,
    resolver_serves_production,
)

__all__ = [
    "ComparisonResultVerificationResult",
    "ComparisonResultVerifierPort",
    "Ed25519ComparisonResultVerifier",
    "verification_result_digest",
]

_GOVERNANCE_HEX = frozenset("0123456789abcdef")


def _is_governance_digest(value: object) -> bool:
    return type(value) is str and len(value) == 64 and set(value) <= _GOVERNANCE_HEX


@dataclass(frozen=True)
class ComparisonResultVerificationResult:
    """The pure, evidence-bound answer to one verification at one instant.

    Binds what was asked (role, engine identity, the governance ``result_digest``
    of the caller's own result), what was claimed (signer identity and key,
    payload digest), what was consulted (the exact coordinate and, when one
    resolved, the anchor revision), when, and the outcome with its one typed
    reason. Nothing here is an authorization, an admission, a fitness verdict or
    a statement that the comparison is correct.
    """

    outcome: _Outcome
    refusal_reason: Optional[_Reason]
    signer_role: ComparisonResultAttesterRole
    signer_identity: str
    signer_key_id: str
    engine_identity: str
    #: The governance contract's bare-hex ``result_digest`` of the caller's own
    #: result — the value an admission cites, carried verbatim.
    result_digest: str
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
        require_exact_type("signer_role", self.signer_role, ComparisonResultAttesterRole)
        require_canonical_identifier("signer_identity", self.signer_identity)
        require_canonical_identifier("signer_key_id", self.signer_key_id)
        require_canonical_identifier("engine_identity", self.engine_identity)
        if not _is_governance_digest(self.result_digest):
            raise _Error("result_digest must be the governance contract's bare 64-hex digest")
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

        return COMPARISON_RESULT_ATTESTATION_ESTABLISHES

    @property
    def role_establishes(self) -> str:
        """What this role's verified signature does and does not prove (SCR-1)."""

        return COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES[self.signer_role]

    @property
    def factual_correctness_established(self) -> bool:
        """Permanently ``False``. A verified signature proves who signed what;
        it never proves the comparison is correct (ADR §3, "role and capability")."""

        return False


def verification_result_digest(result: ComparisonResultVerificationResult) -> str:
    """This package's ``sha256:`` digest of one complete verification result — the
    citation a composition root hands the advisor as the verification receipt.

    Recomputed from the record every time; never stored on it. An auditor who holds
    the record recomputes the same value with plain JSON and SHA-256.
    """

    require_exact_type("result", result, ComparisonResultVerificationResult)
    return canonical_digest(result)


@runtime_checkable
class ComparisonResultVerifierPort(Protocol):
    """The seam a composition root injects. Implemented here by exactly one class."""

    def verify(
        self,
        *,
        signed_result: Optional[SignedComparisonResult],
        expected_role: ComparisonResultAttesterRole,
        expected_engine_identity: str,
        expected_result: ReadinessComparisonResult,
        as_of: datetime,
        expected_anchor_record_digest: Optional[str] = None,
    ) -> ComparisonResultVerificationResult:
        ...


class Ed25519ComparisonResultVerifier:
    """The one verifier. Resolves through an injected TEA resolver; verifies
    through TEA's strictly validated verification key.

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
        raise AttributeError(f"Ed25519ComparisonResultVerifier is immutable; cannot set {name!r}")

    def __delattr__(self, name: str) -> None:
        raise AttributeError(f"Ed25519ComparisonResultVerifier is immutable; cannot delete {name!r}")

    @property
    def production_mode(self) -> bool:
        return self._production_mode

    # ------------------------------------------------------------------ seam
    def verify(
        self,
        *,
        signed_result: Optional[SignedComparisonResult],
        expected_role: ComparisonResultAttesterRole,
        expected_engine_identity: str,
        expected_result: ReadinessComparisonResult,
        as_of: datetime,
        expected_anchor_record_digest: Optional[str] = None,
    ) -> ComparisonResultVerificationResult:
        """Verify one signed result against the caller's own facts at ``as_of``.

        The caller's ``expected_role``, ``expected_engine_identity`` and
        ``expected_result`` are the ground truth every claim in the signed
        result is reconciled against; the signed result supplies only the claim
        about **who signed**, which the anchor resolution then tests. Returns a
        typed result and never raises for an invalid input.
        """

        # The result must be able to name what was asked even when the signed
        # result is absent or malformed, so the caller's own facts are admitted
        # first, and a caller-side contract violation raises: it is a
        # programming error, not external trust state.
        role = require_exact_type("expected_role", expected_role, ComparisonResultAttesterRole)
        engine = require_canonical_identifier("expected_engine_identity", expected_engine_identity)
        require_exact_type("expected_result", expected_result, ReadinessComparisonResult)
        instant = require_aware_utc("as_of", as_of)
        expected_digest = recomputed_result_digest(expected_result)
        if expected_anchor_record_digest is not None and not is_canonical_digest(
            expected_anchor_record_digest
        ):
            raise _Error("expected_anchor_record_digest must be a canonical digest or None")

        claimed_identity = "unattested"
        claimed_key = "unattested"
        coordinate_digest = canonical_digest({"unresolved": True})
        if type(signed_result) is SignedComparisonResult:
            claimed_identity = signed_result.signer_identity
            claimed_key = signed_result.signer_key_id
            coordinate_digest = anchor_coordinate_digest(
                comparison_result_signer_coordinate(
                    role=role, signer_identity=claimed_identity, signer_key_id=claimed_key
                )
            )

        def refuse(reason: _Reason, detail: str, *, payload_digest=None, anchor_digest=None):
            return ComparisonResultVerificationResult(
                outcome=_Outcome.REFUSED,
                refusal_reason=reason,
                signer_role=role,
                signer_identity=claimed_identity,
                signer_key_id=claimed_key,
                engine_identity=engine,
                result_digest=expected_digest,
                signing_payload_digest=payload_digest,
                anchor_coordinate_digest=coordinate_digest,
                anchor_record_digest=anchor_digest,
                evaluated_at=instant,
                detail=detail,
            )

        try:
            return self._verify(
                signed_result, role, engine, expected_result, instant,
                expected_anchor_record_digest, expected_digest, refuse,
            )
        except Exception as exc:  # noqa: BLE001 - the fail-closed terminal
            return refuse(
                _Reason.VERIFICATION_UNAVAILABLE,
                f"verification could not reach a determination: {type(exc).__name__}",
            )

    def _verify(self, signed_result, role, engine, expected_result, instant,
                expected_anchor_record_digest, expected_digest, refuse):
        # === 1. the signed result itself =============================================
        if signed_result is None:
            return refuse(_Reason.ATTESTATION_ABSENT, "no signed result was supplied; absence is a refusal")
        if type(signed_result) is not SignedComparisonResult:
            return refuse(_Reason.UNSUPPORTED_EXACT_TYPE, "signed_result must be exactly SignedComparisonResult")

        # === 2. contract admission ===================================================
        if signed_result.schema_version != COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION:
            return refuse(_Reason.UNSUPPORTED_SCHEMA_VERSION, "unsupported schema version")
        if signed_result.signing_domain != COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN:
            return refuse(_Reason.UNSUPPORTED_SIGNING_DOMAIN, "unsupported signing domain")
        if signed_result.signature_algorithm != COMPARISON_RESULT_ATTESTATION_SIGNATURE_ALGORITHM:
            return refuse(_Reason.UNSUPPORTED_ALGORITHM, "unsupported signature algorithm")
        if signed_result.signature_profile != COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE:
            return refuse(_Reason.UNSUPPORTED_PROFILE, "unsupported signature profile")
        if signed_result.signature_encoding != COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING:
            return refuse(_Reason.UNSUPPORTED_ENCODING, "unsupported signature encoding")

        # === 3. reconciliation against the caller's own facts ========================
        if signed_result.signer_role is not role:
            return refuse(_Reason.ROLE_MISMATCH,
                          "the result was signed under a different role than the one expected")
        if signed_result.signer_identity != engine:
            return refuse(_Reason.WRONG_ENGINE_IDENTITY,
                          "the signed result names a different engine than the one expected")
        try:
            wrapped = canonical_comparison_result(signed_result.result)
        except _Error as exc:
            # The wrapped object no longer projects — most plainly, a field forced
            # open after signing so its self-digest no longer describes it. It is
            # not the result the caller holds, and it is not any result at all.
            return refuse(_Reason.RESULT_MISMATCH,
                          f"the wrapped result no longer projects to a valid comparison result: {exc}")
        if wrapped != canonical_comparison_result(expected_result):
            return refuse(_Reason.RESULT_MISMATCH,
                          "the wrapped result is not the comparison result the caller holds")

        # === 4. anchor resolution at the exact coordinate ============================
        coordinate = comparison_result_signer_coordinate(
            role=role,
            signer_identity=signed_result.signer_identity,
            signer_key_id=signed_result.signer_key_id,
        )
        # TW-3: a resolver that declared the production contract but cannot serve
        # right now — a snapshot that failed to load, most plainly — is refused
        # here, **before it is consulted**, so admitting it at composition can
        # never yield an anchor. A resolver that declares no posture at all is the
        # ratified deny-all, which is admitted by exact type and left alone.
        if (
            self._production_mode
            and declares_production_posture(self._resolver)
            and not resolver_serves_production(self._resolver)
        ):
            return refuse(_Reason.ANCHOR_SET_UNAVAILABLE,
                          "the resolver declares it cannot serve production trust state; "
                          "no anchor is consulted while its posture is not True")
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
            # TW-1: the trust-anchor **set** refusals keep their identity, so an
            # operator can tell "publish a newer snapshot" from "the trust state
            # cannot be consulted" from "the resolver misbehaved" (D-28).
            set_reason = TRUST_ANCHOR_SET_REASONS.get(resolution.refusal_reason)
            if set_reason is not None:
                return refuse(set_reason,
                              f"the trust-anchor set refused: {resolution.refusal_reason.value}")
            # TW-2: everything else, TRUST_ANCHOR_SET_INSTANT_REQUIRED included, is a
            # resolver that answered something this package never asks for, given that
            # it always hands over a validated aware instant.
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
        payload = comparison_result_signing_payload(
            result=expected_result,
            signer_role=role,
            signer_identity=signed_result.signer_identity,
            signer_key_id=signed_result.signer_key_id,
            signed_at=signed_result.signed_at,
            schema_version=signed_result.schema_version,
            signing_domain=signed_result.signing_domain,
            signature_algorithm=signed_result.signature_algorithm,
            signature_profile=signed_result.signature_profile,
            signature_encoding=signed_result.signature_encoding,
        )
        recomputed = comparison_result_signing_bytes(payload)
        payload_digest = canonical_digest(payload)
        if recomputed != signed_result.signed_bytes():
            return refuse(_Reason.PAYLOAD_MISMATCH,
                          "the independently recomputed signing payload is not byte-identical "
                          "to the one the signed result claims was signed",
                          payload_digest=payload_digest, anchor_digest=revision)
        try:
            signature = decode_signature(signed_result.signature, "signature")
        except Exception as exc:  # noqa: BLE001
            return refuse(_Reason.MALFORMED_SIGNATURE,
                          f"the signature could not be decoded: {type(exc).__name__}",
                          payload_digest=payload_digest, anchor_digest=revision)
        if key.verify(recomputed, signature) is not True:
            return refuse(_Reason.SIGNATURE_INVALID,
                          "the signature did not verify under the resolved anchor",
                          payload_digest=payload_digest, anchor_digest=revision)

        return ComparisonResultVerificationResult(
            outcome=_Outcome.VERIFIED,
            refusal_reason=None,
            signer_role=role,
            signer_identity=signed_result.signer_identity,
            signer_key_id=signed_result.signer_key_id,
            engine_identity=engine,
            result_digest=expected_digest,
            signing_payload_digest=payload_digest,
            anchor_coordinate_digest=anchor_coordinate_digest(coordinate),
            anchor_record_digest=revision,
            evaluated_at=instant,
            detail=COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES[role],
        )

    def __repr__(self) -> str:
        return (
            f"Ed25519ComparisonResultVerifier(resolver={type(self._resolver).__name__}, "
            f"production_mode={self._production_mode})"
        )
