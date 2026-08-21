"""The closed policy-authenticity outcome vocabulary. Every non-``VERIFIED`` member is a refusal.

Three properties make this vocabulary load-bearing rather than decorative.

**Security outcomes are distinguished by type, never by message string.** A caller branches
on a :class:`PolicyAuthenticityOutcome` member; the message exists for humans.

**Unknown is a refusal.** :attr:`PolicyAuthenticityOutcome.INDETERMINATE` is the default arm
of every exhaustive match in this package, including the mapping from the Policy Authority's
own :class:`~ugence_policy_authority.api.PolicyResolutionReason`. A reason this package does
not recognise — one a future Policy Authority version adds — becomes ``INDETERMINATE``, which
is a refusal, never a pass.

**The Policy Authority's reasons are carried across, not collapsed.** Every member of
``PolicyResolutionReason`` maps to a distinct member here, so a consumer can tell
``REVOKED`` from ``EXPIRED`` from ``KEY_NOT_ENTITLED`` without parsing prose, and
:data:`RESOLUTION_REASON_OUTCOMES` is asserted total over that enum by
``tests/test_typed_outcomes.py``.

There is exactly one success member, and holding it establishes **policy authenticity
only** — that one exact policy version was authentically issued and is valid at the injected
instant. It is not authorization, and it does not bind that policy to any recommendation,
scope or candidate. See :mod:`.verified`.
"""

from __future__ import annotations

from enum import Enum
from typing import Final

from ugence_policy_authority.api import PolicyResolutionReason

__all__ = [
    "PolicyAuthenticityOutcome",
    "REFUSAL_OUTCOMES",
    "RESOLUTION_REASON_OUTCOMES",
    "TEMPORAL_OUTCOMES",
    "resolution_reason_outcome",
]


