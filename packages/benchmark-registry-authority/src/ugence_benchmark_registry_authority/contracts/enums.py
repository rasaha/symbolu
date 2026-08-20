"""Closed vocabularies for the BR-2 registry authority.

Every enum here is a ``str``-valued :class:`~enum.Enum` with UPPERCASE values,
matching the repository convention and the frozen BR-1 layer, so canonical
serialization is stable and readable.

**None of these enums is a trust grant.** Constructing a member is a naming act,
not an authority act. The frozen BR-1 layer already rules this for its own
lifecycle enum — ADR B-5: "a caller-provided approval label, a *lifecycle enum
on the artifact*, a reputation score, a publisher *name*, or a caller-created
verification object is **not** approval evidence" — and B-9 adds "possession is
not validity; retrieval is not resolution". The same rule governs every member
below, including :class:`BenchmarkRegistrationState`: a payload that says
``REGISTERED`` has been registered by nobody at BR-2A.

Two lifecycles, never merged
----------------------------
:class:`BenchmarkRegistrationState` is the **registry's** administrative
lifecycle: an observed, appended fact about what the registry did. It is a
*different vocabulary* from BR-1's
:class:`~ugence_benchmark_registry.BenchmarkLifecycleState`, which is the
**artifact author's** self-declaration and is frozen inside BR-1's identity
digest.

The two share three spellings — ``APPROVED``/``REGISTERED``/``REVOKED`` overlap
partially — and that overlap is exactly why no automatic bridge exists. There is
no conversion helper, no field-name equality and no enum-value equality that
turns one into the other, in either direction, and
``tests/contract/test_two_lifecycle_authorities.py`` asserts the absence of any
such helper. A BR-1 artifact declaring ``lifecycle_state=REGISTERED`` has been
registered by nobody; a BR-2 payload declaring
``BenchmarkRegistrationState.REGISTERED`` at BR-2A was appended by nobody.

Banned state names
------------------
D-08 rules that **no state named** ``ACTIVE``, ``PUBLISHED``, ``CURRENT``,
``DEFAULT``, ``SUSPENDED`` or ``DEPRECATED`` may be introduced. ``ACTIVE`` is one
rename away from ``latest``, and BR-1 exists to make ``latest`` unrepresentable;
``SUSPENDED`` and ``DEPRECATED`` would each imply a reversible denial, which a
later unsigned assertion could lift. A name-ban test asserts their absence across
every enum, every class name and every exported symbol in this package.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "BenchmarkRegistrationState",
    "BenchmarkAdmissionOutcome",
    "BenchmarkSignatureProfile",
    "BenchmarkRegistryFaultClass",
    "BenchmarkRegistryConsistencyScope",
    "BenchmarkRegistryConsistencyClaim",
    "BenchmarkConfusableNormalizationPosture",
    "BenchmarkRegistrationRecordPresence",
    "BENCHMARK_REGISTRATION_STATE_ORDER",
    "BENCHMARK_TERMINAL_REGISTRATION_STATES",
    "BENCHMARK_BANNED_REGISTRATION_STATE_NAMES",
]


class BenchmarkRegistrationState(str, Enum):
    """The **registry's** administrative state for one exact benchmark locator.

    Exactly five members, ratified as D-08. This is the registry's own
    observation of what it did, appended as events and never edited; it is not,
    and never becomes, the artifact's embedded self-declaration.

    At BR-2A no member is ever *established* — every payload carrying one
    permanently derives that registry admission and trusted resolution are not
    established. The vocabulary exists so that BR-2D's admission path has a
    ratified relation to move through, not so that a caller can assert a
    position in it.
    """

    #: A publisher-signed submission envelope has been received and recorded.
    #: Nothing about it has been verified.
    SUBMITTED = "SUBMITTED"

    #: Every admission prerequisite passed, in the fixed order, and the registry
    #: appended an admission decision. Not yet resolvable.
    ADMITTED = "ADMITTED"

    #: The exact locator slot has been claimed and the artifact is resolvable —
    #: the **only** state after which trusted resolution can succeed at all, and
    #: then only under a real verifier that does not exist before BR-2C.
    REGISTERED = "REGISTERED"

    #: Terminal. A revocation whose signed record verified under an entitled
    #: anchor was appended. Under ``DENY_ALWAYS`` (D-09) a revoked artifact never
    #: resolves as admissible again, at any instant, regardless of any
    #: caller-supplied ``as_of``.
    REVOKED = "REVOKED"

    #: Terminal. An admission prerequisite failed, or an admitted artifact was
    #: rejected before any registration record was appended. Never reversible:
    #: a reversible denial is one an unsigned assertion could lift.
    REJECTED = "REJECTED"


class BenchmarkAdmissionOutcome(str, Enum):
    """What an admission decision **declares**, before anything verified it.

    Exactly two members, because :class:`.chain.BenchmarkAdmissionDecisionPayload`
    represents exactly two transitions: ``SUBMITTED → ADMITTED`` and
    ``SUBMITTED → REJECTED``. It may not represent ``ADMITTED → REJECTED`` —
    that transition has its own payload type,
    :class:`.chain.BenchmarkPostAdmissionRejectionEventPayload`, because its
    predecessor state and predecessor payload type are different.

    There is deliberately no ``PENDING``, ``INDETERMINATE`` or ``DEFERRED``
    member. A decision that has not been made is not a decision, and a payload
    representing one would be a lifecycle position nothing appended.
    """

    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"


class BenchmarkSignatureProfile(str, Enum):
    """The closed set of signature profiles a BR-2 envelope may declare.

    A **closed enum, never an unconstrained algorithm string** (§11). An
    attacker-chosen algorithm name is the classic downgrade vector: a verifier
    that reads the algorithm out of the artifact it is about to verify has
    already lost. Restricting the declaration to a ratified member means BR-2C's
    verifier selects its implementation from a fixed table, and an unknown
    profile is unrepresentable rather than unrecognized.

    Exactly one member ships, because exactly one profile is ratified. A second
    member reserved "for later" would be a byte space a future milestone would
    have to either honour or break, which §05 prohibits.

    **Declaring a profile is not using one.** BR-2A performs no signing, no
    verification and no key parsing, and ships no cryptographic dependency.
    """

    #: Ed25519 (RFC 8032) over the SHA-512-based EdDSA construction, applied to
    #: the framed signing input described in
    #: :mod:`~ugence_benchmark_registry_authority.contracts.envelopes`. The
    #: detached signature is carried as exactly 128 lowercase hex characters —
    #: 64 bytes — because canonicalization refuses ``bytes`` outright and one
    #: value must have exactly one spelling.
    ED25519_SHA512_V1 = "ED25519_SHA512_V1"


class BenchmarkRegistryFaultClass(str, Enum):
    """The seven fault classes BR-2 keeps distinguishable in the type system.

    §16 requires the classes to be distinguishable *in types*, not merely in
    prose, so a consumer can branch on the kind of failure without string
    matching a refusal name. Every member of
    :class:`~.reasons.BenchmarkRegistryRefusalReason` maps to exactly one class,
    and the mapping is total — a reason with no class would be a condition that
    fails open.
    """

    #: A byte-identical resubmission at an occupied locator: not an error, but
    #: not a new registration either.
    IDEMPOTENCE = "IDEMPOTENCE"

    #: Two different things claim one exact locator, or one digest claims two.
    COORDINATE_CONFLICT = "COORDINATE_CONFLICT"

    #: The requested move is not in the closed transition relation, or its
    #: predecessor is terminal.
    LIFECYCLE_INTEGRITY = "LIFECYCLE_INTEGRITY"

    #: The store's own contents are inconsistent, stale, or unreachable.
    STORE_INTEGRITY = "STORE_INTEGRITY"

    #: A publisher, key, signature or approval could not be trusted. This is the
    #: class BR-2C's verifier will attach once real verification exists; until
    #: supplies an audited verifier.
    TRUST_AND_AUTHENTICITY = "TRUST_AND_AUTHENTICITY"

    #: A read produced nothing the caller may see. §17.6's cross-tenant
    #: non-disclosure makes a genuine miss and a denial externally
    #: indistinguishable, so both land here.
    READ_NON_DISCLOSURE = "READ_NON_DISCLOSURE"

    #: The condition could not be determined. Fails closed by construction:
    #: nothing resolves, nothing is admitted.
    INDETERMINATE = "INDETERMINATE"


class BenchmarkRegistryConsistencyScope(str, Enum):
    """The consistency scope a BR-2 store adapter may declare (D-15).

    Exactly one member, because BR-2 claims exactly one thing. There is no
    ``DURABLE``, ``DISTRIBUTED`` or ``PRODUCTION`` member, and adding one is not
    a configuration change a deployment can make — it is a new ratified member
    that does not exist. This is what replaces revision 1's retired
    ``is_production_grade`` Boolean: **there is no flag to set, because there is
    no flag.**
    """

    #: Process-local atomicity and read-after-write behaviour, and nothing more.
    PROCESS_LOCAL_ONLY = "PROCESS_LOCAL_ONLY"


class BenchmarkRegistryConsistencyClaim(str, Enum):
    """Whether one named consistency guarantee is claimed or disclaimed.

    Two members and no third: a guarantee is either claimed within the declared
    scope or **explicitly disclaimed**. There is no "unknown", because an
    unknown guarantee is one a caller would have to assume, and D-15 rules that
    an unavailable guarantee must be stated rather than left open.

    A caller cannot flip a disclaimer into a claim: the descriptor that carries
    these derives every one of them from its
    :class:`BenchmarkRegistryConsistencyScope`, so no assignment path exists.
    """

    CLAIMED_WITHIN_DECLARED_SCOPE = "CLAIMED_WITHIN_DECLARED_SCOPE"
    EXPLICITLY_DISCLAIMED = "EXPLICITLY_DISCLAIMED"


class BenchmarkConfusableNormalizationPosture(str, Enum):
    """What the confusable-coordinate contract does about normalization (D-06).

    Exactly one member. D-06 as ratified **prohibits normalization outright**:
    the canonical locator and the stored bytes are never casefolded, never
    NFKC-normalized and never otherwise rewritten — only compared and refused.
    Normalizing would map two structurally different locators onto one, which is
    the same failure BR-1's reject-don't-normalize Unicode posture exists to
    prevent.
    """

    EXPLICITLY_PROHIBITED = "EXPLICITLY_PROHIBITED"


#: Declaration order of :class:`BenchmarkRegistrationState`, pinned as a tuple.
#: Order is documentation, **not** authority: being later in this tuple grants a
#: state nothing, and no code in this package infers a transition from position.
#: The only authority on which moves exist is
#: :data:`~.lifecycle.BENCHMARK_REGISTRATION_TRANSITIONS`.
BENCHMARK_REGISTRATION_STATE_ORDER: tuple = tuple(BenchmarkRegistrationState)

#: The two terminal states. A terminal state's admissible-successor set is
#: **empty rather than missing**, so a relation lookup never raises — BR-1's
#: pattern, reproduced rather than re-derived.
BENCHMARK_TERMINAL_REGISTRATION_STATES: frozenset = frozenset(
    {
        BenchmarkRegistrationState.REVOKED,
        BenchmarkRegistrationState.REJECTED,
    }
)

#: The state names D-08 permanently bans, pinned so the ban is machine-checkable
#: rather than a comment. ``tests/contract/test_two_lifecycle_authorities.py``
#: asserts that no
#: enum member, no class, and no exported symbol in this package carries any of
#: them.
BENCHMARK_BANNED_REGISTRATION_STATE_NAMES: frozenset = frozenset(
    {
        "ACTIVE",
        "PUBLISHED",
        "CURRENT",
        "DEFAULT",
        "SUSPENDED",
        "DEPRECATED",
    }
)


class BenchmarkRegistrationRecordPresence(str, Enum):
    """Whether a registration record has been appended, as a caller asserts it.

    Two members and no third. This gates the one arrow the closed transition
    relation cannot express on its own: ``ADMITTED → REJECTED`` is permitted
    **only while no registration record has been appended**, which is a fact
    about the log rather than about the state pair.

    A closed enum rather than a Boolean, for D-15's reason. An
    ``is_registered`` flag would be one assignment away from turning a refused
    rejection into a permitted one, and the point of the gate is that it cannot
    be flipped. It is also an *assertion* in both members: BR-2B holds no log,
    so ``NO_RECORD_APPENDED`` is what a caller claims, never what BR-2B
    observed.
    """

    #: The caller asserts no registration record exists for this locator.
    NO_RECORD_APPENDED = "NO_RECORD_APPENDED"

    #: The caller asserts a registration record has been appended. This closes
    #: the ``ADMITTED → REJECTED`` arrow permanently for that locator.
    RECORD_APPENDED = "RECORD_APPENDED"
