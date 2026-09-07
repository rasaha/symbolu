"""Ugence Reasoning-Method Result Attestation — signed comparison results, contracts first.

Scoped by ``docs/architecture/ADR_UGENCE_SIGNED_COMPARISON_RESULT_SCOPING.md``
(SCR-1). This package owns **the signed-comparison-result contract and its
verification only**; it closes requirement A3 of the first-admission study plan
structurally, and nothing else.

What it does
------------
* wraps one complete, unmodified ``ReadinessComparisonResult`` in an immutable
  :class:`SignedComparisonResult`, signed under one role, ``COMPARISON_ENGINE``,
  by the engine the result names;
* resolves that role under one Trusted Evidence Authority capability lent for
  the purpose, ``COMPARISON_RESULT_ATTESTATION``;
* verifies a signed result against the caller's own result, engine identity and
  role, at the caller's instant, through TEA's strictly validated Ed25519
  verification key;
* returns a pure, evidence-bound :class:`ComparisonResultVerificationResult`
  whose ``VERIFIED`` outcome establishes **provenance and integrity only**.

What it does not do
-------------------
It does not run a comparison, admit an advisory, or judge any method fit for
any task; it imports neither the comparison engine nor the advisor; it ships no
production signer, no key loading, key generation, network, filesystem,
environment-variable, credential or discovery code; and it holds no trust store
of its own. A verified signature never says the comparison is correct.

Maturity: **REFERENCE-GRADE / NOT PRODUCTION-READY.** The reference signer and
the reference resolver are refused in production, and no key for any comparison
engine exists anywhere in the repository (ADR §4).
"""

from __future__ import annotations

from .attestation import (
    COMPARISON_RESULT_PROJECTED_FIELDS,
    COMPARISON_RESULT_SIGNED_FIELDS,
    SignedComparisonResult,
    canonical_comparison_result,
    comparison_result_digest,
    comparison_result_signing_bytes,
    comparison_result_signing_payload,
    recomputed_result_digest,
)
from .canonical import canonical_bytes, canonical_digest
from .errors import (
    ComparisonResultAttestationConfigurationError,
    ComparisonResultAttestationContractError,
    ComparisonResultAttestationError,
    ComparisonResultAttestationSigningBoundaryError,
)
from .identifiers import (
    COMPARISON_RESULT_ATTESTATION_ESTABLISHES,
    COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_ALGORITHM,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING,
    COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE,
    COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN,
)
from .outcomes import ComparisonResultRefusalReason, ComparisonResultVerificationOutcome
from .roles import (
    COMPARISON_RESULT_ATTESTER_ROLE_CAPABILITY,
    COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES,
    ComparisonResultAttesterRole,
    capability_for_role,
)
from .signing import (
    ComparisonResultSignerPort,
    ReferenceEd25519ComparisonResultSigner,
    sign_comparison_result,
)
from .trust import (
    REFERENCE_GRADE_RESOLVERS,
    TRUST_ANCHOR_SET_REASONS,
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
    anchor_record_digest,
    anchor_verification_key,
    comparison_result_signer_coordinate,
    declares_production_posture,
    require_production_resolver,
    resolver_serves_production,
)
from .verification import (
    ComparisonResultVerificationResult,
    ComparisonResultVerifierPort,
    Ed25519ComparisonResultVerifier,
    verification_result_digest,
)
from .version import __version__

#: Stated once, machine-readable, asserted by the suite and shipped in the wheel.
MATURITY = "REFERENCE_GRADE_NOT_PRODUCTION_READY"

__all__ = [
    "__version__",
    "MATURITY",
    # the wrapper and its canonical projection
    "SignedComparisonResult",
    "canonical_comparison_result",
    "comparison_result_digest",
    "recomputed_result_digest",
    "comparison_result_signing_payload",
    "comparison_result_signing_bytes",
    "COMPARISON_RESULT_SIGNED_FIELDS",
    "COMPARISON_RESULT_PROJECTED_FIELDS",
    "canonical_bytes",
    "canonical_digest",
    # roles
    "ComparisonResultAttesterRole",
    "COMPARISON_RESULT_ATTESTER_ROLE_CAPABILITY",
    "COMPARISON_RESULT_ATTESTER_ROLE_ESTABLISHES",
    "capability_for_role",
    # identifiers
    "COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION",
    "COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN",
    "COMPARISON_RESULT_ATTESTATION_SIGNATURE_ALGORITHM",
    "COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE",
    "COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING",
    "COMPARISON_RESULT_ATTESTATION_ESTABLISHES",
    # verification
    "ComparisonResultVerificationOutcome",
    "ComparisonResultRefusalReason",
    "ComparisonResultVerificationResult",
    "ComparisonResultVerifierPort",
    "Ed25519ComparisonResultVerifier",
    "verification_result_digest",
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
    "comparison_result_signer_coordinate",
    "anchor_coordinate_digest",
    "anchor_record_digest",
    "anchor_lifecycle_refusal",
    "anchor_verification_key",
    "require_production_resolver",
    "TRUST_ANCHOR_SET_REASONS",
    "resolver_serves_production",
    "declares_production_posture",
    # signing (reference only)
    "ComparisonResultSignerPort",
    "ReferenceEd25519ComparisonResultSigner",
    "sign_comparison_result",
    # errors
    "ComparisonResultAttestationError",
    "ComparisonResultAttestationContractError",
    "ComparisonResultAttestationSigningBoundaryError",
    "ComparisonResultAttestationConfigurationError",
]
