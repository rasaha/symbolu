"""Typed error vocabulary for the UVI Policy Authority (GV-2C-b).

Every rejection raised by the authority is one of these types. None of them is
ever an assertion that something *was* approved, signed, or resolved — they are
fail-closed refusals.

Resolution never raises for a trust failure: it returns a typed
:class:`~ugence_uvi_policy_authority.records.PolicyResolution` carrying a stable
status/reason pair. Exceptions are reserved for *caller* faults on the issuance
and revocation entry points (malformed request, unsupported family, digest
mismatch, registry conflict).
"""

from __future__ import annotations

__all__ = [
    "PolicyAuthorityError",
    "PolicyAuthorityRequestError",
    "UnsupportedPolicyFamilyError",
    "PolicyDigestMismatchError",
    "PolicyApprovalError",
    "PolicySigningError",
    "PolicyIssuanceError",
    "PolicyRegistryConflictError",
    "PolicyRevocationError",
]


class PolicyAuthorityError(Exception):
    """Base class for every Policy Authority refusal.

    Deliberately **not** a ``ValueError`` subclass of the contracts' own
    ``PolicyContractError``: a structural contract violation and an authority
    refusal are different concerns and must be distinguishable by callers.
    """


class PolicyAuthorityRequestError(PolicyAuthorityError):
    """The issuance/revocation request itself is structurally malformed.

    Raised before any approval verification, signing, or registry access.
    """


class UnsupportedPolicyFamilyError(PolicyAuthorityRequestError):
    """The supplied artifact is not one of the five merged UVI policy families.

    The authority issues a closed set of dataclasses. An arbitrary dataclass —
    even one carrying a well-formed :class:`PolicyArtifactMetadata` — is
    refused; a runtime type must match its declared ``PolicyFamily`` exactly.
    """


class PolicyDigestMismatchError(PolicyAuthorityRequestError):
    """The artifact's asserted ``content_digest`` does not bind its body.

    A caller-supplied 64-hex string is never evidence that the body matches it;
    the authority recomputes the canonical body digest and compares.
    """


class PolicyApprovalError(PolicyAuthorityError):
    """Approval evidence is absent, unverified, or does not bind this policy.

    Raised for every approval failure mode — missing, rejected, expired,
    revoked, mismatched, unverifiable, or self-approved. Failing closed here
    guarantees no signature is produced and no registry mutation occurs.
    """


class PolicySigningError(PolicyAuthorityError):
    """The injected signer refused, or produced unusable signature material."""


class PolicyIssuanceError(PolicyAuthorityError):
    """The artifact is not admissible for issuance as an active policy.

    Covers the lifecycle and effective-period rules checked at issuance time.
    """


class PolicyRegistryConflictError(PolicyAuthorityError):
    """A registry append would overwrite or contradict an existing record.

    Issued versions are append-only and immutable: a byte-identical
    re-submission is idempotent, any other reuse of the same identity/version
    is a conflict.
    """


class PolicyRevocationError(PolicyAuthorityError):
    """The revocation request is invalid, cross-tenant, or conflicting."""
