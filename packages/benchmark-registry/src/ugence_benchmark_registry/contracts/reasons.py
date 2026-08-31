"""The typed benchmark refusal vocabulary (ADR §16.3, B-7, DD-1).

ADR §16.3 ratifies that failure at any stage of benchmark admission produces
"**a stable typed refusal reason**", and B-7 adds "no trusted registration, no
partial state, no silent fallback". §22.11 requires reason-code namespaces
"scoped per capability, stable across versions, never reused for a different
meaning". The *exact vocabulary* is **DD-1** — "implementation detail; §11/§16.3
ratify that codes must be stable, typed and namespace-scoped, which is the
boundary-relevant part". DD-1 is therefore not an unresolved decision BR-1 must
stop on; it is one the ADR explicitly delegates to this milestone. This module
discharges it for the BR-1 surface, and **only** for the BR-1 surface.

Every member is a **refusal**
-----------------------------
There is no success member, and none can be added without changing this type's
name and documentation. Because the enum is *entirely* refusals, "no reason
code" is the only way to express "nothing was refused" — and that is emphatically
not a positive state either. ADR B-9 is explicit: "possession is not validity;
retrieval is not resolution". Constructing a benchmark contract from this package
is possession.

Namespace
---------
Every member is prefixed ``BENCHMARK_``: neutral, capability-scoped, and free of
milestone branding. There are **no aliases and no deprecated spellings** —
§22.11's "never reused for a different meaning" is violated the moment two
spellings mean one thing.

The vocabulary is deliberately BR-1-sized
-----------------------------------------
Every member below is raised, or returned, by a code path that exists in this
package. BR-1 mints **no** code for a condition only a running registry could
reach, because a code no code path can produce is a promise about behaviour that
does not exist. The ADR assigns each of the following to **BR-2** (§30, §32), and
none of them is minted here:

* registry unavailable, storage failure, lookup failure (§17.14 — retrieval);
* admission denial and the §16.2 six-stage registration ordering (§30 BR-2);
* append-only slot conflict and byte-identical idempotence (B-10, §17.4-5);
* approval-verification failure at a trusted approval boundary (§16.2 stage 3);
* publisher signature, key trust, key revocation (§16.2 stage 4);
* trust-anchor resolution and configuration (§16.1);
* benchmark-version revocation *records* and their verification (§17.10-11);
* cross-tenant non-disclosure outcomes (§17.6);
* lifecycle-state *admissibility* under a resolution policy (§16.2 stage 5) —
  BR-1 ships the one condition it can decide structurally,
  :attr:`BenchmarkRefusalReason.BENCHMARK_REVOKED`, and leaves the admissibility
  *rule* to BR-2;
* successor resolution and supersession enforcement (§17.12-13, DD-4).

No evidence-verification code appears here either: that vocabulary belongs to
the Trusted Evidence Authority (ADR §11), which owns it in its own namespace.
Two capabilities, two namespaces, no shared spelling.
"""

from __future__ import annotations

from enum import Enum

__all__ = [
    "BenchmarkRefusalReason",
    "BENCHMARK_REFUSAL_REASONS",
    "BR1_BENCHMARK_REFUSAL_REASONS",
]


