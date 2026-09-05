"""Ugence Cloud Scaling Envelope Issuance — Phase 5B-4.

**An envelope is authority, not execution.** This package composes what the Cloud Scaling
ladder already verified into one call on Risk Authority's Phase 5 envelope issuance seam:

* the Phase 5A ``CapacityAuthorizationCandidate`` — reconciled, digest-bound, granting
  nothing;
* the Phase 5B-0A ``ProducerAttestationVerifier`` — *who produced the recommendation*;
* the Phase 5B-0B ``PolicyAuthenticityVerifier`` — *were these limits authentically issued
  and in force at this instant*;
* Risk Authority's ``EnvelopeIssuanceSeam`` — the only place a Phase 5 envelope is signed.

The seam reads the authoritative clock once; this package runs both verifiers at that
instant, revalidates every verified artifact at the consumption boundary, and projects five
bindings onto the seam's one admitted word, ``VERIFIED``: the candidate digest, the
policy-authenticity artifact digest, the producer-attestation verification digest, the
execution target scope digest and the D-6 idempotency key. The seam signs them into
``EnvelopeBindings.artifact_bindings``, caps expiry by the decision, and persists the
envelope in the application that evaluated the decision (ADR D-1 … D-5).

What it does **not** do, and contains no capability to do: read a clock; accept a
caller-supplied instant, decision, scope, binding or signer; hold a signing key; mint a
nonce or keep a replay ledger; call ``authorize_action`` or the case-based
``issue_envelope``; admit an action through ActionGate (5C); broker a credential (5X); call
a cloud provider; or learn from an outcome. An issued envelope reports ``executable`` as a
permanently-``False`` property.
"""

from __future__ import annotations

from .composition import (
    CloudScalingEnvelopeIssuance,
    CloudScalingEnvelopeIssuanceOutcome,
    CloudScalingEnvelopeIssuanceRequest,
)
from .errors import (
    CloudScalingEnvelopeIssuanceError,
    EnvelopeIssuanceConfigurationError,
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
    COMPOSITION_PROFILE,
    COMPOSITION_PROFILE_VERSION,
    REQUIRED_BINDING_KINDS,
)
from .outcomes import (
    REFUSING_STATUSES,
    ArtifactBindingStatus,
    CloudScalingVerificationReport,
)
from .verification import (
    CloudScalingArtifactVerification,
    bare_digest,
    policy_coordinate_of,
)
from .version import __version__

__all__ = [
    "__version__",
    # --- the composition root and its request/outcome ---
    "CloudScalingEnvelopeIssuance",
    "CloudScalingEnvelopeIssuanceRequest",
    "CloudScalingEnvelopeIssuanceOutcome",
    # --- the verification port the seam calls ---
    "CloudScalingArtifactVerification",
    "CloudScalingVerificationReport",
    "ArtifactBindingStatus",
    "REFUSING_STATUSES",
    "bare_digest",
    "policy_coordinate_of",
    # --- ratified binding kinds (ADR D-2) ---
    "BINDING_KIND_AUTHORIZATION_CANDIDATE",
    "BINDING_KIND_POLICY_AUTHENTICITY",
    "BINDING_KIND_PRODUCER_ATTESTATION",
    "BINDING_KIND_TARGET_SCOPE",
    "BINDING_KIND_IDEMPOTENCY_KEY",
    "REQUIRED_BINDING_KINDS",
    "COMPOSITION_PROFILE",
    "COMPOSITION_PROFILE_VERSION",
    # --- typed errors ---
    "CloudScalingEnvelopeIssuanceError",
    "EnvelopeIssuanceConfigurationError",
    "EnvelopeIssuanceContractError",
    "EnvelopeIssuanceExactTypeError",
    "UpstreamVerifierUnavailableError",
]
