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
    "BenchmarkTrustRole",
    "BenchmarkTrustAnchorStatus",
    "BenchmarkVerificationOutcome",
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


class BenchmarkTrustRole(str, Enum):
    """The three role-scoped anchor namespaces BR-2C's trust directory serves.

    D-26 rules that publisher, approver and revoker occupy **logically separate
    role-scoped anchor namespaces**. They may share one physical directory
    implementation, but an anchor authorized for one role **never** authorizes
    another automatically — which is why the role is a mandatory parameter of
    the resolution seam and a bound field of every resolved record and every
    verified result, rather than something a caller may leave implicit.

    §8's role-separation matrix names the benchmark-version revoker as a role
    distinct from the publisher, and §17's rule 10 requires the revoking
    authority to be entitled for the exact benchmark scope with the publisher
    never substituted for it. A single namespace would make that substitution
    a configuration accident rather than an unrepresentable state.

    Three members and no fourth. The composition root — D-02's fourth party —
    supplies anchors; it is never a signer, so it has no anchor namespace of
    its own to name here.

    **Naming a role is not occupying one.** Nothing in this package resolves an
    anchor, holds one, or checks that any identity is entitled under any role.
    """

    #: The publisher namespace. Entitles a key to sign a publisher submission
    #: envelope and nothing else.
    PUBLISHER = "PUBLISHER"

    #: The independent approver namespace. D-02 forbids the publisher from
    #: approving its own artifact; separate namespaces are that rule expressed
    #: where the anchors live rather than only where the envelopes are checked.
    APPROVER = "APPROVER"

    #: The revoker namespace. D-26 allocates revoker entitlement to BR-2C
    #: rather than leaving it to the implementer, because ``is_entitled`` was
    #: publisher-scoped in its own signature and D-02's four-party separation
    #: names no revoker.
    REVOKER = "REVOKER"


class BenchmarkTrustAnchorStatus(str, Enum):
    """The lifecycle status a resolved trust-anchor record carries.

    Three members, and deliberately **not** five. D-27 names five conditions a
    refusal must distinguish — not found, revoked, disabled, not yet valid and
    expired — and only two of them are statuses of a record that was found.
    "Not found" is the absence of a record and can never be a field on one;
    "not yet valid" and "expired" are **derived** by comparing the record's own
    validity interval against the explicit trusted instant, so representing
    them here as well would create a second spelling of a fact the interval
    already carries, and the two spellings could disagree.

    D-28 fixes the evaluation order — **revoked, disabled, not yet valid,
    expired** — so a revoked anchor refuses as revoked even when its interval
    has also elapsed. The first two terms of that order are read from this
    enum; the last two from the interval.

    A closed enum rather than a Boolean pair, for D-15's reason: a settable
    ``is_active`` flag is one assignment away from re-enabling a revoked anchor.
    There is no ``ENABLED_WITH_WARNING``, no ``PENDING`` and no ``UNKNOWN``: an
    anchor whose status could not be determined is not an anchor, and D-28's
    fail-closed posture refuses rather than defaulting.

    The in-force member is ``ENABLED`` and deliberately **not** ``ACTIVE``.
    ``ACTIVE`` is a member of
    :data:`BENCHMARK_BANNED_REGISTRATION_STATE_NAMES` — one of the floating
    lifecycle words B-9 keeps out of this package because "possession is not
    validity" — and an anchor status spelling it would put a banned word back
    into the vocabulary through a side door. ``ENABLED`` also pairs correctly
    with :attr:`DISABLED`, which is the distinction the member actually draws.
    """

    #: The anchor is in force, subject to its validity interval being satisfied
    #: at the trusted instant. **Not** a statement that verification succeeded,
    #: and not a claim that anything is currently resolvable.
    ENABLED = "ENABLED"

    #: The anchor was revoked. D-28: revocation **invalidates prior signatures
    #: retroactively**, unlike ordinary key rotation, so a revoked anchor
    #: refuses at every trusted instant and not merely at instants after the
    #: revocation.
    REVOKED = "REVOKED"

    #: The anchor was administratively disabled without being revoked. Distinct
    #: from :attr:`REVOKED` because it carries no retroactive effect: a disabled
    #: anchor stops authorizing new verification without invalidating what it
    #: previously authorized.
    DISABLED = "DISABLED"


class BenchmarkVerificationOutcome(str, Enum):
    """What a verified result reports about **cryptographic verification only**.

    D-24: a verified result establishes cryptographic verification and nothing
    else — **never admission, never registration, never trusted resolution**.
    This enum is therefore deliberately *not*
    :class:`BenchmarkAdmissionOutcome`: reusing ``ADMITTED``/``REJECTED`` would
    spell a verification answer in the admission vocabulary, which is the exact
    confusion D-24's "cryptographic verification ONLY" forbids, and D-01 keeps
    BR-2D the first phase permitted to assert that anything occurred.

    Two members and no third. There is no ``INDETERMINATE`` member here because
    an undetermined verification is a refusal, not an outcome of its own: the
    refusal vocabulary already carries
    :attr:`~.reasons.BenchmarkRegistryRefusalReason.INDETERMINATE` and every
    unknown condition maps there and refuses. A third outcome member would be a
    way for a result to be neither verified nor refused, which fails open.

    **Declaring an outcome is not producing one.** No verifier ships at this
    contract slice, so every value of this enum in this package is one a caller
    wrote down.
    """

    #: The signature verified under the bound profile against the bound anchor
    #: record, evaluated at the bound trusted instant. Carries **no** refusal
    #: reason, and establishes none of §09's five authority facts.
    VERIFIED = "VERIFIED"

    #: Verification refused. Always accompanied by exactly one stable typed
    #: refusal reason from the BR-2 vocabulary saying why — the constructor of
    #: every verified-result type enforces the biconditional, so a refusal with
    #: no reason and a verification with a reason are both unconstructible.
    REFUSED = "REFUSED"