class BenchmarkRefusalReason(str, Enum):
    """Stable typed refusal codes for benchmark-definition contracts.

    Declaration order is the **deterministic reason ordering** required by ADR
    §22.13: any routine that reports several refusals sorts them into this
    order, so a digest taken over a result set is stable. Members are grouped
    presence -> structure -> identity -> exactness -> applicability ->
    measurement -> source -> approval and role separation -> time -> lifecycle
    -> supersession -> resolution-not-performed.
    """

    # -- presence ---------------------------------------------------------- #
    #: §16.2 stage 1 — no benchmark definition was supplied where one is
    #: required. Distinct from a malformed one: nothing arrived at all.
    BENCHMARK_DEFINITION_MISSING = "BENCHMARK_DEFINITION_MISSING"

    # -- structure --------------------------------------------------------- #
    #: §16.2 stage 1 — the contract does not parse into a well-formed shape:
    #: a mistyped, padded, non-NFC, duck-typed or subclassed value.
    BENCHMARK_MALFORMED_CONTRACT = "BENCHMARK_MALFORMED_CONTRACT"
    #: §22.8 — the value cannot be encoded under the declared, versioned
    #: canonicalization rules. Separated from
    #: :attr:`BENCHMARK_MALFORMED_CONTRACT` because "this shape is wrong" and
    #: "these bytes cannot be produced deterministically" are different faults
    #: with different remedies, and §22.8 rules the second a refusal rather than
    #: a best-effort serialization.
    BENCHMARK_CANONICALIZATION_FAILED = "BENCHMARK_CANONICALIZATION_FAILED"

    # -- identity (§15) ----------------------------------------------------- #
    #: §15 — a required benchmark-identity coordinate is absent or blank. §15's
    #: closing rule: "an explicit ``NOT_APPLICABLE`` is a decision on the
    #: record; an omitted field is not".
    BENCHMARK_IDENTITY_COORDINATE_MISSING = "BENCHMARK_IDENTITY_COORDINATE_MISSING"

    # -- exactness (B-8, §17.1, §17.2) -------------------------------------- #
    #: B-8 / §17.2 — the coordinate is not exact: a floating token (``latest``,
    #: ``current``), a wildcard, a version range, or a partial identity. B-8
    #: requires a floating reference to be **unrepresentable**, so this code is
    #: what "unrepresentable" sounds like at the boundary.
    BENCHMARK_COORDINATE_NOT_EXACT = "BENCHMARK_COORDINATE_NOT_EXACT"

    # -- applicability (§15 rows 5-7) --------------------------------------- #
    #: §15 rows 5-7 — an applicability-scoped coordinate contradicts its own
    #: declaration: ``APPLICABLE`` with no value, ``NOT_APPLICABLE`` with one,
    #: a platform-wide scope naming a tenant, or a tenant scope naming none.
    BENCHMARK_APPLICABILITY_INCONSISTENT = "BENCHMARK_APPLICABILITY_INCONSISTENT"

    # -- measurement semantics (§15 rows 8-14) ------------------------------ #
    #: §15 rows 8-14 — the measurement group is incomplete. Every row is
    #: individually required, so a partial group fails closed rather than
    #: yielding a benchmark whose comparison semantics are undefined.
    BENCHMARK_MEASUREMENT_SEMANTICS_INCOMPLETE = (
        "BENCHMARK_MEASUREMENT_SEMANTICS_INCOMPLETE"
    )

    # -- source / provenance requirements (§15 row 16) ---------------------- #
    #: §15 row 16 — the source/provenance requirements are absent, empty,
    #: blank or duplicated. A duplicate is refused, never de-duplicated.
    BENCHMARK_SOURCE_REQUIREMENTS_INVALID = "BENCHMARK_SOURCE_REQUIREMENTS_INVALID"

    # -- approval and role separation (§15 row 17, B-3, B-4, B-5) ----------- #
    #: B-5 / §15 row 17 — the approval reference is malformed, or it binds a
    #: different content digest than the definition it accompanies. "Approval
    #: binds an exact **content digest**, not a name and not an intent."
    BENCHMARK_APPROVAL_REFERENCE_INVALID = "BENCHMARK_APPROVAL_REFERENCE_INVALID"
    #: B-3 / B-4 — one identifier occupies two adjacent roles for the same
    #: benchmark version: the publisher is also the approving authority. "No
    #: component occupies two adjacent roles for the same benchmark version."
    BENCHMARK_ROLE_SEPARATION_VIOLATED = "BENCHMARK_ROLE_SEPARATION_VIOLATED"

    # -- time (§15 row 15, §17.9) ------------------------------------------- #
    #: §15 row 15 / §17.9 — the effective period is not a well-formed half-open
    #: interval: a naive datetime, a reversed or equal ordering, a bounded
    #: declaration with no end, or an open-ended declaration carrying one.
    BENCHMARK_EFFECTIVE_PERIOD_INVALID = "BENCHMARK_EFFECTIVE_PERIOD_INVALID"
    #: §17.9 — the caller-supplied instant precedes ``effective_from``.
    BENCHMARK_NOT_YET_EFFECTIVE = "BENCHMARK_NOT_YET_EFFECTIVE"
    #: §17.9 — the caller-supplied instant is at or past the **exclusive** end
    #: bound of the half-open interval ``[effective_from, effective_to)``, so
    #: ``effective_to`` itself is already outside.
    BENCHMARK_EXPIRED = "BENCHMARK_EXPIRED"

    # -- lifecycle (§29) ---------------------------------------------------- #
    #: §29 — the proposed lifecycle transition is not a ratified arrow.
    BENCHMARK_INVALID_LIFECYCLE_TRANSITION = "BENCHMARK_INVALID_LIFECYCLE_TRANSITION"
    #: §29 / §19 — the definition declares itself revoked. A **declaration**,
    #: not a verified revocation: B-5 rules that a lifecycle enum carried on the
    #: artifact is not evidence, and §17.11 requires a revocation record to be
    #: signed, entitled and verified before denial is applied. That verification
    #: is BR-2's; refusing an artifact that says so about itself is BR-1's.
    BENCHMARK_REVOKED = "BENCHMARK_REVOKED"

    # -- supersession (§15 row 20, §17.12, §17.13, DD-4) -------------------- #
    #: §17.12 — the supersession declaration is not one BR-1 can represent. The
    #: structured successor reference is **DD-4**; until it lands, the only
    #: ratified declaration is that supersession is undetermined, and §15 row 20
    #: rules that this "never implies 'not superseded'".
    BENCHMARK_SUPERSESSION_DECLARATION_INVALID = (
        "BENCHMARK_SUPERSESSION_DECLARATION_INVALID"
    )

    # -- resolution unavailable (never a pass) ------------------------------ #
    #: B-9 / §17.14 — a consumer required **trusted resolution** and none was
    #: performed. This is the code for the ordinary BR-1 situation: contracts
    #: exist, no registry does. "Raw retrieval and trusted resolution are
    #: different operations with different return types", and BR-1 performs
    #: neither. A consumer that requires a resolved benchmark refuses on this.
    BENCHMARK_RESOLUTION_NOT_PERFORMED = "BENCHMARK_RESOLUTION_NOT_PERFORMED"


