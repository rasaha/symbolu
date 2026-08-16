"""Canonical public API for the Ugence Policy Authority.

The deliberately small, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_policy_authority`).

Note what is **not** exported: there is no allow-all approval verifier, no test
verifier, no "mark approved" helper, no floating-reference lookup, no unsigned
revocation path, and no way to hand the authority a signature. Those absences
are the boundary, not gaps to be filled in later.
"""

from __future__ import annotations

from . import __version__
from .adapters.uvi import (
    SUPPORTED_UVI_POLICY_FAMILIES,
    UVI_ADAPTER_ID,
    UviPolicyFamilyAdapter,
    uvi_coordinate,
)
from .core.adapters import (
    GLOBAL_TENANT,
    AdapterRegistry,
    PolicyArtifactDescriptor,
    PolicyCoordinate,
    PolicyFamilyAdapter,
)
from .core.approval import (
    ApprovalEvidenceRef,
    ApprovalVerification,
    ApprovalVerifier,
    DenyAllApprovalVerifier,
)
from .core.canonical import (
    CANONICALIZATION_VERSION,
    POLICY_BODY_DIGEST_DOMAIN,
    canonical_bytes,
    framed_body_bytes,
    framed_body_digest,
    sha256_hex,
)
from .core.ed25519 import SigningKey, VerifyKey
from .core.errors import (
    PolicyApprovalError,
    PolicyAuthorityError,
    PolicyAuthorityRequestError,
    PolicyCanonicalizationError,
    PolicyDigestMismatchError,
    PolicyIssuanceError,
    PolicyRegistryConflictError,
    PolicyRevocationError,
    PolicySigningError,
    UnsupportedPolicyArtifactError,
    UnsupportedSupersessionError,
)
from .core.issuance import SUPERSESSION_REFERENCE_UNSUPPORTED, issue_policy
from .core.payload import (
    ISSUANCE_SIGNING_DOMAIN,
    REVOCATION_SIGNING_DOMAIN,
    issuance_signing_payload,
    revocation_signing_payload,
)
from .core.records import IssuedPolicyRecord, PolicyResolution, PolicyRevocationRecord
from .core.registry import InMemoryPolicyRegistry, PolicyRegistry
from .core.resolution import resolve_policy
from .core.revocation import revoke_policy, verify_revocation_record
from .core.signing import (
    SIGNATURE_ALG,
    DenyAllSignatureVerifier,
    Ed25519PolicySigner,
    KeyVerification,
    PolicyKeyRing,
    PolicySignatureVerifier,
    PolicySigner,
    PolicyVerificationKey,
)
from .core.statuses import (
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_ID,
    AUTHORITY_PROTOCOL_VERSION,
    ApprovalVerificationStatus,
    HistoricalResolutionRule,
    KeyEntitlement,
    KeyVerificationStatus,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
)

__all__ = [
    "__version__",
    # Protocol and canonicalization identity
    "AUTHORITY_PROTOCOL",
    "AUTHORITY_PROTOCOL_VERSION",
    "AUTHORITY_PROTOCOL_ID",
    "CANONICALIZATION_VERSION",
    "POLICY_BODY_DIGEST_DOMAIN",
    "ISSUANCE_SIGNING_DOMAIN",
    "REVOCATION_SIGNING_DOMAIN",
    # Errors
    "PolicyAuthorityError",
    "PolicyAuthorityRequestError",
    "UnsupportedPolicyArtifactError",
    "PolicyCanonicalizationError",
    "PolicyDigestMismatchError",
    "UnsupportedSupersessionError",
    "PolicyApprovalError",
    "PolicySigningError",
    "PolicyIssuanceError",
    "PolicyRegistryConflictError",
    "PolicyRevocationError",
    "SUPERSESSION_REFERENCE_UNSUPPORTED",
    # Statuses / reasons
    "ApprovalVerificationStatus",
    "KeyEntitlement",
    "KeyVerificationStatus",
    "PolicyResolutionStatus",
    "PolicyResolutionReason",
    "PolicyRevocationReasonCode",
    "HistoricalResolutionRule",
    # Family-neutral identity and the adapter seam
    "GLOBAL_TENANT",
    "PolicyCoordinate",
    "PolicyArtifactDescriptor",
    "PolicyFamilyAdapter",
    "AdapterRegistry",
    # Canonicalization helpers for independent verification
    "canonical_bytes",
    "sha256_hex",
    "framed_body_bytes",
    "framed_body_digest",
    # Approval boundary
    "ApprovalEvidenceRef",
    "ApprovalVerification",
    "ApprovalVerifier",
    "DenyAllApprovalVerifier",
    # Signing boundary and trust anchors
    "SIGNATURE_ALG",
    "SigningKey",
    "VerifyKey",
    "PolicySigner",
    "PolicySignatureVerifier",
    "Ed25519PolicySigner",
    "PolicyVerificationKey",
    "PolicyKeyRing",
    "KeyVerification",
    "DenyAllSignatureVerifier",
    # Signed payloads
    "issuance_signing_payload",
    "revocation_signing_payload",
    # Records
    "IssuedPolicyRecord",
    "PolicyRevocationRecord",
    "PolicyResolution",
    # Registry
    "PolicyRegistry",
    "InMemoryPolicyRegistry",
    # Services
    "issue_policy",
    "resolve_policy",
    "revoke_policy",
    "verify_revocation_record",
    # The first policy-family adapter (UVI)
    "UVI_ADAPTER_ID",
    "SUPPORTED_UVI_POLICY_FAMILIES",
    "UviPolicyFamilyAdapter",
    "uvi_coordinate",
    "default_uvi_adapters",
]


def default_uvi_adapters() -> AdapterRegistry:
    """Convenience composition root: a registry holding just the UVI adapter.

    A convenience only. The authority core depends on the adapter *protocol*,
    never on this function or on UVI — a deployment may assemble any registry,
    including one with no UVI adapter at all.
    """

    return AdapterRegistry((UviPolicyFamilyAdapter(),))
