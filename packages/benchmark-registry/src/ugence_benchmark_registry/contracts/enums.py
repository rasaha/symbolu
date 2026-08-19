"""Enumerations for the benchmark-definition contracts.

Every enum is a ``str``-valued ``Enum`` with UPPERCASE values, matching the
repository convention, so canonical serialization is stable and readable.

None of these enums is a trust grant. Constructing a member is a naming act, not
an authority act — ADR B-5 is explicit that "a caller-provided approval label, a
**lifecycle enum on the artifact**, a reputation score, a publisher **name**, or
a caller-created verification object is **not** approval evidence", and B-9 adds
"possession is not validity; retrieval is not resolution".
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "BenchmarkApplicabilityDeclaration",
    "BenchmarkScopeKind",
    "TemporalBoundDeclaration",
    "BenchmarkLifecycleState",
    "BenchmarkStructuralStatus",
    "BenchmarkSupersessionStatus",
    "BENCHMARK_LIFECYCLE_ORDER",
    "BENCHMARK_TERMINAL_LIFECYCLE_STATES",
]


class BenchmarkApplicabilityDeclaration(str, Enum):
    """Whether an applicability-scoped coordinate applies, stated explicitly.

    ADR §15 rules, for geography (row 6) and domain (row 7), that a coordinate is
    "required where applicability depends on it; explicitly ``NOT_APPLICABLE``
    otherwise — **never omitted**", and adds: "*Geography, domain and intended
    outcome are not cosmetic labels* ... An explicit ``NOT_APPLICABLE`` is a
    decision on the record; an omitted field is not." This enum is that decision,
    made unrepresentable-by-omission.

    There is no ``None`` and no third member: a coordinate must declare one of
    these two, and the declaration is cross-checked against the value it carries.
    The two declarations produce different canonical bytes, so choosing to record
    a coordinate as inapplicable is itself digest-bound.
    """

    #: Applicability depends on this coordinate; an exact non-blank value is
    #: required, because §15 makes a mismatch "a resolution refusal, not an
    #: advisory note".
    APPLICABLE = "APPLICABLE"
    #: Applicability does not depend on this coordinate; the value must be
    #: empty. This is a recorded decision, not an omission.
    NOT_APPLICABLE = "NOT_APPLICABLE"


class BenchmarkScopeKind(str, Enum):
    """How ADR §15 row 5's tenant/scope coordinate is denoted.

    Row 5 is "required (may denote a platform-wide scope explicitly, **never by
    omission**)". A benchmark is therefore either scoped to an exact tenant or
    declared platform-wide *on the record*; there is no third state and no way to
    leave the question open. §27.1's tenant discipline — a tenant is never
    inferred or defaulted — is what makes the distinction load-bearing: §17.6
    requires cross-tenant non-disclosure, and a record whose scope was implicit
    could not be checked against it.

    Declaring ``PLATFORM_WIDE`` is not a grant of platform-wide *trust*. It
    records the intended applicability scope of a definition; whether a caller
    may resolve it is a BR-2 question under §17.6.
    """

    #: Explicitly platform-wide. No tenant is named, and none is implied.
    PLATFORM_WIDE = "PLATFORM_WIDE"
    #: Scoped to exactly one named tenant.
    TENANT = "TENANT"


class TemporalBoundDeclaration(str, Enum):
    """Whether a half-open interval's exclusive end bound exists (ADR §17.9).

    §15 row 15 makes the effective period **required** and §17.9 fixes it as
    half-open ``[effective_from, effective_to)`` with "boundary semantics stated
    once and applied identically everywhere". An open-ended period is a real,
    legitimate thing — but "no end bound" and "an end bound the author forgot"
    must not share one encoding, so the choice is declared rather than inferred
    from a ``None``.

    This is the same discipline :class:`BenchmarkApplicabilityDeclaration`
    applies to geography and domain, applied to time.
    """

    #: The interval has an exclusive end bound, which must be supplied.
    BOUNDED = "BOUNDED"
    #: The interval is open on the right, by decision. No end bound may be
    #: supplied, and its absence is recorded rather than assumed.
    OPEN_ENDED = "OPEN_ENDED"


class BenchmarkStructuralStatus(str, Enum):
    """How much a BR-1 contract actually proves.

    The enum has exactly **one** member because exactly one thing is provable by
    construction. This mirrors, deliberately, the merged
    ``SystemBindingAuthenticityStatus`` whose single ``STRUCTURAL_UNVERIFIED``
    member ADR §14.5 cites as the correct way to be honest about an unverifiable
    artifact, and the merged trusted-evidence contract status that followed it.

    A second member — a registry-resolved status — is deliberately **absent**.
    Admitting one would require the trusted resolution of §17, which is BR-2
    (ADR §30). Adding it later is additive; adding it now would create exactly
    the caller-constructible "RESOLVED" that B-9 exists to prevent consumers from
    trusting.
    """

    #: The contract is internally consistent and digest-bound; admission,
    #: approval verification, publisher verification, registration and trusted
    #: resolution were never performed and are not claimed.
    STRUCTURAL_UNVERIFIED = "STRUCTURAL_UNVERIFIED"


class BenchmarkSupersessionStatus(str, Enum):
    """What a definition records about its own supersession (ADR §15 row 20).

    §15 row 20 requires a "structured supersession / revocation reference"
    "**required where supported**; absent until DD-4 lands, and its absence never
    implies 'not superseded'". §17.12 adds that supersession is expressed "**only**
    through a structured successor reference — no string matching, no version
    ordering, no 'latest' inference", and §17.13 that resolution "fails closed
    when supersession cannot be determined".

    At BR-1 the structured successor reference does **not** exist: its shape,
    successor authorization, activation instant, predecessor invalidation,
    historical resolution across the boundary and cross-tenant/cross-family
    restrictions are all **DD-4**, explicitly deferred. So the one thing a BR-1
    contract may honestly record is that supersession is undetermined — and
    §15 row 20's rule makes recording it *mandatory*, because silence would be
    read as "not superseded".

    ``SUPERSEDED_BY`` is deliberately not a member
    ----------------------------------------------
    A member naming a successor would require the successor reference DD-4
    defers. Writing one from a version string, an ordering or a name would be
    precisely the "guessed supersession" §17.12 calls "an unsigned authority
    decision". The absence of that member is the boundary, and a package test
    asserts no such member appears.
    """

    #: Structured supersession is not representable at this contract version.
    #: **This is not a claim that the version is not superseded** (§15 row 20).
    #: A consumer that needs to know must fail closed (§17.13) until DD-4 lands
    #: and a registry can answer.
    UNDETERMINED = "UNDETERMINED"


class BenchmarkLifecycleState(str, Enum):
    """The lifecycle state a benchmark definition **asserts about itself**.

    The members are the ratified nodes of the benchmark lifecycle drawn in ADR
    §29 — "author benchmark content" → "approve the EXACT digest" → ... →
    "register exact version" — plus §29's terminal "revoke version". §29 states
    that "every stage above is **RATIFIED as design**".

    Carrying a state is never proving one. B-5 lists "a lifecycle enum on the
    artifact" among the things that are **not** approval evidence, and §16.2
    keeps the acts that would establish these states — approval verification
    (stage 3), publisher verification (stage 4), registration (stage 6) — in
    BR-2. A definition that says ``REGISTERED`` has been registered by nobody.

    ``SUPERSEDED`` is deliberately not a member
    -------------------------------------------
    §17.12 admits supersession "**only** through a structured successor
    reference", and that reference is **DD-4**, deferred. A ``SUPERSEDED``
    lifecycle label with no structured successor would be a supersession
    assertion with nothing behind it — the "guessed supersession ... unsigned
    authority decision" §17.12 prohibits. Supersession is recorded instead by
    :class:`BenchmarkSupersessionStatus`, whose only ratified value is
    ``UNDETERMINED``, and it becomes a lifecycle state when DD-4 lands.

    ``EXPIRED`` is deliberately not a member
    ----------------------------------------
    Expiry is a *temporal* question about the declared effective period at a
    caller-supplied instant, and §16.2 stage 5 keeps "state admissible" and
    "effective period well-formed" as two separate checks. Making expiry a state
    would create a second source of truth for the same fact and would require
    something to mutate the state as time passes — a clock-driven mutation, which
    §22.9 forbids outright ("no wall clock inside canonicalization or
    evaluation"). Expiry is answered by
    :meth:`~.identity.BenchmarkEffectivePeriod.temporal_refusal_at`, which takes
    the instant as a parameter.

    ``REVOKED`` **is** a member
    ---------------------------
    §16.2 stage 5 validates that a state is "admissible", which is vacuous
    unless at least one state is not; §19 names a revoked benchmark among the
    things a policy may cite and a resolution must refuse. A revoked version must
    therefore be *representable* in order to be refused. Being representable is
    not being admissible, and this state carries no revoker, no revocation
    reference and no revocation instant — so it can never masquerade as the
    signed, entitled, verified revocation record §17.10/§17.11 require, which is
    BR-2's.
    """

    #: §29 — content authored by a domain owner. Establishes nothing else.
    AUTHORED = "AUTHORED"
    #: §29 — an external governance process approved the **exact digest**.
    #: The artifact says so; §16.2 stage 3 is what would check it, in BR-2.
    APPROVED = "APPROVED"
    #: §29 — registered at its exact coordinate, append-only. The artifact says
    #: so; §16.2 stage 6 is what would perform it, in BR-2.
    REGISTERED = "REGISTERED"
    #: §29 / §19 — revoked. Terminal. A declaration, not a verified revocation.
    REVOKED = "REVOKED"


#: The four lifecycle states in their ratified ADR §29 progression order.
#:
#: This is the canonical ordering for any state sequence in this package, and it
#: is the order the transition relation is drawn in. It is **not** a ranking of
#: trust: ``REGISTERED`` is later than ``APPROVED`` in the progression and proves
#: no more about the artifact than ``AUTHORED`` does.
BENCHMARK_LIFECYCLE_ORDER: tuple = (
    BenchmarkLifecycleState.AUTHORED,
    BenchmarkLifecycleState.APPROVED,
    BenchmarkLifecycleState.REGISTERED,
    BenchmarkLifecycleState.REVOKED,
)

#: The lifecycle states from which no ratified ADR §29 arrow leaves.
#:
#: Exactly ``{REVOKED}``. Nothing leaves it: §17.11's discipline is that
#: revocation is verified *before* denial is applied, so an un-revoke would be an
#: unsigned authority decision. A test derives this set from the transition
#: relation rather than trusting the literal, so the two cannot drift.
#:
#: Which states a *resolution* may admit is deliberately **not** declared here.
#: §16.2 stage 5's admissibility rule belongs to BR-2; BR-1 ships the vocabulary
#: and the one structural refusal it can decide on its own
#: (``BENCHMARK_REVOKED``).
BENCHMARK_TERMINAL_LIFECYCLE_STATES: frozenset = frozenset(
    {BenchmarkLifecycleState.REVOKED}
)