class PolicyAuthenticityOutcome(str, Enum):
    """The one closed vocabulary for the result of policy-authenticity verification."""

    # --- the single success ------------------------------------------------------------
    #: The coordinate resolved, under the configured policy trust, at the injected
    #: ``as_of``, to a non-historical ``RESOLVED`` answer whose record carries that exact
    #: coordinate and binds its own body digest. Nothing more. It is not an authorization.
    VERIFIED = "VERIFIED"

    # --- admission ----------------------------------------------------------------------
    #: An input was not the exact required type. Subclasses and look-alikes land here.
    UNSUPPORTED_EXACT_TYPE = "UNSUPPORTED_EXACT_TYPE"
    #: The coordinate is structurally unusable, or an instant was naive.
    COORDINATE_MALFORMED = "COORDINATE_MALFORMED"
    #: The caller's ``expected_reference_tenant_id`` is not the coordinate's own tenant
    #: component. Refused before the authority is asked anything.
    TENANT_EXPECTATION_MISMATCH = "TENANT_EXPECTATION_MISMATCH"
    #: The record names a signature algorithm outside the closed admitted set.
    UNSUPPORTED_ALGORITHM = "UNSUPPORTED_ALGORITHM"

    # --- the Policy Authority's own refusals, carried across one-for-one -----------------
    #: The reference's declared tenant did not match the tenant presented to the authority.
    TENANT_SCOPE_MISMATCH = "TENANT_SCOPE_MISMATCH"
    #: No record exists under the exact coordinate. Exact-match lookup is the only lookup.
    POLICY_NOT_FOUND = "POLICY_NOT_FOUND"
    #: The stored record does not carry the coordinate it was filed under.
    REFERENCE_MISMATCH = "REFERENCE_MISMATCH"
    #: The stored artifact no longer re-derives the coordinate it was issued under.
    ARTIFACT_REFERENCE_MISMATCH = "ARTIFACT_REFERENCE_MISMATCH"
    #: No registered adapter still claims the stored artifact.
    NO_ADAPTER_REGISTERED = "NO_ADAPTER_REGISTERED"
    #: The stored artifact no longer canonicalizes.
    ARTIFACT_NOT_CANONICALIZABLE = "ARTIFACT_NOT_CANONICALIZABLE"
    #: The declared content digest is not the recomputed body digest.
    CONTENT_DIGEST_MISMATCH = "CONTENT_DIGEST_MISMATCH"
    #: The signed body digest is not the recomputed body digest.
    BODY_DIGEST_MISMATCH = "BODY_DIGEST_MISMATCH"
    #: The issuance signature did not verify under the named key.
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    #: No trust anchor is registered under the record's ``key_id``, or none was configured.
    KEY_UNKNOWN = "KEY_UNKNOWN"
    #: The signing key is revoked, outside its window, bound to another tenant, or belongs
    #: to another authority. The Policy Authority reports all four as ``KEY_REVOKED``.
    KEY_REVOKED = "KEY_REVOKED"
    #: The key is not entitled to ``ISSUE_POLICY``.
    KEY_NOT_ENTITLED = "KEY_NOT_ENTITLED"
    #: External approval evidence failed re-verification at the injected instant.
    APPROVAL_PROOF_INVALID = "APPROVAL_PROOF_INVALID"
    #: The artifact's lifecycle label is not an active one.
    LIFECYCLE_NOT_ACTIVE = "LIFECYCLE_NOT_ACTIVE"
    #: The injected instant precedes the artifact's ``effective_from``.
    NOT_YET_EFFECTIVE = "NOT_YET_EFFECTIVE"
    #: The injected instant is at or after the artifact's ``effective_to``.
    EXPIRED = "EXPIRED"
    #: A verified revocation applies at the injected instant.
    REVOKED = "REVOKED"
    #: A revocation record targeting this version exists but does not itself verify. It is
    #: neither honoured as a revocation nor ignored: it fails closed.
    REVOCATION_INTEGRITY_INVALID = "REVOCATION_INTEGRITY_INVALID"
    #: The stored artifact declares an unstructured supersession reference.
    SUPERSESSION_REFERENCE_UNSUPPORTED = "SUPERSESSION_REFERENCE_UNSUPPORTED"

    # --- this package's own gates, on top of a RESOLVED answer ---------------------------
    #: The answer is a historical one. A historical resolution describes the past and can
    #: never back an authorization, so it is refused at admission rather than carried
    #: forward labelled (D-5B0B-1).
    HISTORICAL_RESOLUTION_REFUSED = "HISTORICAL_RESOLUTION_REFUSED"
    #: The resolution port answered about a different coordinate, or at a different
    #: instant, than it was asked about.
    RESOLUTION_ANSWERED_ANOTHER_QUESTION = "RESOLUTION_ANSWERED_ANOTHER_QUESTION"
    #: A ``RESOLVED`` answer arrived without the record, without the artifact, or carrying
    #: a record whose coordinate is not the resolved one.
    RESOLUTION_MALFORMED = "RESOLUTION_MALFORMED"
    #: The record's ``coordinate.content_digest`` is not its ``policy_body_digest``. The
    #: Policy Authority enforces this equality at issuance but does **not** re-enforce it
    #: at resolution (ADR residual R-3), so this boundary enforces it itself.
    COORDINATE_DIGEST_UNBOUND = "COORDINATE_DIGEST_UNBOUND"
    #: The candidate this determination accompanies names a **different policy** than the one
    #: that resolved (5B-1). A refusal, not a warning: the two artifacts are handed to a
    #: consumer together, and a proof about policy A beside a candidate about policy B is a
    #: misstatement however genuine each half is on its own.
    CANDIDATE_COORDINATE_MISMATCH = "CANDIDATE_COORDINATE_MISMATCH"

    # --- fail-closed terminals ------------------------------------------------------------
    #: The resolution port could not be used — it raised, or returned a foreign type.
    #: Unavailable is a refusal.
    VERIFICATION_UNAVAILABLE = "VERIFICATION_UNAVAILABLE"
    #: An internal invariant of this package did not hold. A verifier that cannot trust its
    #: own reasoning must not conclude.
    INVARIANT_VIOLATION = "INVARIANT_VIOLATION"
    #: The default arm of every exhaustive match. Unknown fails closed.
    INDETERMINATE = "INDETERMINATE"


#: Every member that is **not** a success. Used to assert, structurally, that the only
#: outcome which can mint a verified artifact is ``VERIFIED``.
REFUSAL_OUTCOMES: Final[frozenset] = frozenset(
    member for member in PolicyAuthenticityOutcome
    if member is not PolicyAuthenticityOutcome.VERIFIED
)

