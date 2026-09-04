"""Ratified identifiers: the binding kinds this composition root requires (ADR D-1, D-2).

Risk Authority names no domain's artifacts. The seam takes the kinds it must see from the
composition root, and this module is where cloud scaling declares them. Every kind is a
dotted, lowercase token so the envelope's ``artifact_bindings`` read as a namespace rather
than as five loose words.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "BINDING_KIND_AUTHORIZATION_CANDIDATE",
    "BINDING_KIND_POLICY_AUTHENTICITY",
    "BINDING_KIND_PRODUCER_ATTESTATION",
    "BINDING_KIND_TARGET_SCOPE",
    "BINDING_KIND_IDEMPOTENCY_KEY",
    "REQUIRED_BINDING_KINDS",
    "COMPOSITION_PROFILE",
    "COMPOSITION_PROFILE_VERSION",
]

#: The Phase 5A candidate: ``candidate_digest``, re-derived before it is bound.
BINDING_KIND_AUTHORIZATION_CANDIDATE: Final[str] = "cloud-scaling.authorization-candidate"
#: The 5B-0B verified policy proof: ``VerifiedPolicyAuthenticity.artifact_digest``.
BINDING_KIND_POLICY_AUTHENTICITY: Final[str] = "cloud-scaling.policy-authenticity"
#: The 5B-0A verified producer proof: ``VerifiedProducerAttestation.artifact_digest``.
BINDING_KIND_PRODUCER_ATTESTATION: Final[str] = "cloud-scaling.producer-attestation"
#: The account-bound execution target the candidate names: ``target_scope_digest``.
BINDING_KIND_TARGET_SCOPE: Final[str] = "cloud-scaling.execution-target-scope"
#: The D-6 idempotency key the candidate carries: one recommendation, one key, no timestamp.
BINDING_KIND_IDEMPOTENCY_KEY: Final[str] = "cloud-scaling.idempotency-key"

#: The five kinds an envelope must bind before it is signed (ADR D-2). Passed verbatim to
#: the seam as ``required_binding_kinds``; a report missing any one of them is refused there.
REQUIRED_BINDING_KINDS: Final[tuple[str, ...]] = (
    BINDING_KIND_AUTHORIZATION_CANDIDATE,
    BINDING_KIND_POLICY_AUTHENTICITY,
    BINDING_KIND_PRODUCER_ATTESTATION,
    BINDING_KIND_TARGET_SCOPE,
    BINDING_KIND_IDEMPOTENCY_KEY,
)

#: How the report was reached. Recorded on every report so an auditor can tell which
#: projection produced a binding set.
COMPOSITION_PROFILE: Final[str] = "ugence.cloud-scaling.envelope-issuance"
COMPOSITION_PROFILE_VERSION: Final[str] = "v1"