#: The refusal codes BR-1 ratifies and ships, frozen for backward compatibility.
#:
#: A later milestone may **append** to :class:`BenchmarkRefusalReason` — BR-2 has
#: a substantial ratified surface of its own (§30, §32) — but it may not rename,
#: re-value, re-order or remove any member of this set. §22.13's deterministic
#: reason ordering sorts by declaration index, so inserting a member among these
#: would silently re-order a previously-issued refusal sequence.
BR1_BENCHMARK_REFUSAL_REASONS: frozenset = frozenset(
    {
        BenchmarkRefusalReason.BENCHMARK_DEFINITION_MISSING,
        BenchmarkRefusalReason.BENCHMARK_MALFORMED_CONTRACT,
        BenchmarkRefusalReason.BENCHMARK_CANONICALIZATION_FAILED,
        BenchmarkRefusalReason.BENCHMARK_IDENTITY_COORDINATE_MISSING,
        BenchmarkRefusalReason.BENCHMARK_COORDINATE_NOT_EXACT,
        BenchmarkRefusalReason.BENCHMARK_APPLICABILITY_INCONSISTENT,
        BenchmarkRefusalReason.BENCHMARK_MEASUREMENT_SEMANTICS_INCOMPLETE,
        BenchmarkRefusalReason.BENCHMARK_SOURCE_REQUIREMENTS_INVALID,
        BenchmarkRefusalReason.BENCHMARK_APPROVAL_REFERENCE_INVALID,
        BenchmarkRefusalReason.BENCHMARK_ROLE_SEPARATION_VIOLATED,
        BenchmarkRefusalReason.BENCHMARK_EFFECTIVE_PERIOD_INVALID,
        BenchmarkRefusalReason.BENCHMARK_NOT_YET_EFFECTIVE,
        BenchmarkRefusalReason.BENCHMARK_EXPIRED,
        BenchmarkRefusalReason.BENCHMARK_INVALID_LIFECYCLE_TRANSITION,
        BenchmarkRefusalReason.BENCHMARK_REVOKED,
        BenchmarkRefusalReason.BENCHMARK_SUPERSESSION_DECLARATION_INVALID,
        BenchmarkRefusalReason.BENCHMARK_RESOLUTION_NOT_PERFORMED,
    }
)

#: Every member of :class:`BenchmarkRefusalReason`, as an immutable set.
#:
#: The equality ``BENCHMARK_REFUSAL_REASONS == set(BenchmarkRefusalReason)`` is
#: asserted by the package tests. It is the structural statement that the
#: vocabulary contains **no success state**: there is nothing to add a member to
#: except the refusal set. At BR-1 it is also equal to
#: :data:`BR1_BENCHMARK_REFUSAL_REASONS`, and a test pins that too — so the day
#: BR-2 appends, the two constants diverge visibly rather than silently.
BENCHMARK_REFUSAL_REASONS: frozenset = frozenset(BenchmarkRefusalReason)
