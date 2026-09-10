"""Typed error vocabulary for the Ugence Policy Authority.

Every rejection raised by the authority is one of these types. None of them is
ever an assertion that something *was* approved, signed, or resolved — they are
fail-closed refusals.

Resolution never raises for a trust failure: it returns a typed
:class:`~ugence_policy_authority.core.records.PolicyResolution` carrying a
stable status/reason pair. Exceptions are reserved for *caller* faults on the
issuance and revocation entry points.
"""

from __future__ import annotations

__all__ = [
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
    "PolicySuspensionError",
    "PolicyExclusivityError",
]


class PolicyAuthorityError(Exception):
    """Base class for every Policy Authority refusal."""


class PolicyAuthorityRequestError(PolicyAuthorityError):
    """The issuance/revocation request itself is structurally malformed.

    Raised before any approval verification, signing, or registry access.
    """


class UnsupportedPolicyArtifactError(PolicyAuthorityRequestError):
    """No registered policy-family adapter recognizes this artifact.

    The authority issues only artifacts a registered adapter claims and can
    fully describe. An unrecognized object — however well-formed — is refused.
    """


class PolicyCanonicalizationError(PolicyAuthorityRequestError):
    """The artifact cannot be canonicalized under the declared rules.

    Raised for a naive datetime, a non-NFC string, a ``float``, or any type the
    canonical encoder does not admit. These are refusals, not coercions: the
    authority never silently repairs an artifact into a digestible shape.
    """


class PolicyDigestMismatchError(PolicyAuthorityRequestError):
    """The artifact's declared content digest does not bind its canonical body.

    A caller-supplied 64-hex string is never evidence that the body matches it.
    """


class UnsupportedSupersessionError(PolicyAuthorityRequestError):
    """The artifact declares a non-empty unstructured supersession reference.

    An unstructured ``supersedes_ref`` cannot bind a complete exact policy
    coordinate, and guessing one would be an unsigned authority decision. v0.1
    refuses issuance outright (ADR §13); structured successor references are a
    separate, deferred contract milestone.
    """


class PolicyApprovalError(PolicyAuthorityError):
    """Approval evidence is absent, unverified, or does not bind this policy."""


class PolicySigningError(PolicyAuthorityError):
    """The injected signer refused, or produced unusable signature material."""


class PolicyIssuanceError(PolicyAuthorityError):
    """The artifact is not admissible for issuance as an active policy."""


class PolicyRegistryConflictError(PolicyAuthorityError):
    """A registry append would overwrite or contradict an existing record."""


class PolicyRegistryStorageError(PolicyAuthorityError):
    """The durable registry could not be used as a registry.

    Raised when the store is closed or unreachable, its schema version does not
    match, or a stored record cannot be rehydrated by the configured codec. Every
    case fails closed: a record that cannot be read is never treated as absent.
    """


class PolicyRegistryProductionModeError(PolicyRegistryStorageError):
    """A reference-grade registry was asked to run in production mode."""


class PolicySupersessionError(PolicyAuthorityError):
    """A structured supersession reference was present but inadmissible.

    `ACC-LC-IA-3`. Raised when the named predecessor does not exist, does not
    resolve at the issuance instant, is already revoked or superseded, sits in
    another tenant or scope, or is the artifact naming itself. Distinct from
    :class:`UnsupportedSupersessionError`, which refuses the *unstructured*
    string and is unchanged. Nothing is signed and nothing is stored.
    """


class PolicyExclusivityError(PolicyAuthorityError):
    """An artifact claimed exclusive governance of something already governed.

    `ACC-OVL-1` – `ACC-OVL-3`. Raised at issuance when another simultaneously
    effective version, in the same tenant and scope, holds an equal exclusivity
    claim and no verified supersession relationship permits the overlap.

    `[R]` There is no variant of this that resolves the overlap by choosing a
    winner. Registration order, mapping order and arrival order are all refused
    as tie-breakers, so an ambiguous state is reported rather than silently
    decided. Nothing is signed and nothing is stored.
    """


class PolicySuspensionError(PolicyAuthorityError):
    """A suspension lifecycle act was refused, and nothing was signed or stored.

    `ACC-SUSP-IA-7`. Raised when the targeted version was never issued, is
    already revoked or superseded, when the signing key is not entitled to
    :attr:`~ugence_policy_authority.core.statuses.KeyEntitlement.SUSPEND_POLICY`,
    or when the candidate record would break either ordering invariant:

    * its signed instant is **not strictly later** than the latest accepted
      record for that coordinate — a retroactive insertion, refused rather than
      sorted into place;
    * it is a ``REINSTATE`` whose latest accepted state is not ``SUSPEND`` — a
      reinstatement cannot manufacture the transition it claims to reverse.

    An **exact replay** of an already-stored record is not an error: it is an
    idempotent no-op, on the revocation store's precedent.
    """


class PolicyRevocationError(PolicyAuthorityError):
    """The revocation request is invalid, unauthorized, cross-tenant, or conflicting."""
