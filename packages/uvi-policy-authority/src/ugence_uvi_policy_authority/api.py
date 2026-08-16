"""Canonical public API for the Ugence UVI Policy Authority.

The deliberately small, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_uvi_policy_authority`). Every
symbol below is stable; ``public_api.json`` snapshots this surface and
``tests/packaging/test_public_api.py`` asserts they agree.

Note what is **not** exported: there is no allow-all approval verifier, no
"mark approved" helper, no floating-reference lookup, and no way to hand the
authority a signature. Those are not omissions to be filled in later — their
absence is the boundary.
"""

from __future__ import annotations

from . import __version__
from .approval import (
    ApprovalEvidenceRef,
    ApprovalVerification,
    ApprovalVerifier,
    DenyAllApprovalVerifier,
)
from .canonical import (
    POLICY_BODY_DIGEST_DOMAIN,
    canonical_policy_body_bytes,
    canonical_policy_body_digest,
)
from .ed25519 import SigningKey, VerifyKey
from .errors import (
    PolicyApprovalError,
    PolicyAuthorityError,
    PolicyAuthorityRequestError,
    PolicyDigestMismatchError,
    PolicyIssuanceError,
    PolicyRegistryConflictError,
    PolicyRevocationError,
    PolicySigningError,
    UnsupportedPolicyFamilyError,
)
from .families import SUPPORTED_POLICY_FAMILIES, policy_family_of, require_supported_policy
from .issuance import issue_policy
from .payload import (
    ISSUANCE_SIGNING_DOMAIN,
    REVOCATION_SIGNING_DOMAIN,
    issuance_signing_payload,
    revocation_signing_payload,
)
from .records import IssuedPolicyRecord, PolicyResolution, PolicyRevocationRecord
from .registry import InMemoryPolicyRegistry, PolicyRegistry
from .resolution import resolve_policy
from .revocation import revoke_policy
from .signing import (
    SIGNATURE_ALG,
    DenyAllSignatureVerifier,
    Ed25519PolicySigner,
    KeyVerification,
    PolicyKeyRing,
    PolicySignatureVerifier,
    PolicySigner,
    PolicyVerificationKey,
)
from .statuses import (
    AUTHORITY_PROTOCOL,
    AUTHORITY_PROTOCOL_VERSION,
    ApprovalVerificationStatus,
    HistoricalResolutionRule,
    KeyVerificationStatus,
    PolicyResolutionReason,
    PolicyResolutionStatus,
    PolicyRevocationReasonCode,
    SupersessionRule,
)

__all__ = [
    "__version__",
    # Protocol identity
    "AUTHORITY_PROTOCOL",
    "AUTHORITY_PROTOCOL_VERSION",
    # Errors
    "PolicyAuthorityError",
    "PolicyAuthorityRequestError",
    "UnsupportedPolicyFamilyError",
    "PolicyDigestMismatchError",
    "PolicyApprovalError",
    "PolicySigningError",
    "PolicyIssuanceError",
    "PolicyRegistryConflictError",
    "PolicyRevocationError",
    # Statuses / reasons
    "ApprovalVerificationStatus",
    "KeyVerificationStatus",
    "PolicyResolutionStatus",
    "PolicyResolutionReason",
    "PolicyRevocationReasonCode",
    "HistoricalResolutionRule",
    "SupersessionRule",
    # Canonicalization & digest binding
    "POLICY_BODY_DIGEST_DOMAIN",
    "canonical_policy_body_bytes",
    "canonical_policy_body_digest",
    # Supported families
    "SUPPORTED_POLICY_FAMILIES",
    "policy_family_of",
    "require_supported_policy",
    # Approval boundary
    "ApprovalEvidenceRef",
    "ApprovalVerification",
    "ApprovalVerifier",
    "DenyAllApprovalVerifier",
    # Signing boundary
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
    "ISSUANCE_SIGNING_DOMAIN",
    "REVOCATION_SIGNING_DOMAIN",
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
]
