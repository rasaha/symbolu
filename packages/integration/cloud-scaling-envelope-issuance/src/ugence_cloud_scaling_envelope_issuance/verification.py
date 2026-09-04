"""The ``ArtifactVerificationPort`` for cloud scaling: five bindings, one instant.

Risk Authority's issuance seam reads its clock once and calls this port with that instant
as ``as_of``. The port runs the two authenticity verifiers the ladder already has — 5B-0A
producer attestation and 5B-0B policy authenticity — at exactly that instant, revalidates
each verified artifact at this consumption boundary, checks that it names *this* candidate
and recorded *this* instant, and projects the results onto the seam's one admitted word.
It then adds the three bindings the candidate itself carries: its own digest, its execution
target scope, and the D-6 idempotency key, each re-derived before it is reported.

**No clock.** ``as_of`` is the seam's; nothing here reads or generates an instant.

**No authority.** The port reports; the seam decides. A report of five ``VERIFIED``
bindings is an input to issuance, not an issuance, and the seam still refuses a decision
that has drifted, expired or grants nothing.

**Exact types.** The candidate, the attestation and both verifiers are admitted by exact
type at construction, so a subclass with a diverting property never reaches a verifier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from risk_authority.api import VERIFIED, VerifiedArtifactBinding
from ugence_cloud_scaling_authorization_contracts import (
    CapacityAuthorizationCandidate,
    DIGEST_PREFIX,
    canonical_digest,
    is_canonical_digest,
)
from ugence_cloud_scaling_policy_authenticity import (
    PolicyAuthenticityVerifier,
    VerifiedPolicyArtifactIntegrityError,
    is_policy_digest,
    require_verified_policy_authenticity,
)
from ugence_cloud_scaling_producer_attestation import (
    ProducerAttestationV2,
    ProducerAttestationVerifier,
    VerifiedArtifactIntegrityError,
    require_verified_producer_attestation,
)
from ugence_policy_authority.api import PolicyCoordinate

from .errors import (
    EnvelopeIssuanceContractError,
    EnvelopeIssuanceExactTypeError,
    UpstreamVerifierUnavailableError,
)
from .identifiers import (
    BINDING_KIND_AUTHORIZATION_CANDIDATE,
    BINDING_KIND_IDEMPOTENCY_KEY,
    BINDING_KIND_POLICY_AUTHENTICITY,
    BINDING_KIND_PRODUCER_ATTESTATION,
    BINDING_KIND_TARGET_SCOPE,
    REQUIRED_BINDING_KINDS,
)
from .outcomes import ArtifactBindingStatus, CloudScalingVerificationReport

__all__ = [
    "CloudScalingArtifactVerification",
    "bare_digest",
    "policy_coordinate_of",
]

_S = ArtifactBindingStatus


def bare_digest(value: str) -> str:
    """Project a ladder digest onto the seam's bare 64-hex form.

    Phase 5A and 5B-0A write ``sha256:``-prefixed digests; 5B-0B writes bare framed digests.
    ``ArtifactBinding`` takes bare hex, so the prefix is dropped here and nowhere else — the
    kind names which namespace a binding came from.
    """

    if is_canonical_digest(value):
        return value[len(DIGEST_PREFIX):]
    if is_policy_digest(value):
        return value
    raise EnvelopeIssuanceContractError(f"not a ladder digest: {value!r}")


def policy_coordinate_of(candidate: CapacityAuthorizationCandidate) -> PolicyCoordinate:
    """The exact coordinate the candidate names, and nothing the caller chose.

    5B-1 put all six components inside the candidate's ``policy_coordinate_binding``; the
    verifier resolves *that* coordinate and gate 11 reconciles the candidate against what
    resolved. A caller therefore cannot point the verifier at a different policy than the
    one the candidate was bound to.
    """

    binding = candidate.policy_coordinate_binding
    return PolicyCoordinate(
        policy_family=binding.policy_family,
        policy_id=binding.policy_id,
        version=binding.policy_version,
        content_digest=binding.policy_content_digest,
        scope=binding.policy_scope,
        tenant_id=binding.policy_tenant_id,
    )


def _is_aware(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
    )


@dataclass
class CloudScalingArtifactVerification:
    """One act's verification port. Built per candidate; reports once per ``verify``.

    Satisfies ``risk_authority.api.ArtifactVerificationPort``: ``is_production_authoritative``
    is true only when *both* upstream verifiers were built in production mode, and
    ``verify(as_of=...)`` returns exactly the five required bindings, in the ratified order.
    The last report is kept on :attr:`report` so the composition root can return it beside
    the seam's outcome.
    """

    candidate: CapacityAuthorizationCandidate
    attestation: ProducerAttestationV2
    producer_verifier: ProducerAttestationVerifier
    policy_verifier: PolicyAuthenticityVerifier
    report: Optional[CloudScalingVerificationReport] = field(default=None, init=False)

    def __post_init__(self) -> None:
        _exact(self.candidate, CapacityAuthorizationCandidate, "candidate")
        _exact(self.attestation, ProducerAttestationV2, "producer_attestation")
        _exact(self.producer_verifier, ProducerAttestationVerifier, "producer_verifier")
        _exact(self.policy_verifier, PolicyAuthenticityVerifier, "policy_verifier")

    @property
    def is_production_authoritative(self) -> bool:
        return bool(self.producer_verifier.production_mode) and bool(
            self.policy_verifier.production_mode
        )

    # ------------------------------------------------------------------ the act
    def verify(self, *, as_of: datetime) -> tuple[VerifiedArtifactBinding, ...]:
        if not _is_aware(as_of):
            raise EnvelopeIssuanceContractError(
                "verify(as_of) requires a timezone-aware datetime; the seam supplies it"
            )
        candidate = self.candidate

        # 1. The candidate, re-derived. Its own type re-derives ``candidate_digest`` at
        #    construction; this boundary asks again, because the instance crossed it.
        candidate_status = _S.VERIFIED
        detail = ""
        try:
            rederived = canonical_digest(candidate.digest_payload())
            if (
                rederived != candidate.candidate_digest
                or candidate.target_scope.digest() != candidate.target_scope_digest
                or not is_canonical_digest(candidate.idempotency_key)
            ):
                candidate_status = _S.CANDIDATE_NOT_REDERIVED
                detail = "candidate digests do not re-derive"
        except Exception as exc:  # noqa: BLE001 — a candidate that cannot be read is refused
            candidate_status = _S.CANDIDATE_NOT_REDERIVED
            detail = f"candidate re-derivation raised {type(exc).__name__}"

        # 2. Producer authenticity at this instant (5B-0A).
        producer_outcome: Optional[str] = None
        producer_status, producer_digest = _S.VERIFIER_UNAVAILABLE, bare_digest(
            candidate.candidate_digest
        )
        try:
            result = self.producer_verifier.verify(
                candidate=candidate, attestation=self.attestation, as_of=as_of
            )
        except Exception as exc:  # noqa: BLE001
            self._record(as_of, (), None, None, f"producer verifier raised {type(exc).__name__}")
            raise UpstreamVerifierUnavailableError("producer attestation verifier raised") from exc
        producer_outcome = _token(result.outcome)
        artifact = result.verified_attestation
        if result.refusal is not None or artifact is None:
            producer_status = _S.PRODUCER_ATTESTATION_REFUSED
        else:
            try:
                require_verified_producer_attestation(artifact)
            except VerifiedArtifactIntegrityError:
                producer_status = _S.ARTIFACT_INTEGRITY_FAILED
            else:
                producer_digest = bare_digest(artifact.artifact_digest)
                if artifact.candidate_digest != candidate.candidate_digest:
                    producer_status = _S.ARTIFACT_NOT_BOUND_TO_CANDIDATE
                elif artifact.verified_as_of_fact != as_of:
                    producer_status = _S.ARTIFACT_INSTANT_MISMATCH
                else:
                    producer_status = _S.VERIFIED

        # 3. Policy authenticity at this instant (5B-0B), for the coordinate the candidate names.
        policy_outcome: Optional[str] = None
        policy_status = _S.VERIFIER_UNAVAILABLE
        policy_digest = candidate.policy_coordinate_binding.policy_body_digest
        try:
            coordinate = policy_coordinate_of(candidate)
            presult = self.policy_verifier.verify(
                coordinate=coordinate,
                expected_reference_tenant_id=coordinate.tenant_id,
                as_of=as_of,
                candidate=candidate,
            )
        except Exception as exc:  # noqa: BLE001
            self._record(
                as_of, (), producer_outcome, None, f"policy verifier raised {type(exc).__name__}"
            )
            raise UpstreamVerifierUnavailableError("policy authenticity verifier raised") from exc
        policy_outcome = _token(presult.outcome)
        proof = presult.verified_policy
        if presult.refusal is not None or proof is None:
            policy_status = _S.POLICY_AUTHENTICITY_REFUSED
        else:
            try:
                require_verified_policy_authenticity(proof)
            except VerifiedPolicyArtifactIntegrityError:
                policy_status = _S.ARTIFACT_INTEGRITY_FAILED
            else:
                policy_digest = proof.artifact_digest
                if proof.candidate_digest_fact != candidate.candidate_digest:
                    policy_status = _S.ARTIFACT_NOT_BOUND_TO_CANDIDATE
                elif proof.resolved_as_of_fact != as_of:
                    policy_status = _S.ARTIFACT_INSTANT_MISMATCH
                else:
                    policy_status = _S.VERIFIED

        # 4. The five bindings, in the ratified order, all resolved at the seam's instant.
        bindings = (
            _binding(BINDING_KIND_AUTHORIZATION_CANDIDATE, candidate.candidate_digest,
                     candidate_status, as_of),
            _binding(BINDING_KIND_POLICY_AUTHENTICITY, policy_digest, policy_status, as_of),
            _binding(BINDING_KIND_PRODUCER_ATTESTATION, producer_digest, producer_status, as_of),
            _binding(BINDING_KIND_TARGET_SCOPE, candidate.target_scope_digest,
                     candidate_status, as_of),
            _binding(BINDING_KIND_IDEMPOTENCY_KEY, candidate.idempotency_key,
                     candidate_status, as_of),
        )
        if tuple(b.kind for b in bindings) != REQUIRED_BINDING_KINDS:  # pragma: no cover
            raise EnvelopeIssuanceContractError("binding order drifted from REQUIRED_BINDING_KINDS")
        if not detail:
            refused = [f"{b.kind}={b.outcome}" for b in bindings if b.outcome != VERIFIED]
            detail = "; ".join(refused)
        self._record(as_of, bindings, producer_outcome, policy_outcome, detail)
        return bindings

    def _record(self, as_of, bindings, producer_outcome, policy_outcome, detail) -> None:
        self.report = CloudScalingVerificationReport(
            as_of=as_of,
            bindings=tuple(bindings),
            producer_outcome=producer_outcome,
            policy_outcome=policy_outcome,
            detail=detail,
        )


def _binding(kind: str, digest: str, status: ArtifactBindingStatus, as_of: datetime
             ) -> VerifiedArtifactBinding:
    return VerifiedArtifactBinding(
        kind=kind, digest=bare_digest(digest), outcome=status.value, resolved_as_of=as_of
    )


def _token(outcome: object) -> str:
    return str(getattr(outcome, "value", outcome))


def _exact(value: object, expected: type, name: str) -> None:
    if type(value) is not expected:
        raise EnvelopeIssuanceExactTypeError(
            f"{name} must be exactly {expected.__name__} (got {type(value).__name__}); "
            "a subclass or look-alike is refused, not adapted"
        )
