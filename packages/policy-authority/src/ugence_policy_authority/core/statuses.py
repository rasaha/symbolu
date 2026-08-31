"""Stable typed status / reason vocabulary for the Ugence Policy Authority.

Every value is a stable token consumers may branch on; values are never
repurposed. Nothing here is collapsed into a free-form string, and no failure
mode is reported as a generic exception.

This vocabulary is **platform-neutral**: it names no policy family. Family
recognition lives entirely in registered adapters.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "AUTHORITY_PROTOCOL",
    "AUTHORITY_PROTOCOL_VERSION",
    "AUTHORITY_PROTOCOL_ID",
    "CANONICALIZATION_VERSION",
    "ApprovalVerificationStatus",
    "KeyEntitlement",
    "KeyVerificationStatus",
    "PolicyResolutionStatus",
    "PolicyResolutionReason",
    "PolicyRevocationReasonCode",
    "HistoricalResolutionRule",
]

#: Identity of the shared authority protocol. Platform-neutral: it names no
#: policy family, no capability, and no milestone.
AUTHORITY_PROTOCOL = "ugence.policy-authority"

#: Version of the ratified issuance/resolution rule set implemented here.
#: Bumped only when a signed payload shape or a trust rule changes.
AUTHORITY_PROTOCOL_VERSION = "v0.1"

#: The exact protocol identifier bound into every signed payload. Snapshotted in
#: ``public_api.json`` so a change is visible in review.
AUTHORITY_PROTOCOL_ID = f"{AUTHORITY_PROTOCOL}/{AUTHORITY_PROTOCOL_VERSION}"

#: Version of the canonicalization rules (encoding, key ordering, Unicode
#: posture, datetime rendering). Bound into every digest and signed payload.
CANONICALIZATION_VERSION = "ugence.policy-authority/canonicalization/v1"


class ApprovalVerificationStatus(str, Enum):
    """Outcome reported by an injected external approval verifier.

    Only :attr:`APPROVED` may lead to issuance, and only after the authority
    independently re-checks that the returned verification *binds* the exact
    policy being issued. Every other member fails closed.
    """

    APPROVED = "APPROVED"
    NOT_FOUND = "NOT_FOUND"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    MISMATCHED = "MISMATCHED"
    UNVERIFIED = "UNVERIFIED"
    NO_APPROVAL_AUTHORITY_CONFIGURED = "NO_APPROVAL_AUTHORITY_CONFIGURED"


class KeyEntitlement(str, Enum):
    """What a registered trust anchor is authorized to do.

    A key entitled only to issue cannot revoke, and vice versa. This is what
    makes "the revoking authority must be authorized for the exact policy
    scope" enforceable rather than aspirational.
    """

    ISSUE_POLICY = "ISSUE_POLICY"
    REVOKE_POLICY = "REVOKE_POLICY"


class KeyVerificationStatus(str, Enum):
    """Outcome of resolving a trust anchor by exact ``key_id`` and checking it."""

    VALID = "VALID"
    UNKNOWN_KEY = "UNKNOWN_KEY"
    REVOKED_KEY = "REVOKED_KEY"
    KEY_NOT_IN_WINDOW = "KEY_NOT_IN_WINDOW"
    WRONG_AUTHORITY = "WRONG_AUTHORITY"
    WRONG_TENANT = "WRONG_TENANT"
    NOT_ENTITLED = "NOT_ENTITLED"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    NO_VERIFIER_CONFIGURED = "NO_VERIFIER_CONFIGURED"


class PolicyResolutionStatus(str, Enum):
    """The two-valued outcome of a trusted resolution.

    A policy artifact is returned **only** under :attr:`RESOLVED`; the result
    shape enforces this structurally.
    """

    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class PolicyResolutionReason(str, Enum):
    """The single stable reason a resolution succeeded or failed closed."""

    RESOLVED = "RESOLVED"
    TENANT_SCOPE_MISMATCH = "TENANT_SCOPE_MISMATCH"
    NOT_FOUND = "NOT_FOUND"
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    ARTIFACT_REFERENCE_MISMATCH = "ARTIFACT_REFERENCE_MISMATCH"
    NO_ADAPTER_REGISTERED = "NO_ADAPTER_REGISTERED"
    ARTIFACT_NOT_CANONICALIZABLE = "ARTIFACT_NOT_CANONICALIZABLE"
    CONTENT_DIGEST_MISMATCH = "CONTENT_DIGEST_MISMATCH"
    BODY_DIGEST_MISMATCH = "BODY_DIGEST_MISMATCH"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    KEY_UNKNOWN = "KEY_UNKNOWN"
    KEY_REVOKED = "KEY_REVOKED"
    KEY_NOT_ENTITLED = "KEY_NOT_ENTITLED"
    APPROVAL_PROOF_INVALID = "APPROVAL_PROOF_INVALID"
    LIFECYCLE_NOT_ACTIVE = "LIFECYCLE_NOT_ACTIVE"
    NOT_YET_EFFECTIVE = "NOT_YET_EFFECTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    #: A revocation record targeting this version exists but does not verify —
    #: unsigned, wrong key, unauthorized signer, or tampered. It neither denies
    #: as a valid revocation nor is ignored: it fails closed as an integrity
    #: error (ADR §14.7).
    REVOCATION_INTEGRITY_INVALID = "REVOCATION_INTEGRITY_INVALID"
    #: The stored artifact declares a non-empty unstructured ``supersedes_ref``.
    #: v0.1 refuses to issue such an artifact; a legacy or hand-assembled record
    #: that reaches resolution fails closed here rather than being guessed at.
    SUPERSESSION_REFERENCE_UNSUPPORTED = "SUPERSESSION_REFERENCE_UNSUPPORTED"
    #: `ACC-LC-IA-2`. A verified supersession record names this version as the
    #: predecessor of a successor issued over it. The record stays readable as
    #: history; it simply no longer resolves.
    SUPERSEDED = "SUPERSEDED"
    #: A supersession record targeting this version exists but does not verify —
    #: unsigned, wrong key, unauthorized signer, or tampered. Like its revocation
    #: counterpart it fails closed rather than being ignored.
    SUPERSESSION_INTEGRITY_INVALID = "SUPERSESSION_INTEGRITY_INVALID"


class PolicyRevocationReasonCode(str, Enum):
    """Why an authority revoked one exact policy version.

    Policy-version revocation is a distinct concept from signing-key revocation
    and from Risk Authority envelope revocation; none of the three implies any
    other.
    """

    CONTENT_DEFECT = "CONTENT_DEFECT"
    APPROVAL_WITHDRAWN = "APPROVAL_WITHDRAWN"
    COMPLIANCE_VIOLATION = "COMPLIANCE_VIOLATION"
    ISSUED_IN_ERROR = "ISSUED_IN_ERROR"
    REPLACED = "REPLACED"
    KEY_COMPROMISE = "KEY_COMPROMISE"
    OTHER = "OTHER"


class HistoricalResolutionRule(str, Enum):
    """How a verified revocation affects resolution *before* its instant.

    Revocation is always absolute at and after ``revoked_at``. What happens for
    an explicitly historical ``as_of`` strictly before ``revoked_at`` is a
    deliberate, configured decision — never an implicit default. A historical
    answer is labelled as such on the result and never implies current validity
    (ADR §14.10).
    """

    #: Default, fail-closed: a revoked version never resolves, at any ``as_of``.
    DENY_ALWAYS = "DENY_ALWAYS"
    #: A historical ``as_of`` strictly before ``revoked_at`` may still resolve.
    #: The result carries ``historical=True`` and its explicit ``as_of``.
    ALLOW_BEFORE_REVOCATION = "ALLOW_BEFORE_REVOCATION"
