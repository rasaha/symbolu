"""Stable typed status / reason vocabulary for the UVI Policy Authority.

Every value is a stable token consumers may branch on; values are never
repurposed. Nothing here is collapsed into a free-form string, and no failure
mode is reported as a generic exception.

The four trust questions the authority answers are deliberately kept apart and
each has its own vocabulary:

* :class:`ApprovalVerificationStatus` — did an *external* approval authority
  approve this exact policy version?
* :class:`KeyVerificationStatus` — is the signing key recognized, in-window and
  un-revoked for this authority and tenant?
* :class:`PolicyResolutionReason` — the single reason a trusted resolution
  succeeded or failed closed.
* :class:`PolicyRevocationReasonCode` — why an authority revoked an exact
  policy version.

None of them is a statement about whether the policy *content* is correct or
commercially sound. See ``README.md`` §"What a resolution does and does not
prove".
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "AUTHORITY_PROTOCOL",
    "AUTHORITY_PROTOCOL_VERSION",
    "ApprovalVerificationStatus",
    "KeyVerificationStatus",
    "PolicyResolutionStatus",
    "PolicyResolutionReason",
    "PolicyRevocationReasonCode",
    "HistoricalResolutionRule",
    "SupersessionRule",
]

#: Identity of this authority protocol. Bound into every signed payload so a
#: signature produced under one protocol can never be replayed under another.
AUTHORITY_PROTOCOL = "ugence.uvi.policy-authority"

#: Version of the ratified issuance/resolution rule set implemented here.
#: Bumped only when the signed payload shape or a trust rule changes.
AUTHORITY_PROTOCOL_VERSION = "GV-2C-b.1"


class ApprovalVerificationStatus(str, Enum):
    """Outcome reported by an injected external approval verifier.

    Only :attr:`APPROVED` may lead to issuance, and only after the authority
    independently re-checks that the returned verification *binds* the exact
    policy being issued. Every other member fails closed.
    """

    #: The approval authority verified this exact policy version.
    APPROVED = "APPROVED"
    #: No approval artifact was supplied or the reference resolved to nothing.
    NOT_FOUND = "NOT_FOUND"
    #: The approval authority explicitly rejected the policy.
    REJECTED = "REJECTED"
    #: The approval existed but its approved period has elapsed.
    EXPIRED = "EXPIRED"
    #: The approval was withdrawn by the approving authority.
    REVOKED = "REVOKED"
    #: The artifact resolved, but binds a different policy/digest/tenant.
    MISMATCHED = "MISMATCHED"
    #: The verifier could not establish authenticity of the approval artifact.
    UNVERIFIED = "UNVERIFIED"
    #: No approval authority is configured — the deny-by-default outcome.
    NO_APPROVAL_AUTHORITY_CONFIGURED = "NO_APPROVAL_AUTHORITY_CONFIGURED"


class KeyVerificationStatus(str, Enum):
    """Outcome of resolving and checking an issuance signing key by ``key_id``."""

    #: The key is known, in-window, un-revoked, and the signature verified.
    VALID = "VALID"
    #: No key is registered under this exact ``key_id``.
    UNKNOWN_KEY = "UNKNOWN_KEY"
    #: The key is registered but has been revoked.
    REVOKED_KEY = "REVOKED_KEY"
    #: The key exists but is outside its ``not_before``/``not_after`` window.
    KEY_NOT_IN_WINDOW = "KEY_NOT_IN_WINDOW"
    #: The key belongs to a different issuing authority.
    WRONG_AUTHORITY = "WRONG_AUTHORITY"
    #: The key is bound to a different tenant than the artifact.
    WRONG_TENANT = "WRONG_TENANT"
    #: The key resolved and was eligible, but the signature did not verify.
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    #: No signature verifier is configured — the deny-by-default outcome.
    NO_VERIFIER_CONFIGURED = "NO_VERIFIER_CONFIGURED"


class PolicyResolutionStatus(str, Enum):
    """The two-valued outcome of a trusted resolution.

    A policy artifact is returned **only** under :attr:`RESOLVED`; the result
    shape enforces this structurally, so a caller can never receive a policy
    alongside a failed status.
    """

    RESOLVED = "RESOLVED"
    UNRESOLVED = "UNRESOLVED"


class PolicyResolutionReason(str, Enum):
    """The single stable reason a resolution succeeded or failed closed.

    Exactly one reason is reported per resolution, selected in the fixed order
    documented on :func:`~ugence_uvi_policy_authority.resolution.resolve_policy`.
    """

    #: Every trust condition held at ``as_of``.
    RESOLVED = "RESOLVED"
    #: The requested tenant/scope does not match the requested reference.
    TENANT_SCOPE_MISMATCH = "TENANT_SCOPE_MISMATCH"
    #: No issuance record exists under this exact reference.
    NOT_FOUND = "NOT_FOUND"
    #: The stored record's reference is not the reference requested.
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    #: The stored artifact's own metadata does not derive the stored reference.
    ARTIFACT_REFERENCE_MISMATCH = "ARTIFACT_REFERENCE_MISMATCH"
    #: The recomputed canonical body digest is not the attested content digest.
    CONTENT_DIGEST_MISMATCH = "CONTENT_DIGEST_MISMATCH"
    #: The recomputed body digest is not the digest bound into the signature.
    BODY_DIGEST_MISMATCH = "BODY_DIGEST_MISMATCH"
    #: The issuance signature did not verify over the signed payload.
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    #: The signing key is not registered under this exact ``key_id``.
    KEY_UNKNOWN = "KEY_UNKNOWN"
    #: The signing key is registered but revoked, out of window, or bound to a
    #: different authority/tenant.
    KEY_REVOKED = "KEY_REVOKED"
    #: Approval proof is absent, unverified, or does not bind this policy.
    APPROVAL_PROOF_INVALID = "APPROVAL_PROOF_INVALID"
    #: The artifact's lifecycle state is not ``APPROVED_ACTIVE``.
    LIFECYCLE_NOT_ACTIVE = "LIFECYCLE_NOT_ACTIVE"
    #: ``as_of`` precedes the inclusive ``effective_from`` bound.
    NOT_YET_EFFECTIVE = "NOT_YET_EFFECTIVE"
    #: ``as_of`` is at or after the exclusive ``effective_to`` bound.
    EXPIRED = "EXPIRED"
    #: A targeted revocation of this exact version applies at ``as_of``.
    REVOKED = "REVOKED"
    #: The artifact declares itself superseded.
    SUPERSEDED = "SUPERSEDED"
    #: A successor artifact exists, but the merged contracts do not carry enough
    #: information to determine whether it *binds* — deferred, never guessed.
    SUPERSESSION_UNDETERMINED = "SUPERSESSION_UNDETERMINED"


class PolicyRevocationReasonCode(str, Enum):
    """Why an authority revoked one exact policy version.

    Policy-version revocation is a distinct concept from authority/key
    revocation and from Risk Authority envelope revocation; none of the three
    implies either of the others.
    """

    #: The policy content was found to be defective.
    CONTENT_DEFECT = "CONTENT_DEFECT"
    #: The approval that justified issuance was withdrawn.
    APPROVAL_WITHDRAWN = "APPROVAL_WITHDRAWN"
    #: The policy is no longer compliant with governing regulation.
    COMPLIANCE_VIOLATION = "COMPLIANCE_VIOLATION"
    #: The issuance itself was erroneous (wrong artifact, wrong scope).
    ISSUED_IN_ERROR = "ISSUED_IN_ERROR"
    #: A replacement version has been issued and this one is withdrawn.
    REPLACED = "REPLACED"
    #: A key or authority compromise makes the issuance untrustworthy.
    KEY_COMPROMISE = "KEY_COMPROMISE"
    #: Withdrawn for a reason the authority records out of band.
    OTHER = "OTHER"


class HistoricalResolutionRule(str, Enum):
    """How a recorded revocation affects resolution *before* its instant.

    Revocation is always absolute at and after ``revoked_at``. What happens for
    an explicitly historical ``as_of`` strictly before ``revoked_at`` is a
    deliberate, configured decision — never an implicit default.
    """

    #: Default, fail-closed: a revoked version never resolves, at any ``as_of``.
    DENY_ALWAYS = "DENY_ALWAYS"
    #: A historical ``as_of`` strictly before ``revoked_at`` may still resolve;
    #: ``as_of >= revoked_at`` still fails closed.
    ALLOW_BEFORE_REVOCATION = "ALLOW_BEFORE_REVOCATION"


class SupersessionRule(str, Enum):
    """How supersession affects resolution.

    ``PolicyArtifactMetadata.supersedes_ref`` is an unstructured ``str`` in the
    merged contracts: it cannot bind a complete exact ``PolicyReference`` (no
    family, digest, scope or tenant). The authority therefore refuses to infer
    a binding supersession from it — it either ignores it or fails closed with
    a typed deferred status, and never guesses.
    """

    #: Default: only an artifact's own ``SUPERSEDED`` lifecycle invalidates it.
    SELF_DECLARED_ONLY = "SELF_DECLARED_ONLY"
    #: Additionally fail closed with ``SUPERSESSION_UNDETERMINED`` when another
    #: issued version of the same identity declares a non-empty
    #: ``supersedes_ref`` that cannot be resolved to an exact reference.
    STRICT_UNDETERMINED_ON_SUCCESSOR = "STRICT_UNDETERMINED_ON_SUCCESSOR"
