"""Ugence UVI Policy Authority (GV-2C-b).

A narrow **internal technical authority leaf** — not a customer-facing product,
and not a general-purpose governance authority. It owns exactly one technical
job: issuing, signing, registering, resolving, verifying and revoking **UVI
policy versions** for the five merged UVI policy families.

What it does **not** do, by design:

* it does not author policy content;
* it does not decide whether policy content is good, lawful, or commercially
  sound;
* it does not approve its own policy — approval remains an external
  human/governance responsibility, reaching the authority only through an
  injected trusted approval-verification boundary;
* it never trusts a caller-supplied ``approved=True``, authority label,
  lifecycle label, or evidence-status enum as proof of approval;
* it evaluates no readiness, calculates no value, resolves no benchmark, and
  performs no forecasting or attribution.

The reference registry is **in-memory and reference-grade**, not production
persistence. Benchmark-value registration is a separate, later milestone.

Import the curated surface from :mod:`ugence_uvi_policy_authority.api`.
See ``README.md`` for the exact trust guarantees and their limits.
"""

from __future__ import annotations

__version__ = "0.1.0"

from .approval import (  # noqa: E402
    ApprovalEvidenceRef,
    ApprovalVerification,
    ApprovalVerifier,
    DenyAllApprovalVerifier,
)
from .canonical import (  # noqa: E402
    POLICY_BODY_DIGEST_DOMAIN,
    canonical_policy_body_bytes,
    canonical_policy_body_digest,
)
from .ed25519 import SigningKey, VerifyKey  # noqa: E402
from .errors import (  # noqa: E402
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
from .families import (  # noqa: E402
    SUPPORTED_POLICY_FAMILIES,
    policy_family_of,
    require_supported_policy,
)
from .issuance import issue_policy  # noqa: E402
from .payload import (  # noqa: E402
    ISSUANCE_SIGNING_DOMAIN,
    REVOCATION_SIGNING_DOMAIN,
    issuance_signing_payload,
    revocation_signing_payload,
)
from .records import (  # noqa: E402
    IssuedPolicyRecord,
    PolicyResolution,
    PolicyRevocationRecord,
)
from .registry import InMemoryPolicyRegistry, PolicyRegistry  # noqa: E402
from .resolution import resolve_policy  # noqa: E402
from .revocation import revoke_policy  # noqa: E402
from .signing import (  # noqa: E402
    SIGNATURE_ALG,
    DenyAllSignatureVerifier,
    Ed25519PolicySigner,
    KeyVerification,
    PolicyKeyRing,
    PolicySignatureVerifier,
    PolicySigner,
    PolicyVerificationKey,
)
from .statuses import (  # noqa: E402
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
    "AUTHORITY_PROTOCOL",
    "AUTHORITY_PROTOCOL_VERSION",
    "PolicyAuthorityError",
    "PolicyAuthorityRequestError",
    "UnsupportedPolicyFamilyError",
    "PolicyDigestMismatchError",
    "PolicyApprovalError",
    "PolicySigningError",
    "PolicyIssuanceError",
    "PolicyRegistryConflictError",
    "PolicyRevocationError",
    "ApprovalVerificationStatus",
    "KeyVerificationStatus",
    "PolicyResolutionStatus",
    "PolicyResolutionReason",
    "PolicyRevocationReasonCode",
    "HistoricalResolutionRule",
    "SupersessionRule",
    "POLICY_BODY_DIGEST_DOMAIN",
    "canonical_policy_body_bytes",
    "canonical_policy_body_digest",
    "SUPPORTED_POLICY_FAMILIES",
    "policy_family_of",
    "require_supported_policy",
    "ApprovalEvidenceRef",
    "ApprovalVerification",
    "ApprovalVerifier",
    "DenyAllApprovalVerifier",
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
    "ISSUANCE_SIGNING_DOMAIN",
    "REVOCATION_SIGNING_DOMAIN",
    "issuance_signing_payload",
    "revocation_signing_payload",
    "IssuedPolicyRecord",
    "PolicyRevocationRecord",
    "PolicyResolution",
    "PolicyRegistry",
    "InMemoryPolicyRegistry",
    "issue_policy",
    "resolve_policy",
    "revoke_policy",
]
