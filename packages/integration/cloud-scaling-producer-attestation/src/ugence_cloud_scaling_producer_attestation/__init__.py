"""Ugence Cloud Scaling Producer Attestation — Phase 5B-0A producer authenticity.

**A verified attestation grants nothing.** It establishes who produced a recommendation,
and stops. It is not an authorization, not an envelope, not an ActionGate admission, not a
credential and not permission to execute anything.

What this package closes
------------------------
Before it, the Cloud Scaling chain had a hole an auditor could drive a forged
recommendation through. A self-consistent forgery — invented capacity facts, its own
matching unkeyed digest — passes Phase 4C's structural admission, obtains a genuine Risk
Decision, and binds into a valid Phase 5A ``CapacityAuthorizationCandidate``, because
nothing in that chain establishes *who produced the recommendation*. Phase 5A carries a
producer attestation and says so plainly: it never checks the signature, and its one trust
state is ``PRESENT_BUT_NOT_TRUST_VERIFIED``.

Phase 5B-0A makes such an attestation mintable and verifiable for the first time:

* :class:`ProducerAttestationV2` — a new, separately tagged contract whose signed payload
  binds issuer, tenant, subject and subject type as well as the recommendation;
* :func:`mint_producer_attestation` — the one route to a producer signature, through a
  token-guarded signing input, at the Controller's output boundary and never inside it;
* :class:`ProducerAttestationVerifier` — the authoritative routine, which recomputes the
  signed payload from the candidate's own reconciled facts and refuses unless the bytes
  match, resolves the key through the Trusted Evidence Authority's existing trust-anchor
  store, and checks the signature under a strictly validated public key;
* :class:`VerifiedProducerAttestation` — the exact-typed, immutable, non-authoritative
  result, constructible only by that routine and revalidated at every consumption boundary.

What it deliberately does not do
--------------------------------
Phase 5A stays at **0.1.0, unmodified**: this package does not change its canonical
dictionaries, its candidate digest, or the documented limitation of its v1 attestation, and
it does not reinterpret that unverified field as verified. The v2 proof travels *alongside*
a candidate; binding one *inside* a candidate is Phase 5B-0B's work. It is bound to the
**recommendation** — by id and content digest — and **not** to the candidate: ``candidate_digest``
is not signature-covered. See :mod:`ugence_cloud_scaling_producer_attestation.verified` and
ADR §12.1 before reading a ``VERIFIED`` outcome as saying anything about the policy binding
or the execution scope the recommendation was later bound into. The Cloud Scaling Controller stays at 0.4.0, key-free and advisory.

**Policy authenticity remains unresolved.** Nothing here establishes that the policy binding
a candidate carries is genuine or in force. That blocker is Phase 5B-0B's and is open.

Not implemented here, and not reachable from here: Risk Decision reconstruction, Risk
Authority v3, scope repair, nonces and replay ledgers, audience, envelope requests, envelope
signing, containment lifting, ActionGate, credentials, execution, effect verification and
learning.
"""

from __future__ import annotations

from .attestation import ProducerAttestationV2, producer_attestation_signing_payload
from .canonical import (
    DIGEST_PREFIX,
    canonical_bytes,
    canonical_digest,
    is_canonical_digest,
)
from .errors import (
    CloudScalingProducerAttestationError,
    ProducerAttestationCanonicalFieldError,
    ProducerAttestationConfigurationError,
    ProducerAttestationContractError,
    ProducerAttestationExactTypeError,
    ProducerAttestationSigningBoundaryError,
    VerifiedArtifactIntegrityError,
)
from .identifiers import (
    KNOWN_POLICY_SIGNING_PURPOSES,
    PHASE_5A_V1_SCHEMA_VERSION,
    PRODUCER_ATTESTATION_CAPABILITY,
    PRODUCER_ATTESTATION_SIGNATURE_ALGORITHM,
    PRODUCER_ATTESTATION_SIGNATURE_ENCODING,
    PRODUCER_ATTESTATION_SIGNATURE_PROFILE,
    PRODUCER_ATTESTATION_V2_SCHEMA_VERSION,
    PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE,
    SUBJECT_TYPE_CAPACITY_SUBJECT,
    SUPPORTED_V2_SIGNATURE_ALGORITHMS,
    SUPPORTED_V2_SIGNING_PURPOSES,
    VERIFICATION_PROFILE,
    VERIFICATION_PROFILE_VERSION,
)
from .outcomes import (
    ANCHOR_LIFECYCLE_OUTCOMES,
    REFUSAL_OUTCOMES,
    ProducerAuthenticityOutcome,
)
from .signing import (
    REFERENCE_GRADE_SIGNERS,
    ProducerAttestationSignerPort,
    ProducerAttestationSigningInput,
    ReferenceEd25519ProducerAttestationSigner,
    mint_producer_attestation,
)
from .trust import (
    REFERENCE_GRADE_RESOLVERS,
    DenyAllTrustAnchorDirectory,
    KeyRevocation,
    StaticTrustAnchorDirectory,
    TrustAnchorCapability,
    TrustAnchorCoordinate,
    TrustAnchorRecord,
    TrustAnchorResolution,
    TrustAnchorResolverPort,
    anchor_coordinate_digest,
    anchor_lifecycle_outcome,
    anchor_record_digest,
    producer_anchor_coordinate,
    require_production_resolver,
)
from .verification import (
    Ed25519ProducerSignatureVerifier,
    ProducerAttestationRefusal,
    ProducerAttestationVerifier,
    ProducerAuthenticityResult,
    ProducerSignatureVerifierPort,
)
from .verified import (
    VerifiedProducerAttestation,
    require_verified_producer_attestation,
)
from .version import __version__

