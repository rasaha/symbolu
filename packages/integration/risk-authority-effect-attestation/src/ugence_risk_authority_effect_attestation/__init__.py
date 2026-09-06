"""Ugence Risk Authority Effect Attestation — signed external-effect verification, contracts first.

The wave 5 successor to RA-8's non-cryptographic effect-source trust, scoped by
``docs/architecture/ADR_UGENCE_SIGNED_EFFECT_ATTESTATION_SCOPING.md`` (SE-1 to
SE-5). This package owns **effect-attestation contracts and verification only**.

What it does
------------
* wraps one complete ``ExecutionObservation`` in an immutable, signed
  :class:`EffectAttestation` (SE-3) — never altering the observation;
* distinguishes an **executing provider** from an **independent observer** by
  role, each resolved under its own Trusted Evidence Authority capability
  (SE-2, SE-4);
* verifies an attestation against the caller's own observation, tenant and
  role, at the caller's instant, through TEA's strictly validated Ed25519
  verification key — the D-41 pair with the libsodium point check (SE-5);
* returns a pure, evidence-bound :class:`EffectAttestationVerificationResult`
  whose ``VERIFIED`` outcome establishes **provenance and integrity only**.

What it does not do
-------------------
It does not produce, fetch, reconcile or admit an observation; it does not
integrate with RA-8 (a later, separately validated step); it is not the
Third-Party Gateway, which remains FUTURE; it ships no production signer, no
key loading, key generation, network, filesystem, environment-variable,
credential or discovery code; and it holds no trust store of its own. Provider
self-attestation is not independent effect verification, and no verified result
here says an effect is true.

Maturity: **REFERENCE-GRADE / NOT PRODUCTION-READY.** The reference signer and
the reference resolver are refused in production; RA-8's production posture is
unchanged.
"""

from __future__ import annotations

from .attestation import (
    EFFECT_ATTESTATION_SIGNED_FIELDS,
    EffectAttestation,
    canonical_observation,
    effect_attestation_signing_bytes,
    effect_attestation_signing_payload,
    observation_digest,
)
from .canonical import canonical_bytes, canonical_digest
from .errors import (
    EffectAttestationConfigurationError,
    EffectAttestationContractError,
    EffectAttestationError,
    EffectAttestationSigningBoundaryError,
)
from .identifiers import (
    EFFECT_ATTESTATION_ESTABLISHES,
    EFFECT_ATTESTATION_SCHEMA_VERSION,
    EFFECT_ATTESTATION_SIGNATURE_ALGORITHM,
    EFFECT_ATTESTATION_SIGNATURE_ENCODING,
    EFFECT_ATTESTATION_SIGNATURE_PROFILE,
    EFFECT_ATTESTATION_SIGNING_DOMAIN,
)
from .outcomes import EffectAttestationRefusalReason, EffectAttestationVerificationOutcome
from .roles import (
    EFFECT_ATTESTER_ROLE_CAPABILITY,
    EFFECT_ATTESTER_ROLE_ESTABLISHES,
    EffectAttesterRole,
    capability_for_role,
)
from .signing import (
    EffectAttestationSignerPort,
    ReferenceEd25519EffectAttestationSigner,
    mint_effect_attestation,
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
    anchor_lifecycle_refusal,
    TRUST_ANCHOR_SET_REASONS,
    anchor_record_digest,
    anchor_verification_key,
    declares_production_posture,
    effect_attester_coordinate,
    require_production_resolver,
    resolver_serves_production,
)
from .verification import (
    Ed25519EffectAttestationVerifier,
    EffectAttestationVerificationResult,
    EffectAttestationVerifierPort,
)
from .version import __version__

#: Stated once, machine-readable, asserted by the suite and shipped in the wheel.
MATURITY = "REFERENCE_GRADE_NOT_PRODUCTION_READY"

__all__ = [
    "__version__",
    "MATURITY",
    # the wrapper and its canonical projection
    "EffectAttestation",
    "canonical_observation",
    "observation_digest",
    "effect_attestation_signing_payload",
    "effect_attestation_signing_bytes",
    "EFFECT_ATTESTATION_SIGNED_FIELDS",
    "canonical_bytes",
    "canonical_digest",
    # roles
    "EffectAttesterRole",
    "EFFECT_ATTESTER_ROLE_CAPABILITY",
    "EFFECT_ATTESTER_ROLE_ESTABLISHES",
    "capability_for_role",
    # identifiers
    "EFFECT_ATTESTATION_SCHEMA_VERSION",
    "EFFECT_ATTESTATION_SIGNING_DOMAIN",
    "EFFECT_ATTESTATION_SIGNATURE_ALGORITHM",
    "EFFECT_ATTESTATION_SIGNATURE_PROFILE",
    "EFFECT_ATTESTATION_SIGNATURE_ENCODING",
    "EFFECT_ATTESTATION_ESTABLISHES",
    # verification
    "EffectAttestationVerificationOutcome",
    "EffectAttestationRefusalReason",
    "EffectAttestationVerificationResult",
    "EffectAttestationVerifierPort",
    "Ed25519EffectAttestationVerifier",
    # trust anchors — TEA's, re-exported unchanged
    "TrustAnchorCoordinate",
    "TrustAnchorRecord",
    "TrustAnchorCapability",
    "TrustAnchorResolution",
    "TrustAnchorResolverPort",
    "KeyRevocation",
    "StaticTrustAnchorDirectory",
    "DenyAllTrustAnchorDirectory",
    "REFERENCE_GRADE_RESOLVERS",
    "effect_attester_coordinate",
    "anchor_coordinate_digest",
    "anchor_record_digest",
    "anchor_lifecycle_refusal",
    "anchor_verification_key",
    "require_production_resolver",
    "TRUST_ANCHOR_SET_REASONS",
    "resolver_serves_production",
    "declares_production_posture",
    # signing (reference only)
    "EffectAttestationSignerPort",
    "ReferenceEd25519EffectAttestationSigner",
    "mint_effect_attestation",
    # errors
    "EffectAttestationError",
    "EffectAttestationContractError",
    "EffectAttestationSigningBoundaryError",
    "EffectAttestationConfigurationError",
]
