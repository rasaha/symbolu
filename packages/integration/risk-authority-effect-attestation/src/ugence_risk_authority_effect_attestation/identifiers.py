"""The pinned identifiers of the effect-attestation contract.

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
    "EFFECT_ATTESTATION_SCHEMA_VERSION",
    "EFFECT_ATTESTATION_SIGNING_DOMAIN",
    "EFFECT_ATTESTATION_SIGNATURE_ALGORITHM",
    "EFFECT_ATTESTATION_SIGNATURE_PROFILE",
    "EFFECT_ATTESTATION_SIGNATURE_ENCODING",
    "EFFECT_ATTESTATION_ESTABLISHES",
]

#: The contract the signed bytes belong to. Bound as the first canonical field.
EFFECT_ATTESTATION_SCHEMA_VERSION: Final[str] = "risk_authority.effect_attestation.v1"

#: The signing-frame domain tag, bound both outside the JSON (as the frame
#: prefix) and inside it. Nothing else in the repository signs under it.
EFFECT_ATTESTATION_SIGNING_DOMAIN: Final[str] = (
    "ugence.risk-authority-effect-attestation/effect-attestation-signing/v1"
)

#: The one admitted algorithm. There is no negotiation and no alias.
EFFECT_ATTESTATION_SIGNATURE_ALGORITHM: Final[str] = "Ed25519"

#: TEA's ratified Ed25519 profile and 128-hex encoding, by value.
EFFECT_ATTESTATION_SIGNATURE_PROFILE: Final[str] = TRUSTED_EVIDENCE_SIGNATURE_PROFILE_V1
EFFECT_ATTESTATION_SIGNATURE_ENCODING: Final[str] = TRUSTED_EVIDENCE_SIGNATURE_ENCODING_V1

#: What a VERIFIED result establishes, and all it establishes. Carried on every
#: result so no consumer can read a verification as a statement about the world.
EFFECT_ATTESTATION_ESTABLISHES: Final[str] = "PROVENANCE_AND_INTEGRITY_ONLY"

# Import-time separations, failing closed.
assert EFFECT_ATTESTATION_SCHEMA_VERSION != EFFECT_ATTESTATION_SIGNING_DOMAIN
assert "cloud-scaling" not in EFFECT_ATTESTATION_SIGNING_DOMAIN
assert "evidence" not in EFFECT_ATTESTATION_SIGNING_DOMAIN.split("/")[0].split(".")[1]
