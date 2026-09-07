"""The pinned identifiers of the signed-comparison-result contract.

Every one is bound into the signed payload, so a signature made under a
different schema, domain, algorithm, profile or encoding differs in bytes before
it differs in anything else. The profile and encoding are the Trusted Evidence
Authority's ratified Ed25519 ones, reused by value: an anchor record carries the
same two strings, and a verifier compares them exactly.
"""

from __future__ import annotations

from typing import Final

from ugence_trusted_evidence_authority import (
    TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1,
    TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1,
)

__all__ = [
    "COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION",
    "COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN",
    "COMPARISON_RESULT_ATTESTATION_SIGNATURE_ALGORITHM",
    "COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE",
    "COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING",
    "COMPARISON_RESULT_ATTESTATION_ESTABLISHES",
]

#: The contract the signed bytes belong to. Bound as a canonical field.
COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION: Final[str] = "reasoning_method.signed_comparison_result.v1"

#: The signing-frame domain tag, bound both outside the JSON (as the frame
#: prefix) and inside it. Nothing else in the repository signs under it.
COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN: Final[str] = (
    "ugence.reasoning-method-result-attestation/comparison-result-signing/v1"
)

#: The one admitted algorithm. There is no negotiation and no alias.
COMPARISON_RESULT_ATTESTATION_SIGNATURE_ALGORITHM: Final[str] = "Ed25519"

#: TEA's ratified Ed25519 profile and 128-hex encoding, by value.
COMPARISON_RESULT_ATTESTATION_SIGNATURE_PROFILE: Final[str] = TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1
COMPARISON_RESULT_ATTESTATION_SIGNATURE_ENCODING: Final[str] = TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1

#: What a VERIFIED result establishes, and all it establishes. Carried on every
#: result so no consumer can read a verification as a statement that the
#: comparison is correct.
COMPARISON_RESULT_ATTESTATION_ESTABLISHES: Final[str] = "PROVENANCE_AND_INTEGRITY_ONLY"

# Import-time separations, failing closed.
assert COMPARISON_RESULT_ATTESTATION_SCHEMA_VERSION != COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN
assert "effect" not in COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN
assert "cloud-scaling" not in COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN
assert "evidence" not in COMPARISON_RESULT_ATTESTATION_SIGNING_DOMAIN.split("/")[0].split(".")[1]
