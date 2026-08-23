"""The BR-2 registry refusal vocabulary — additive, disjoint, BR-1 untouched.

BR-1's seventeen refusal reasons are frozen. §22.13 of the governing ADR sorts
refusals by *declaration index*, so BR-2 **appends and never inserts, renames,
re-values, re-orders or removes**. This module therefore defines a *separate*
enum rather than attempting to extend BR-1's — Python enums cannot be extended
once they have members, and pretending otherwise by re-declaring BR-1's members
here would create two spellings of one vocabulary.

Two vocabularies, provably disjoint
-----------------------------------
:class:`~ugence_benchmark_registry.BenchmarkRefusalReason` (BR-1, seventeen
members, every value prefixed ``BENCHMARK_``) and
:class:`BenchmarkRegistryRefusalReason` (BR-2, twenty-four members, none so
prefixed) share no member and no value, in either direction. There is no alias,
no lookup helper that accepts one and returns the other, and no member of either
that means the same thing as a member of the other.
``tests/contract/test_refusal_vocabulary.py`` proves the disjointness rather
than asserting it in prose.

The composite, and why its prefix comes from the enum
-----------------------------------------------------
:data:`BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS` is the ordered composite: BR-1's
members in **declaration order**, then BR-2's in declaration order.

The BR-1 prefix is taken from ``tuple(BenchmarkRefusalReason)`` — iterating the
*enum class*, which yields declaration order — and explicitly **not** from
``BR1_BENCHMARK_REFUSAL_REASONS``, which is a :class:`frozenset` whose iteration
order is a hash artifact and is not declaration order. A composite built from
the frozenset would look correct, pass a membership assertion, and silently
scramble the ordering §22.13 depends on. The module then asserts
``frozenset(prefix) == BR1_BENCHMARK_REFUSAL_REASONS`` at import time, so the
enum and the frozen set can never drift apart without this package failing to
import at all.

Fail closed
-----------
Every unknown condition maps to :attr:`BenchmarkRegistryRefusalReason.INDETERMINATE`,
whose fault class is :attr:`~.enums.BenchmarkRegistryFaultClass.INDETERMINATE`.
There is no "unknown means allowed" path anywhere in this package, and
:func:`fault_class_for` is total over the enum — a reason with no fault class
would be a condition a consumer could not classify, which is a condition that
fails open.
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType

from ugence_benchmark_registry import (
    BR1_BENCHMARK_REFUSAL_REASONS,
    BenchmarkRefusalReason,
)

from .enums import BenchmarkRegistryFaultClass
from .errors import BenchmarkRegistryContractError

__all__ = [
    "BenchmarkRegistryRefusalReason",
    "BENCHMARK_REGISTRY_REFUSAL_REASONS",
    "BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS",
    "BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES",
    "fault_class_for",
]


class BenchmarkRegistryRefusalReason(str, Enum):
    """Typed BR-2 registry and resolution refusals. Every member is a refusal.

    No member of this enum is a success, a warning, a partial result or a
    "soft" outcome — including :attr:`IDEMPOTENT_DUPLICATE`, which reports that
    **nothing new was registered**. A consumer that receives any member of this
    vocabulary has not obtained a registration and has not obtained a trusted
    resolution.

    Declaration order is load-bearing and append-only: a later milestone adds
    members at the end and never inserts, renames or re-values an existing one.
    """

    # ---------------------------------------------------------------- #
    # Idempotence
    # ---------------------------------------------------------------- #
    #: A byte-identical resubmission arrived at an occupied exact locator. The
    #: existing record and its **original** recorded time are returned
    #: unchanged; nothing is appended, and no new registration occurs. D-06
    #: requires the comparison to be over **canonical bytes**, not digests
    #: alone.
    IDEMPOTENT_DUPLICATE = "IDEMPOTENT_DUPLICATE"

    # ---------------------------------------------------------------- #
    # Coordinate conflict
    # ---------------------------------------------------------------- #
    #: A non-identical submission arrived for an exact locator that is already
    #: occupied, or a second publisher claimed a locator another publisher
    #: holds. Last-writer-wins is prohibited, and so is publisher-partitioned
    #: coordinate squatting: the conflict is typed and the write is refused.
    COORDINATE_SLOT_CONFLICT = "COORDINATE_SLOT_CONFLICT"

    #: A digest already bound to one exact locator arrived under a different
    #: one. This is an aliasing attack — the same content addressed two ways —
    #: and it is refused rather than recorded.
    DIGEST_ALREADY_BOUND = "DIGEST_ALREADY_BOUND"

    #: A submitted locator is visually confusable with an occupied one.
    #: **Rejection only.** See
    #: :data:`~.confusable.BENCHMARK_CONFUSABLE_COMPARISON_CONTRACT` for what is
    #: compared and for the explicit statement that no complete Unicode
    #: confusable algorithm is claimed at this version.
    CONFUSABLE_COORDINATE = "CONFUSABLE_COORDINATE"

    # ---------------------------------------------------------------- #
    # Lifecycle integrity
    # ---------------------------------------------------------------- #
    #: The requested move conflicts with the locator's recorded lifecycle —
    #: most commonly a re-registration attempt after revocation, which is
    #: refused because ``REVOKED`` is terminal.
    LIFECYCLE_CONFLICT = "LIFECYCLE_CONFLICT"

    #: The requested transition is not a member of the closed relation
    #: :data:`~.lifecycle.BENCHMARK_REGISTRATION_TRANSITIONS`, or the payload
    #: offered for it is not the one bound to that transition.
    UNAUTHORIZED_TRANSITION = "UNAUTHORIZED_TRANSITION"

    #: A supersession was requested, inferred, or guessed from version order.
    #: D-10: supersession is out of scope for the whole of BR-2 and **fails
    #: closed**. BR-2 must never infer authority from SemVer ordering; a guessed
    #: supersession is an unsigned authority decision (ADR §17.12).
    UNSUPPORTED_SUPERSESSION = "UNSUPPORTED_SUPERSESSION"

    # ---------------------------------------------------------------- #
    # Store integrity and availability
    # ---------------------------------------------------------------- #
    #: The caller's view of the event chain is behind the registry's — a replay
    #: or a rollback. Refused rather than merged.
    STALE_REGISTRY_SNAPSHOT = "STALE_REGISTRY_SNAPSHOT"

    #: The store holds an equal digest over unequal bytes, or is otherwise
    #: self-inconsistent. Neither admits nor overwrites: an integrity fault is
    #: never resolved by picking a side.
    STORE_INTEGRITY_INVALID = "STORE_INTEGRITY_INVALID"

    #: The store could not be reached. Fails closed — an unreachable registry
    #: resolves nothing, and never falls back to a cached or default answer.
    STORE_UNAVAILABLE = "STORE_UNAVAILABLE"

    # ---------------------------------------------------------------- #
    # Trust and authenticity
    # ---------------------------------------------------------------- #
    #: No trust anchor was configured by the composition root. D-04's seventh
    #: constraint: production startup **fails closed** when a production trust
    #: resolver is absent. The registry never mints an anchor to fill the gap.
    NO_TRUST_ANCHOR_CONFIGURED = "NO_TRUST_ANCHOR_CONFIGURED"

    #: The publisher, or the publisher's key, is not entitled under any
    #: configured anchor.
    PUBLISHER_UNTRUSTED = "PUBLISHER_UNTRUSTED"

    #: A declared signature is absent, malformed, or did not verify. At BR-2A
    #: nothing verifies anything, so this member is defined and produced by
    #: nothing in this package.
    SIGNATURE_INVALID = "SIGNATURE_INVALID"

    #: The independent approval assertion was missing or did not verify. A BR-1
    #: artifact carrying ``lifecycle_state=APPROVED`` never satisfies this: B-5
    #: rules a lifecycle enum on the artifact is not approval evidence.
    APPROVAL_UNVERIFIED = "APPROVAL_UNVERIFIED"

    # ---------------------------------------------------------------- #
    # Read non-disclosure
    # ---------------------------------------------------------------- #
    #: Nothing the caller may see. §17.6 and §27.2 require a genuine miss and a
    #: cross-tenant denial to be **externally indistinguishable** — same code,
    #: same shape, same timing posture — so the registry is not an enumeration
    #: oracle. This is deliberately the same member for both.
    NOT_FOUND = "NOT_FOUND"

    #: The locator exists in the chain but has not reached ``REGISTERED``, so it
    #: is not resolvable. Distinct from :attr:`NOT_FOUND`, and only ever
    #: returned where the caller is already entitled to know the locator exists.
    NOT_ADMITTED = "NOT_ADMITTED"

    # ---------------------------------------------------------------- #
    # Fail-closed catch-all
    # ---------------------------------------------------------------- #
    #: The condition could not be determined. Never "allow"; never "probably
    #: fine". Every unknown condition in BR-2 maps here and refuses.
    INDETERMINATE = "INDETERMINATE"

    # ---------------------------------------------------------------- #
    # Trust-anchor lifecycle (D-27) and trust-state availability (D-28)
    #
    # Seven members appended at the END of the enum rather than inserted into
    # the thematic block above, because §35.6 requires appending and never
    # inserting: BR-2's members occupy composite indices 17..40 and an
    # insertion would silently renumber every member after the insertion
    # point, so a consumer that had recorded an index against §22.13 would
    # find it pointing at a different refusal.
    #
    # All seven are **role-neutral** (D-27). A refusal says an anchor was
    # revoked, not that a *publisher's* anchor was revoked: the role is carried
    # as a bound field of the verified result, so folding it into the refusal
    # name would be a second spelling of a fact already bound, and would
    # multiply five conditions into fifteen members.
    #
    # D-27 also fixes the count at five for the lifecycle conditions and D-28
    # at two for the availability conditions. Folding any condition into an
    # existing member later needs its own ratification rather than being an
    # implementation choice.
    # ---------------------------------------------------------------- #
    #: No anchor record exists for the exact (role, identity, key) triple.
    #: Distinct from :attr:`PUBLISHER_UNTRUSTED`, which D-03 already used for
    #: both an unknown key and a revoked one; D-27 separates them because
    #: collapsing an absent anchor into a revoked one loses the operator's
    #: single most useful distinction. **Role-scoped absence**: an anchor
    #: entitled for another role is *not found* for this one (D-26), never
    #: silently accepted.
    TRUST_ANCHOR_NOT_FOUND = "TRUST_ANCHOR_NOT_FOUND"

    #: The resolved anchor carries
    #: :attr:`~.enums.BenchmarkTrustAnchorStatus.REVOKED`. First in D-28's
    #: evaluation order, and **retroactive**: revocation invalidates prior
    #: signatures at every trusted instant, so this refuses even for an
    #: instant before the revocation. Ordinary key rotation does not.
    TRUST_ANCHOR_REVOKED = "TRUST_ANCHOR_REVOKED"

    #: The resolved anchor carries
    #: :attr:`~.enums.BenchmarkTrustAnchorStatus.DISABLED`. Second in D-28's
    #: order. Carries no retroactive effect, which is exactly why it is not
    #: folded into :attr:`TRUST_ANCHOR_REVOKED`.
    TRUST_ANCHOR_DISABLED = "TRUST_ANCHOR_DISABLED"

    #: The trusted instant precedes the anchor's ``validity_from``. Third in
    #: D-28's order, and derived from the record's interval rather than from
    #: its status.
    TRUST_ANCHOR_NOT_YET_VALID = "TRUST_ANCHOR_NOT_YET_VALID"

    #: The trusted instant is at or after the anchor's ``validity_to`` — the
    #: half-open ``[validity_from, validity_to)`` rule this package applies
    #: everywhere. Last in D-28's order.
    TRUST_ANCHOR_EXPIRED = "TRUST_ANCHOR_EXPIRED"

    #: The trust directory could not be reached. Fails closed on exactly
    #: :attr:`STORE_UNAVAILABLE`'s posture, extended from the store to anchors:
    #: there is **never** a fallback to a cached, default or previously
    #: successful verification (D-28). D-04's seventh constraint covered the
    #: absence of a trust resolver at startup only; this covers it at every
    #: evaluation thereafter.
    TRUST_DIRECTORY_UNAVAILABLE = "TRUST_DIRECTORY_UNAVAILABLE"

    #: The trust state available is older than the evaluation requires. D-21
    #: records that a cached verification answer is indistinguishable from a
    #: fresh one, which is why staleness must refuse rather than be tolerated:
    #: a stale snapshot may predate a revocation, and serving from it is
    #: indistinguishable from ignoring the revocation.
    STALE_TRUST_SNAPSHOT = "STALE_TRUST_SNAPSHOT"


#: Every BR-2 refusal reason, as an unordered set for membership tests.
BENCHMARK_REGISTRY_REFUSAL_REASONS: frozenset = frozenset(
    BenchmarkRegistryRefusalReason
)

# The BR-1 prefix in **declaration order**. Taken from the enum class, never
# from BR1_BENCHMARK_REFUSAL_REASONS, which is a frozenset: iterating a frozenset
# yields hash order, which is neither declaration order nor stable across
# interpreter runs with hash randomization for anything but small int-like keys.
_BR1_PREFIX: tuple = tuple(BenchmarkRefusalReason)

# Fail at import if the two BR-1 spellings ever drift apart. This is not a test
# helper — it runs in the installed wheel, in the source tree and in every
# consumer's process, so a BR-1 upgrade that silently added or dropped a member
# cannot be papered over by regenerating a manifest.
if frozenset(_BR1_PREFIX) != BR1_BENCHMARK_REFUSAL_REASONS:
    raise BenchmarkRegistryContractError(
        "the BR-1 refusal vocabulary reached through BenchmarkRefusalReason "
        "does not equal BR1_BENCHMARK_REFUSAL_REASONS; BR-2 refuses to publish "
        "a composite whose frozen prefix it cannot vouch for"
    )

#: The ordered composite refusal vocabulary: BR-1's seventeen members in
#: declaration order, then BR-2's twenty-four in declaration order.
#:
#: The BR-1 prefix is byte-for-byte BR-1's own order, so a consumer sorting by
#: index against §22.13 gets the same answer from either package. BR-2's members
#: occupy indices 17..40 and never displace a BR-1 index.
BENCHMARK_REGISTRY_ALL_REFUSAL_REASONS: tuple = _BR1_PREFIX + tuple(
    BenchmarkRegistryRefusalReason
)

#: Total classification of every BR-2 refusal into one of the seven fault
#: classes. Total by construction: :func:`fault_class_for` raises rather than
#: guessing, and a package test asserts the mapping covers the enum exactly.
BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES: MappingProxyType = MappingProxyType(
    {
        BenchmarkRegistryRefusalReason.IDEMPOTENT_DUPLICATE: (
            BenchmarkRegistryFaultClass.IDEMPOTENCE
        ),
        BenchmarkRegistryRefusalReason.COORDINATE_SLOT_CONFLICT: (
            BenchmarkRegistryFaultClass.COORDINATE_CONFLICT
        ),
        BenchmarkRegistryRefusalReason.DIGEST_ALREADY_BOUND: (
            BenchmarkRegistryFaultClass.COORDINATE_CONFLICT
        ),
        BenchmarkRegistryRefusalReason.CONFUSABLE_COORDINATE: (
            BenchmarkRegistryFaultClass.COORDINATE_CONFLICT
        ),
        BenchmarkRegistryRefusalReason.LIFECYCLE_CONFLICT: (
            BenchmarkRegistryFaultClass.LIFECYCLE_INTEGRITY
        ),
        BenchmarkRegistryRefusalReason.UNAUTHORIZED_TRANSITION: (
            BenchmarkRegistryFaultClass.LIFECYCLE_INTEGRITY
        ),
        BenchmarkRegistryRefusalReason.UNSUPPORTED_SUPERSESSION: (
            BenchmarkRegistryFaultClass.LIFECYCLE_INTEGRITY
        ),
        BenchmarkRegistryRefusalReason.STALE_REGISTRY_SNAPSHOT: (
            BenchmarkRegistryFaultClass.STORE_INTEGRITY
        ),
        BenchmarkRegistryRefusalReason.STORE_INTEGRITY_INVALID: (
            BenchmarkRegistryFaultClass.STORE_INTEGRITY
        ),
        BenchmarkRegistryRefusalReason.STORE_UNAVAILABLE: (
            BenchmarkRegistryFaultClass.STORE_INTEGRITY
        ),
        BenchmarkRegistryRefusalReason.NO_TRUST_ANCHOR_CONFIGURED: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.PUBLISHER_UNTRUSTED: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.SIGNATURE_INVALID: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.APPROVAL_UNVERIFIED: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.NOT_FOUND: (
            BenchmarkRegistryFaultClass.READ_NON_DISCLOSURE
        ),
        BenchmarkRegistryRefusalReason.NOT_ADMITTED: (
            BenchmarkRegistryFaultClass.READ_NON_DISCLOSURE
        ),
        BenchmarkRegistryRefusalReason.INDETERMINATE: (
            BenchmarkRegistryFaultClass.INDETERMINATE
        ),
        # D-27's five and D-28's two. Every one of the seven is a statement
        # that a key or the trust state behind it could not be trusted, which
        # is TRUST_AND_AUTHENTICITY's own definition; none is a statement about
        # the registry store, whose contents these refusals never consult.
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_FOUND: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_REVOKED: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_DISABLED: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_NOT_YET_VALID: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.TRUST_ANCHOR_EXPIRED: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.TRUST_DIRECTORY_UNAVAILABLE: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
        BenchmarkRegistryRefusalReason.STALE_TRUST_SNAPSHOT: (
            BenchmarkRegistryFaultClass.TRUST_AND_AUTHENTICITY
        ),
    }
)


def fault_class_for(
    reason: BenchmarkRegistryRefusalReason,
) -> BenchmarkRegistryFaultClass:
    """Return the fault class of ``reason``, refusing anything unclassified.

    Pure validation: a total lookup over a frozen mapping, with no default and
    no fallback. An object that is not exactly a
    :class:`BenchmarkRegistryRefusalReason` is refused rather than coerced — a
    bare string that happens to spell a member is not a member, and treating it
    as one would let an unknown condition acquire a class by matching text.
    """

    if type(reason) is not BenchmarkRegistryRefusalReason:
        raise BenchmarkRegistryContractError(
            "fault_class_for expects exactly a BenchmarkRegistryRefusalReason "
            f"(got {type(reason).__name__}); a string spelling of a member is "
            "not a member, and BR-1's separate vocabulary is never classified "
            "by this function"
        )
    classification = BENCHMARK_REGISTRY_REFUSAL_FAULT_CLASSES.get(reason)
    if classification is None:
        raise BenchmarkRegistryContractError(
            f"{reason.value} has no ratified fault class; an unclassified "
            "refusal fails closed rather than being reported as unknown"
        )
    return classification
