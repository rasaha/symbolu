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
    #: A verified supersession applies: a successor was issued over this version, which
    #: therefore no longer resolves. Distinct from ``REVOKED`` — the version is replaced,
    #: not withdrawn — and kept a separate member because the mapping is injective.
    POLICY_SUPERSEDED = "POLICY_SUPERSEDED"
    #: A supersession record targeting this version exists but does not itself verify. On
    #: ``REVOCATION_INTEGRITY_INVALID``'s exact precedent: neither honoured nor ignored.
    SUPERSESSION_INTEGRITY_INVALID = "SUPERSESSION_INTEGRITY_INVALID"

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
    #: The candidate names *this* policy, and the policy belongs to another tenant (R-9,
    #: 5B-2). Distinct from the mismatch above on purpose: there, the two artifacts are
    #: about different policies; here they agree about the policy and the disagreement is
    #: over whose action it may bound. Only ``TENANT``-scoped policies can trip it — a
    #: ``GLOBAL`` policy carries the empty tenant and bounds any tenant's action.
    CANDIDATE_CROSS_TENANT_POLICY = "CANDIDATE_CROSS_TENANT_POLICY"

    # --- the candidate must be valid AT the verified instant (R-2, 5B-2) -----------------
    #: Four members rather than one, because "the pair is stale" is four different facts and
    #: a reader triaging a refusal needs to know which. ``as_of`` is the authoritative
    #: verification instant injected by the composition root; this package still reads no
    #: clock. What these add is that the instant is now reconciled against the candidate's own
    #: carried validity rather than merely recorded beside it.
    #:
    #: The boundaries are inclusive on both ends, matching the seam that already enforces the
    #: same interval upstream (``cloud-scaling-risk-integration``'s ``_require_within_validity``
    #: and Risk Authority's ``now > expires_at``), so the three do not disagree about which
    #: instants are admissible.
    #: ``as_of`` precedes ``subject_valid_from_fact`` — the recommendation is not yet valid.
    CANDIDATE_RECOMMENDATION_NOT_YET_VALID = "CANDIDATE_RECOMMENDATION_NOT_YET_VALID"
    #: ``as_of`` is past ``subject_valid_until_fact`` — the recommendation has expired.
    CANDIDATE_RECOMMENDATION_EXPIRED = "CANDIDATE_RECOMMENDATION_EXPIRED"
    #: ``as_of`` is past ``decision_expires_at_fact`` — the Risk Authority decision has
    #: expired. Independent of the recommendation window: a live recommendation can carry a
    #: dead decision.
    CANDIDATE_DECISION_EXPIRED = "CANDIDATE_DECISION_EXPIRED"
    #: ``as_of`` precedes an instant the candidate asserts already happened — the subject
    #: assertion, the decision evaluation, or the attestation issuance. A determination
    #: cannot be about a moment before the evidence it rests on came into being.
    CANDIDATE_FACT_NOT_YET_OCCURRED = "CANDIDATE_FACT_NOT_YET_OCCURRED"
    #: One of the candidate's six carried instants is not exactly a ``datetime``. Phase 5A
    #: admits them exactly at construction, but this boundary accepts a candidate object it
    #: did not build, and ``object.__new__`` and ``pickle`` both bypass ``__post_init__``.
    #: A ``datetime`` subclass overriding the comparison operators satisfies every window
    #: below by fiat, with ``candidate_digest`` unmoved because the canonical rendering of a
    #: subclass is byte-identical to the plain value's. The type is the only place the
    #: difference survives, so it is re-checked here rather than inherited.
    CANDIDATE_FACT_NOT_EXACT_INSTANT = "CANDIDATE_FACT_NOT_EXACT_INSTANT"

    # --- the resolved projection, and the bounds it authenticates (R-8, 5B-3) ------------
    #: The resolution carried no descriptor projection, so the body digest could not be
    #: reproduced here. Refused rather than skipped: ``policy_body_digest`` is a one-way
    #: hash, and without the projection this package has nothing to check it against — which
    #: is exactly the condition that kept ``policy_type`` in the recorded half. A port that
    #: omits the projection is a port whose answer cannot be independently reproduced, and
    #: "cannot reproduce" is a refusal, never a downgrade to carrying the fact unchecked.
    POLICY_PROJECTION_ABSENT = "POLICY_PROJECTION_ABSENT"
    #: The projection was present and did **not** reproduce ``record.policy_body_digest``
    #: when reframed through the Policy Authority's own ``framed_body_digest``. Either the
    #: projection, the adapter id or the policy type is not what the signature covered.
    POLICY_PROJECTION_DIGEST_MISMATCH = "POLICY_PROJECTION_DIGEST_MISMATCH"
    #: The projection reproduced the digest, and the capacity bounds inside it are not the
    #: shape this profile knows how to carry. A digest match proves the bytes are the signed
    #: ones; it does not make an unreadable structure readable, and a bound this routine
    #: cannot state exactly is not one it will attest.
    POLICY_BOUNDS_MALFORMED = "POLICY_BOUNDS_MALFORMED"

    # --- the candidate reconciled against those bounds (R-8 reconciliation) -------------
    #: A candidate accompanied the request and the resolved policy states no capacity bound
    #: at all — it is not a capacity-bounds policy. Refused, never ``VERIFIED``: an artifact
    #: that says a candidate was checked against a bound must not be mintable when no bound
    #: existed to check it against. ``capacity_bounds_fact=None`` remains a legitimate
    #: determination *without* a candidate; it is the pairing that is refused.
    CANDIDATE_POLICY_STATES_NO_BOUNDS = "CANDIDATE_POLICY_STATES_NO_BOUNDS"
    #: The policy states bounds and none of them is for this candidate's
    #: ``(action_type, resource_class)``. Selector matching is exact and fail-closed: no
    #: wildcard, no normalization, and no treating an unspecified selector as "any". A miss
    #: means this policy does not bound this action, which is a refusal rather than a
    #: determination carrying somebody else's ceiling.
    CANDIDATE_BOUND_SELECTOR_MISS = "CANDIDATE_BOUND_SELECTOR_MISS"
    #: More than one authenticated bound matches the selector exactly. Which ceiling applies
    #: is then not determined by the policy body, and a verifier that picked one would be
    #: inventing the answer. Refused.
    CANDIDATE_BOUND_SELECTOR_AMBIGUOUS = "CANDIDATE_BOUND_SELECTOR_AMBIGUOUS"
    #: The selected authenticated bound is narrower than what the candidate carries or asks
    #: for. A candidate may bound itself more tightly than the policy does; it may never
    #: bound itself more loosely, and the request itself is compared against the
    #: authenticated ceiling as well as the candidate's own copy of it.
    CANDIDATE_BOUND_EXCEEDED = "CANDIDATE_BOUND_EXCEEDED"

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
    PolicyResolutionReason.SUPERSEDED: PolicyAuthenticityOutcome.POLICY_SUPERSEDED,
    PolicyResolutionReason.SUPERSESSION_INTEGRITY_INVALID: (
        PolicyAuthenticityOutcome.SUPERSESSION_INTEGRITY_INVALID
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