__all__ = [
    "__version__",
    # --- the attestation contract (new schema tag; Phase 5A v1 is untouched) ---
    "ProducerAttestationV2",
    "producer_attestation_signing_payload",
    "PRODUCER_ATTESTATION_V2_SCHEMA_VERSION",
    "PRODUCER_ATTESTATION_V2_SIGNING_PURPOSE",
    "SUPPORTED_V2_SIGNING_PURPOSES",
    "PRODUCER_ATTESTATION_SIGNATURE_ALGORITHM",
    "SUPPORTED_V2_SIGNATURE_ALGORITHMS",
    "PRODUCER_ATTESTATION_SIGNATURE_PROFILE",
    "PRODUCER_ATTESTATION_SIGNATURE_ENCODING",
    "PHASE_5A_V1_SCHEMA_VERSION",
    "KNOWN_POLICY_SIGNING_PURPOSES",
    "SUBJECT_TYPE_CAPACITY_SUBJECT",
    # --- the signer boundary (no signing oracle; reference signer is marked) ---
    "ProducerAttestationSignerPort",
    "ProducerAttestationSigningInput",
    "ReferenceEd25519ProducerAttestationSigner",
    "mint_producer_attestation",
    # --- trust resolution (TEV's store, reused; no second anchor store) ---
    "TrustAnchorCoordinate",
    "TrustAnchorRecord",
    "TrustAnchorCapability",
    "TrustAnchorResolution",
    "TrustAnchorResolverPort",
    "KeyRevocation",
    "StaticTrustAnchorDirectory",
    "DenyAllTrustAnchorDirectory",
    "PRODUCER_ATTESTATION_CAPABILITY",
    "producer_anchor_coordinate",
    "anchor_coordinate_digest",
    "anchor_record_digest",
    "anchor_lifecycle_outcome",
    "require_production_resolver",
    "REFERENCE_GRADE_RESOLVERS",
    "REFERENCE_GRADE_SIGNERS",
    # --- the authoritative verification routine ---
    "ProducerAttestationVerifier",
    "ProducerSignatureVerifierPort",
    "Ed25519ProducerSignatureVerifier",
    "ProducerAuthenticityResult",
    "ProducerAttestationRefusal",
    "VERIFICATION_PROFILE",
    "VERIFICATION_PROFILE_VERSION",
    # --- the verified artifact (non-authoritative; revalidated at consumption) ---
    "VerifiedProducerAttestation",
    "require_verified_producer_attestation",
    # --- typed outcomes ---
    "ProducerAuthenticityOutcome",
    "REFUSAL_OUTCOMES",
    "ANCHOR_LIFECYCLE_OUTCOMES",
    # --- canonicalization (Risk Authority's scheme, public API only) ---
    "canonical_digest",
    "canonical_bytes",
    "is_canonical_digest",
    "DIGEST_PREFIX",
    # --- typed errors ---
    "CloudScalingProducerAttestationError",
    "ProducerAttestationContractError",
    "ProducerAttestationExactTypeError",
    "ProducerAttestationCanonicalFieldError",
    "ProducerAttestationSigningBoundaryError",
    "VerifiedArtifactIntegrityError",
    "ProducerAttestationConfigurationError",
]