#: The Policy Authority's reasons, mapped one-for-one. Total over ``PolicyResolutionReason``
#: except ``RESOLVED``, which is not a refusal and is deliberately absent: a caller must not
#: be able to reach a success outcome by looking one up in a table.
RESOLUTION_REASON_OUTCOMES: Final[dict] = {
    PolicyResolutionReason.TENANT_SCOPE_MISMATCH: (
        PolicyAuthenticityOutcome.TENANT_SCOPE_MISMATCH
    ),
    PolicyResolutionReason.NOT_FOUND: PolicyAuthenticityOutcome.POLICY_NOT_FOUND,
    PolicyResolutionReason.REFERENCE_MISMATCH: PolicyAuthenticityOutcome.REFERENCE_MISMATCH,
    PolicyResolutionReason.ARTIFACT_REFERENCE_MISMATCH: (
        PolicyAuthenticityOutcome.ARTIFACT_REFERENCE_MISMATCH
    ),
    PolicyResolutionReason.NO_ADAPTER_REGISTERED: (
        PolicyAuthenticityOutcome.NO_ADAPTER_REGISTERED
    ),
    PolicyResolutionReason.ARTIFACT_NOT_CANONICALIZABLE: (
        PolicyAuthenticityOutcome.ARTIFACT_NOT_CANONICALIZABLE
    ),
    PolicyResolutionReason.CONTENT_DIGEST_MISMATCH: (
        PolicyAuthenticityOutcome.CONTENT_DIGEST_MISMATCH
    ),
    PolicyResolutionReason.BODY_DIGEST_MISMATCH: (
        PolicyAuthenticityOutcome.BODY_DIGEST_MISMATCH
    ),
    PolicyResolutionReason.SIGNATURE_INVALID: PolicyAuthenticityOutcome.SIGNATURE_INVALID,
    PolicyResolutionReason.KEY_UNKNOWN: PolicyAuthenticityOutcome.KEY_UNKNOWN,
    PolicyResolutionReason.KEY_REVOKED: PolicyAuthenticityOutcome.KEY_REVOKED,
    PolicyResolutionReason.KEY_NOT_ENTITLED: PolicyAuthenticityOutcome.KEY_NOT_ENTITLED,
    PolicyResolutionReason.APPROVAL_PROOF_INVALID: (
        PolicyAuthenticityOutcome.APPROVAL_PROOF_INVALID
    ),
    PolicyResolutionReason.LIFECYCLE_NOT_ACTIVE: (
        PolicyAuthenticityOutcome.LIFECYCLE_NOT_ACTIVE
    ),
    PolicyResolutionReason.NOT_YET_EFFECTIVE: PolicyAuthenticityOutcome.NOT_YET_EFFECTIVE,
    PolicyResolutionReason.EXPIRED: PolicyAuthenticityOutcome.EXPIRED,
    PolicyResolutionReason.REVOKED: PolicyAuthenticityOutcome.REVOKED,
    PolicyResolutionReason.REVOCATION_INTEGRITY_INVALID: (
        PolicyAuthenticityOutcome.REVOCATION_INTEGRITY_INVALID
    ),
    PolicyResolutionReason.SUPERSESSION_REFERENCE_UNSUPPORTED: (
        PolicyAuthenticityOutcome.SUPERSESSION_REFERENCE_UNSUPPORTED
    ),
}

#: The refusals that depend on the injected ``as_of``. Named as a set because D-5B0B-5's
#: open residual (R-2: whose clock supplies ``as_of``) is exactly the question of who can
#: move an answer between these members and ``VERIFIED``.
TEMPORAL_OUTCOMES: Final[frozenset] = frozenset(
    {
        PolicyAuthenticityOutcome.NOT_YET_EFFECTIVE,
        PolicyAuthenticityOutcome.EXPIRED,
        PolicyAuthenticityOutcome.REVOKED,
        PolicyAuthenticityOutcome.KEY_REVOKED,
        PolicyAuthenticityOutcome.APPROVAL_PROOF_INVALID,
    }
)


def resolution_reason_outcome(reason: object) -> PolicyAuthenticityOutcome:
    """Map one Policy Authority refusal reason onto this vocabulary. Unknown fails closed.

    ``RESOLVED`` is not in the table and never maps to ``VERIFIED``: this function answers
    "which refusal is this", and a success is reached only by passing every gate in
    :mod:`.verification`, not by a lookup.
    """

    if not isinstance(reason, PolicyResolutionReason):
        return PolicyAuthenticityOutcome.INDETERMINATE
    return RESOLUTION_REASON_OUTCOMES.get(reason, PolicyAuthenticityOutcome.INDETERMINATE)
