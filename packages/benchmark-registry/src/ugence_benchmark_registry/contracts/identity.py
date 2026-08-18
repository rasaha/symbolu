"""Canonical benchmark-definition identity and coordinates (ADR §15, B-8).

The question these contracts answer is *which exact benchmark definition is
this* — and nothing else. They answer it precisely enough that a definition
favourable under one tenant, geography, domain, metric, unit, population,
aggregation, observation window or effective period is **mechanically detectable
when replayed under another**, because every one of ADR §15's twenty coordinates
participates in :meth:`CanonicalBenchmarkDefinitionIdentity.canonical_digest`.

What a canonical benchmark identity proves
------------------------------------------
Exactly one thing: **internal consistency and digest-bound identity.** ADR B-9 is
the governing rule — "possession is not validity; retrieval is not resolution" —
and constructing one of these objects is possession.

What it does **not** prove
--------------------------
Every stage of ADR §16.2 except the first, and every property §17 attaches to a
trusted resolution:

* that the declared **content digest** equals the digest of any actual benchmark
  content (§16.2 stage 2) — this package never holds the content;
* that the **approval** it names exists, was issued by an entitled approver, or
  was verified at a configured trusted approval boundary (§16.2 stage 3, B-5);
* that the **publisher** is authorized, that any signature exists, or that any
  key is trusted, unexpired and unrevoked (§16.2 stage 4, §16.1);
* that its **lifecycle state** is admissible or that the state it declares was
  ever reached (§16.2 stage 5, B-5 — "a lifecycle enum on the artifact ... is
  **not** approval evidence");
* that it was ever **registered**, at this or any coordinate (§16.2 stage 6);
* that it **resolves**, is unrevoked, is unsuperseded, or is disclosable to the
  caller's tenant (§17.6, §17.10-13).

:attr:`CanonicalBenchmarkDefinitionIdentity.structural_status` is accordingly a
permanently ``STRUCTURAL_UNVERIFIED`` **property**, not a field: there is no
constructor argument, assignment or subclass hook that can raise it. Raising it
requires a registry, trust anchors, an approval boundary and a resolver —
**BR-2** (ADR §30).

A definition is not its content, and not a result
-------------------------------------------------
ADR §18 separates four artifacts and rules that "no renaming promotes one into
another": a **benchmark definition** (owned here), an **observed measurement**
(owned by measurement systems, its evidence verified by the Trusted Evidence
Authority), a **benchmark comparison result** (owned by the consuming evaluation
engine) and a **policy decision** (owned by the Policy Authority). This package
carries the *identity of a definition*. It carries no measured value, no
comparison, no threshold verdict, no readiness determination and no monetary
figure, and B-12 is categorical: "the Registry computes nothing".

It does not carry the benchmark's **content** either. The content is authored by
domain owners (§7.2 row 1) and is named here only by its digest (§15 row 4), so
there is nothing in this package a caller could mistake for the benchmark itself.

The twenty coordinates of ADR §15
---------------------------------
Every row is represented explicitly. None is optional, none has an implicit
default, and none can be written into a free-form dictionary — the canonical
encoder refuses mappings outright, so an "extension bag" is not expressible.

===  =========================================  =========================================
Row  ADR §15 coordinate                         Where it lives
===  =========================================  =========================================
1    Benchmark id                               ``coordinate.benchmark_id``
2    Family / type                              ``coordinate.benchmark_family``
3    Semantic version                           ``coordinate.benchmark_version``
4    Content digest                             ``content_digest``
5    Tenant / scope                             ``coordinate.scope``
6    Geography                                  ``coordinate.geography``
7    Domain                                     ``coordinate.domain``
8    Intended outcome / metric purpose          ``measurement.intended_outcome_ref``
9    Metric identity                            ``measurement.metric_ref``
10   Unit                                       ``measurement.unit``
11   Measurement protocol / reference           ``measurement.measurement_protocol_ref``
12   Population / cohort                        ``measurement.population_ref``
13   Aggregation semantics                      ``measurement.aggregation_semantics_ref``
14   Observation window                         ``measurement.observation_window_ref``
15   Effective period                           ``effective_period``
16   Source / provenance requirements           ``source_requirements``
17   Approval reference                         ``approval``
18   Publisher identity                         ``publisher_id``
19   Lifecycle state                            ``lifecycle_state``
20   Structured supersession / revocation ref   ``supersession``
===  =========================================  =========================================

:data:`BENCHMARK_IDENTITY_COORDINATES` is the machine-readable form of that
table, and the package tests walk it — and every leaf beneath it — to prove each
coordinate is in the canonical body and independently changes the digest.

Why geography and domain are declared rather than omitted
---------------------------------------------------------
ADR §15 rows 6-7 are "required where applicability depends on it; explicitly
``NOT_APPLICABLE`` otherwise — **never omitted**", and §15 closes with
"*Geography, domain and intended outcome are not cosmetic labels* ... An explicit
``NOT_APPLICABLE`` is a decision on the record; an omitted field is not." They
are therefore carried as mandatory
:class:`BenchmarkApplicabilityCoordinate` values, which make omission
unrepresentable. Row 8 — intended outcome — is required unconditionally by §15
and so is a plain mandatory coordinate, not an applicability-declared one.

Why so many coordinates are opaque tokens
-----------------------------------------
No unit vocabulary, metric registry, population taxonomy, aggregation grammar,
observation-window grammar, geography code list or domain code list is ratified
anywhere in the ADR, so **none is invented here**. Each is carried as a required,
exact, digest-bound token — the discipline the merged ``AssessedSystemBinding``
applies to ``deployment_environment_ref`` ("no environment enumeration is
ratified anywhere in the repository, so none is invented"). Once one is ratified,
the token points at it with no shape change here.

No competing types are defined
------------------------------
``BenchmarkReference`` is **not** defined here. It is already merged in
``ugence-governance-contracts``, and ADR §6.3 assigns it exactly: it is "the
reference *type*; this ADR owns the **values** it points at". Defining a second
one would be the duplicate contract §22's placement rule exists to prevent. No
``AssessedSystemBinding``, ``SystemManifest`` or ``SubjectContext`` is defined
either (§14, DD-11).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from ._validation import (
    normalize_unordered_reference_tuple,
    require_aware_datetime,
    require_canonical_str,
    require_digest,
    require_exact_coordinate_token,
    require_exact_semantic_version,
    require_exact_type,
    require_optional_aware_datetime,
    require_strictly_before,
)
from .canonical import canonical_bytes, canonical_digest
from .enums import (
    BenchmarkApplicabilityDeclaration,
    BenchmarkLifecycleState,
    BenchmarkScopeKind,
    BenchmarkStructuralStatus,
    BenchmarkSupersessionStatus,
    TemporalBoundDeclaration,
)
from .errors import BenchmarkContractError
from .reasons import BenchmarkRefusalReason

__all__ = [
    "BenchmarkApplicabilityCoordinate",
    "BenchmarkScope",
    "BenchmarkCoordinate",
    "BenchmarkMeasurementSemantics",
    "BenchmarkEffectivePeriod",
    "BenchmarkSourceRequirements",
    "BenchmarkApprovalReference",
    "BenchmarkSupersessionDeclaration",
    "CanonicalBenchmarkDefinitionIdentity",
    "BENCHMARK_IDENTITY_COORDINATES",
]

_R = BenchmarkRefusalReason


def _fail(message: str, reason: BenchmarkRefusalReason) -> BenchmarkContractError:
    error = BenchmarkContractError(message)
    error.reason = reason
    return error


# --------------------------------------------------------------------------- #
# Applicability (ADR §15 rows 6-7)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BenchmarkApplicabilityCoordinate:
    """A coordinate that is either applicable with a value, or explicitly not.

    ADR §15's ruling made structural: there is no way to *omit* the coordinate,
    only to declare it inapplicable on the record. The declaration and the value
    are cross-checked, so ``APPLICABLE`` with no value and ``NOT_APPLICABLE``
    with a value are both refused — neither is silently repaired into the other.

    ``NOT_APPLICABLE`` and ``APPLICABLE`` produce different canonical bytes, so
    a decision to declare a coordinate inapplicable is itself digest-bound —
    which matters because §15 makes an applicability mismatch "a resolution
    refusal, not an advisory note".

    Under ``APPLICABLE`` the value must be an **exact** coordinate token: a
    geography or domain of ``*`` or ``any`` would be a wildcard, and §17.1
    admits exact-coordinate lookup only.
    """

    declaration: BenchmarkApplicabilityDeclaration
    value: str = ""

    def __post_init__(self) -> None:
        require_exact_type(
            self.declaration,
            BenchmarkApplicabilityDeclaration,
            "BenchmarkApplicabilityCoordinate.declaration",
        )
        text = require_canonical_str(
            self.value, "BenchmarkApplicabilityCoordinate.value", allow_empty=True
        )
        if self.declaration is BenchmarkApplicabilityDeclaration.APPLICABLE:
            if not text:
                raise _fail(
                    "BenchmarkApplicabilityCoordinate declared APPLICABLE must "
                    "carry a non-empty value; declaring applicability without "
                    "naming the value it applies to records no decision "
                    "(ADR §15 rows 6-7)",
                    _R.BENCHMARK_APPLICABILITY_INCONSISTENT,
                )
            require_exact_coordinate_token(
                text, "BenchmarkApplicabilityCoordinate.value"
            )
        elif text:
            raise _fail(
                "BenchmarkApplicabilityCoordinate declared NOT_APPLICABLE must "
                f"carry an empty value (got {text!r}); a value under "
                "NOT_APPLICABLE is an ambiguous coordinate, not a recorded "
                "decision (ADR §15)",
                _R.BENCHMARK_APPLICABILITY_INCONSISTENT,
            )

    @classmethod
    def applicable(cls, value: str) -> "BenchmarkApplicabilityCoordinate":
        """Declare the coordinate applicable, with ``value``."""

        return cls(
            declaration=BenchmarkApplicabilityDeclaration.APPLICABLE, value=value
        )

    @classmethod
    def not_applicable(cls) -> "BenchmarkApplicabilityCoordinate":
        """Declare the coordinate inapplicable — a decision, not an omission."""

        return cls(
            declaration=BenchmarkApplicabilityDeclaration.NOT_APPLICABLE, value=""
        )


# --------------------------------------------------------------------------- #
# Tenant / scope (ADR §15 row 5, §27.1)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BenchmarkScope:
    """The tenant or platform-wide scope of a benchmark definition (§15 row 5).

    Row 5 is "required (may denote a platform-wide scope explicitly, **never by
    omission**)". A definition is therefore scoped to exactly one named tenant or
    declared platform-wide on the record; there is no third state, and no way to
    leave the question open for a later reader to guess.

    ``PLATFORM_WIDE`` must carry no tenant and ``TENANT`` must carry one, each
    cross-checked. §27.1's discipline — a tenant is never inferred or defaulted —
    is what makes this load-bearing: §17.6 requires cross-tenant non-disclosure,
    and a record whose scope was implicit could not be checked against it.

    Declaring a scope is not being granted one. Whether a caller may resolve a
    platform-wide or another tenant's definition is a §17.6 question, and §17.6
    is BR-2's.
    """

    kind: BenchmarkScopeKind
    tenant_id: str = ""

    def __post_init__(self) -> None:
        require_exact_type(self.kind, BenchmarkScopeKind, "BenchmarkScope.kind")
        text = require_canonical_str(
            self.tenant_id, "BenchmarkScope.tenant_id", allow_empty=True
        )
        if self.kind is BenchmarkScopeKind.TENANT:
            if not text:
                raise _fail(
                    "BenchmarkScope declared TENANT must name a tenant_id; ADR "
                    "§27.1 never infers or defaults a tenant, and §17.6's "
                    "cross-tenant non-disclosure cannot be checked against an "
                    "unnamed one",
                    _R.BENCHMARK_APPLICABILITY_INCONSISTENT,
                )
            require_exact_coordinate_token(text, "BenchmarkScope.tenant_id")
        elif text:
            raise _fail(
                "BenchmarkScope declared PLATFORM_WIDE must carry an empty "
                f"tenant_id (got {text!r}); a platform-wide scope that also "
                "names a tenant is two answers to one question (ADR §15 row 5)",
                _R.BENCHMARK_APPLICABILITY_INCONSISTENT,
            )

    @classmethod
    def platform_wide(cls) -> "BenchmarkScope":
        """Declare the definition platform-wide — explicitly, per §15 row 5."""

        return cls(kind=BenchmarkScopeKind.PLATFORM_WIDE, tenant_id="")

    @classmethod
    def for_tenant(cls, tenant_id: str) -> "BenchmarkScope":
        """Scope the definition to exactly one named tenant."""

        return cls(kind=BenchmarkScopeKind.TENANT, tenant_id=tenant_id)


# --------------------------------------------------------------------------- #
# The exact coordinate (ADR §15 rows 1, 2, 3, 5, 6, 7; B-8; §17.1, §17.2)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BenchmarkCoordinate:
    """The complete, exact set of coordinates that names **one** benchmark version.

    ADR B-8: "Benchmark identity is exact and digest-bound. Floating ``latest``,
    implicit version selection, and string-parsed successor guesses are
    **prohibited in governed evaluation**. A floating reference must be
    *unrepresentable* on the trusted path, not merely discouraged."

    This type is where "unrepresentable" is made literal. Every field is
    mandatory with no default, so a **partial** coordinate cannot be built; every
    identifier must be an exact token, so a wildcard cannot be written; and the
    version must parse as an exact Semantic Versioning 2.0.0 string, so a range,
    a comparator or a two-component version cannot be written either. There is no
    constructor, classmethod or sentinel that yields a coordinate meaning "the
    newest one".

    This is a **name**, not a lookup
    --------------------------------
    Naming a benchmark version is not finding one, and finding one is not trusting
    one. §17.14 keeps "retrieval distinct from trusted resolution ... different
    operations, different return types", and BR-1 implements neither: there is no
    resolver, no registry, no store and no lookup function anywhere in this
    package. A future BR-2 resolver will take a coordinate of exactly this shape;
    that it does not exist yet is why BR-1 mints no resolution-request type and no
    resolution-result type.
    """

    benchmark_id: str
    benchmark_family: str
    benchmark_version: str
    scope: BenchmarkScope
    geography: BenchmarkApplicabilityCoordinate
    domain: BenchmarkApplicabilityCoordinate

    def __post_init__(self) -> None:
        require_exact_coordinate_token(
            self.benchmark_id, "BenchmarkCoordinate.benchmark_id"
        )
        require_exact_coordinate_token(
            self.benchmark_family, "BenchmarkCoordinate.benchmark_family"
        )
        require_exact_semantic_version(
            self.benchmark_version, "BenchmarkCoordinate.benchmark_version"
        )
        require_exact_type(self.scope, BenchmarkScope, "BenchmarkCoordinate.scope")
        for name in ("geography", "domain"):
            require_exact_type(
                getattr(self, name),
                BenchmarkApplicabilityCoordinate,
                f"BenchmarkCoordinate.{name}",
            )

    @property
    def exact_identity(self) -> tuple:
        """The coordinate tuple that must not be reused across benchmarks.

        Two definitions differing in any element of this tuple are different
        benchmark versions, and their canonical digests differ accordingly.
        """

        return (
            self.benchmark_id,
            self.benchmark_family,
            self.benchmark_version,
            self.scope.kind.value,
            self.scope.tenant_id,
            self.geography.declaration.value,
            self.geography.value,
            self.domain.declaration.value,
            self.domain.value,
        )

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over."""

        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the complete exact coordinate.

        A fingerprint of a **name**. It is not a registration, not a resolution
        and not a proof that any benchmark exists at this coordinate.
        """

        return canonical_digest(self)


# --------------------------------------------------------------------------- #
# Measurement semantics (ADR §15 rows 8-14)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BenchmarkMeasurementSemantics:
    """What is measured and how a comparison is interpreted (§15 rows 8-14).

    ADR §18 defines a benchmark definition as "an approved, versioned reference
    describing **what is measured and how comparison is interpreted**". These
    seven coordinates are that description, and §15 makes every one of them
    **required** without qualification — so this contract has no optional field,
    no default and no partial state. A benchmark whose unit, population,
    aggregation or observation window were unstated would be uninterpretable, and
    an uninterpretable definition cannot be compared against anything.

    This records semantics only
    ---------------------------
    No conversion, normalization, dimensional analysis, comparison, aggregation
    or evaluation happens here or anywhere in this package. §18 assigns
    comparison to the consuming evaluation engine and B-12 keeps result
    calculation away from the Registry entirely. Every field is an opaque
    declared token: no unit, metric, population, aggregation or observation-window
    vocabulary is ratified anywhere in the ADR, so none is invented.

    ``intended_outcome_ref`` is §15 row 8's "intended outcome / metric purpose",
    required unconditionally — unlike geography and domain it is not an
    applicability-declared coordinate, because §15 does not qualify it. It names
    the purpose the benchmark exists to serve; it does not authorize converting a
    comparison into value, which §21 keeps with ``governed-value`` under an
    approved ``IntendedOutcomePolicy``.
    """

    intended_outcome_ref: str
    metric_ref: str
    unit: str
    measurement_protocol_ref: str
    population_ref: str
    aggregation_semantics_ref: str
    observation_window_ref: str

    _REQUIRED = (
        "intended_outcome_ref",
        "metric_ref",
        "unit",
        "measurement_protocol_ref",
        "population_ref",
        "aggregation_semantics_ref",
        "observation_window_ref",
    )

    def __post_init__(self) -> None:
        missing = []
        for name in BenchmarkMeasurementSemantics._REQUIRED:
            value = getattr(self, name)
            if type(value) is str and not value.strip():
                missing.append(name)
        if missing:
            raise _fail(
                "BenchmarkMeasurementSemantics requires every ADR §15 row 8-14 "
                f"coordinate; missing or blank: {', '.join(sorted(missing))}. A "
                "partial measurement group fails closed rather than yielding a "
                "definition whose comparison semantics are undefined",
                _R.BENCHMARK_MEASUREMENT_SEMANTICS_INCOMPLETE,
            )
        for name in BenchmarkMeasurementSemantics._REQUIRED:
            require_exact_coordinate_token(
                getattr(self, name), f"BenchmarkMeasurementSemantics.{name}"
            )

    @property
    def measurement_identity(self) -> tuple:
        """The tuple a cross-metric or cross-unit replay must move."""

        return tuple(
            getattr(self, name) for name in BenchmarkMeasurementSemantics._REQUIRED
        )


# --------------------------------------------------------------------------- #
# Effective period (ADR §15 row 15, §17.9)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BenchmarkEffectivePeriod:
    """The half-open effective period ``[effective_from, effective_to)`` (§17.9).

    ADR §15 row 15 makes the effective period **required**, and §17.9 fixes it as
    half-open with "boundary semantics stated once and applied identically
    everywhere". ``effective_to`` is therefore the **exclusive** end: an instant
    equal to it is already outside.

    An open-ended period is declared, never inferred
    ------------------------------------------------
    An open-ended benchmark is legitimate, but "no end bound" and "an end bound
    the author omitted" must not share one encoding. :class:`TemporalBoundDeclaration`
    makes the choice explicit and digest-bound: ``BOUNDED`` requires an end,
    ``OPEN_ENDED`` refuses one, and neither is repaired into the other.

    No clock is read
    ----------------
    :meth:`is_effective_at` and :meth:`temporal_refusal_at` take the instant as a
    mandatory parameter with no default (ADR §22.9, §22.10 — "explicit
    caller-supplied evaluation instant ... a parameter, not an ambient read").
    Nothing here changes as time passes, which is why expiry is not a lifecycle
    state.
    """

    effective_from: datetime
    end_declaration: TemporalBoundDeclaration
    effective_to: Optional[datetime] = None

    def __post_init__(self) -> None:
        require_aware_datetime(
            self.effective_from, "BenchmarkEffectivePeriod.effective_from"
        )
        require_exact_type(
            self.end_declaration,
            TemporalBoundDeclaration,
            "BenchmarkEffectivePeriod.end_declaration",
        )
        require_optional_aware_datetime(
            self.effective_to, "BenchmarkEffectivePeriod.effective_to"
        )
        if self.end_declaration is TemporalBoundDeclaration.BOUNDED:
            if self.effective_to is None:
                raise _fail(
                    "BenchmarkEffectivePeriod declared BOUNDED must supply "
                    "effective_to; a bounded interval with no end bound is not "
                    "an interval (ADR §15 row 15, §17.9)",
                    _R.BENCHMARK_EFFECTIVE_PERIOD_INVALID,
                )
            require_strictly_before(
                self.effective_from,
                self.effective_to,
                "BenchmarkEffectivePeriod.effective_from",
                "BenchmarkEffectivePeriod.effective_to",
                "the effective period is half-open [effective_from, "
                "effective_to) per ADR §17.9",
            )
        elif self.effective_to is not None:
            raise _fail(
                "BenchmarkEffectivePeriod declared OPEN_ENDED must not supply "
                "effective_to; an open right bound and an end instant are two "
                "answers to one question (ADR §17.9)",
                _R.BENCHMARK_EFFECTIVE_PERIOD_INVALID,
            )

    @classmethod
    def bounded(
        cls, effective_from: datetime, effective_to: datetime
    ) -> "BenchmarkEffectivePeriod":
        """A half-open period with an explicit exclusive end bound."""

        return cls(
            effective_from=effective_from,
            end_declaration=TemporalBoundDeclaration.BOUNDED,
            effective_to=effective_to,
        )

    @classmethod
    def open_ended(cls, effective_from: datetime) -> "BenchmarkEffectivePeriod":
        """A period open on the right — a recorded decision, not an omission."""

        return cls(
            effective_from=effective_from,
            end_declaration=TemporalBoundDeclaration.OPEN_ENDED,
            effective_to=None,
        )

    def is_effective_at(self, instant: datetime) -> bool:
        """Half-open ``[effective_from, effective_to)`` membership (ADR §17.9).

        ``instant`` is always an explicit caller input — **the system clock is
        never read**. This answers a *temporal* question about a *declared*
        interval. It is not a validity decision: §17 additionally requires
        revocation, approval, publisher, lifecycle and scope checks that BR-1
        cannot perform at all.
        """

        require_aware_datetime(
            instant, "BenchmarkEffectivePeriod.is_effective_at.instant"
        )
        if instant < self.effective_from:
            return False
        if self.effective_to is not None and instant >= self.effective_to:
            return False
        return True

    def temporal_refusal_at(self, instant: datetime):
        """The typed temporal refusal at ``instant``, or ``None`` if within.

        Returns ``BENCHMARK_NOT_YET_EFFECTIVE`` before ``effective_from`` and
        ``BENCHMARK_EXPIRED`` at or after ``effective_to`` — the half-open
        boundary, so ``effective_to`` itself is already expired.

        ``None`` means "no *temporal* refusal applies". It is emphatically not a
        pass: nothing about approval, publication, registration, revocation,
        supersession or scope has been established (B-9).
        """

        require_aware_datetime(
            instant, "BenchmarkEffectivePeriod.temporal_refusal_at.instant"
        )
        if instant < self.effective_from:
            return _R.BENCHMARK_NOT_YET_EFFECTIVE
        if self.effective_to is not None and instant >= self.effective_to:
            return _R.BENCHMARK_EXPIRED
        return None


# --------------------------------------------------------------------------- #
# Source / provenance requirements (ADR §15 row 16)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BenchmarkSourceRequirements:
    """Where the benchmark's values come from, and what provenance is required.

    ADR §15 row 16 makes "source / provenance requirements" a **required**
    identity coordinate. ``source_ref`` names the authoritative source the
    definition draws on; ``provenance_requirement_refs`` names the provenance
    conditions any observation compared against this benchmark must satisfy.

    These are **requirements the definition states**, not evidence
    -------------------------------------------------------------
    Verifying that an actual observation's provenance meets them is evidence
    verification, which ADR §7.2 row 9 assigns to the Trusted Evidence Authority
    and explicitly not to the Registry. Nothing here inspects, holds or verifies
    evidence, and nothing here is an evidence reference.

    Order is irrelevant, so it is normalized
    ----------------------------------------
    A set of requirements means the same thing in any order, and §22.2 requires
    canonical bytes to be a pure function of the payload — so two callers who
    wrote the same requirements in different orders must produce one digest. The
    tuple is therefore sorted at construction, inside the contract. The encoder
    itself never reorders, so a future collection whose order *is* meaningful
    keeps its order.

    Duplicates are refused, never de-duplicated: a document that names one
    requirement twice is malformed, and B-7 admits no silent repair. A
    caller-owned ``list`` is defensively copied, so later mutation of it cannot
    change this frozen contract or its digest (§17.7).
    """

    source_ref: str
    provenance_requirement_refs: tuple = ()

    def __post_init__(self) -> None:
        require_exact_coordinate_token(
            self.source_ref, "BenchmarkSourceRequirements.source_ref"
        )
        normalized = normalize_unordered_reference_tuple(
            self.provenance_requirement_refs,
            "BenchmarkSourceRequirements.provenance_requirement_refs",
            reason=_R.BENCHMARK_SOURCE_REQUIREMENTS_INVALID,
        )
        object.__setattr__(self, "provenance_requirement_refs", normalized)


# --------------------------------------------------------------------------- #
# Approval reference (ADR §15 row 17, B-3, B-4, B-5)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BenchmarkApprovalReference:
    """The external approval a definition cites (§15 row 17, B-5).

    ADR B-5 is the governing rule: "A caller-provided approval label, a lifecycle
    enum on the artifact, a reputation score, a publisher **name**, or a
    caller-created verification object is **not** approval evidence. **Approval
    binds an exact content digest**, not a name and not an intent."

    So this contract cannot be a label. It carries three things, all mandatory:
    the approval's own reference, the authority that issued it, and — the part
    B-5 insists on — the **exact content digest the approval binds**. A
    :class:`CanonicalBenchmarkDefinitionIdentity` refuses to be constructed when
    that digest is not the content digest it declares, so an approval for
    *different content* cannot be carried alongside a definition without the
    mismatch being structural.

    Citing an approval is not verifying one
    ---------------------------------------
    ADR §16.2 stage 3 — "external benchmark-approval verification ... through a
    configured trusted approval-verification boundary" — is **BR-2**, and B-4
    keeps the Registry from approving its own input in any case. What BR-1
    provides is that a definition and its cited approval cannot disagree about
    *which content* was approved. That is a consistency invariant, not a
    verification, and it establishes nothing about whether the approval exists.
    """

    approval_ref: str
    approval_authority_ref: str
    approved_content_digest: str

    def __post_init__(self) -> None:
        require_exact_coordinate_token(
            self.approval_ref, "BenchmarkApprovalReference.approval_ref"
        )
        require_exact_coordinate_token(
            self.approval_authority_ref,
            "BenchmarkApprovalReference.approval_authority_ref",
        )
        require_digest(
            self.approved_content_digest,
            "BenchmarkApprovalReference.approved_content_digest",
            reason=_R.BENCHMARK_APPROVAL_REFERENCE_INVALID,
        )


# --------------------------------------------------------------------------- #
# Supersession declaration (ADR §15 row 20, §17.12, §17.13, DD-4)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class BenchmarkSupersessionDeclaration:
    """What a definition records about its own supersession (§15 row 20).

    §15 row 20 requires the coordinate and rules that its **absence never implies
    "not superseded"**. The only way to honour that in a contract is to make the
    coordinate mandatory and to give it a value that says exactly what is true:
    at BR-1, supersession is *undetermined*.

    Why there is no successor reference here
    ----------------------------------------
    §17.12 admits supersession "**only** through a structured successor
    reference", and **DD-4** defers that reference entirely — its shape, successor
    authorization, activation instant, predecessor invalidation, historical
    resolution across the boundary and cross-tenant/cross-family restrictions.
    Writing a successor from a version string, an ordering or a name would be the
    "guessed supersession ... unsigned authority decision" §17.12 prohibits. So
    BR-1 ships the declaration and not the reference, and §17.13's "fail closed
    when supersession cannot be determined" is exactly what a consumer must do
    with it.

    This type has one field with one admissible value, deliberately. When DD-4 is
    ratified, a successor member and its reference are **added**; nothing here is
    renamed or re-valued, and no digest of an existing definition moves.
    """

    status: BenchmarkSupersessionStatus

    def __post_init__(self) -> None:
        require_exact_type(
            self.status,
            BenchmarkSupersessionStatus,
            "BenchmarkSupersessionDeclaration.status",
        )
        if self.status is not BenchmarkSupersessionStatus.UNDETERMINED:
            raise _fail(
                "BenchmarkSupersessionDeclaration.status must be UNDETERMINED "
                "at this contract version; the structured successor reference "
                "ADR §17.12 requires is deferred to DD-4, and a supersession "
                "declared without one would be a guessed, unsigned authority "
                "decision",
                _R.BENCHMARK_SUPERSESSION_DECLARATION_INVALID,
            )

    @classmethod
    def undetermined(cls) -> "BenchmarkSupersessionDeclaration":
        """Record that supersession is undetermined — never "not superseded"."""

        return cls(status=BenchmarkSupersessionStatus.UNDETERMINED)


# --------------------------------------------------------------------------- #
# The identity (ADR §15, all twenty rows)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CanonicalBenchmarkDefinitionIdentity:
    """The exact identity of one benchmark definition — and nothing more.

    Every field participates in :meth:`canonical_digest`, so the *complete*
    identity distinguishes one definition from another, not merely its id and
    version. The dataclass is frozen and every nested contract is frozen, so no
    post-construction mutation can alter the content or the digest.

    Construction is a **structural** act. It records what a caller says about a
    benchmark definition and makes swapping any coordinate detectable. It
    establishes no approval, confers no registration, and authorizes nothing —
    not a comparison, not a readiness determination, not a policy decision, not a
    monetary valuation, not a deployment.

    Two cross-field invariants
    --------------------------
    Both are structural consequences of ratified rules, and neither is a
    verification:

    * **B-5** — the cited approval must bind *this* content digest. An approval
      naming different content is refused, so a definition can never travel with
      an approval for something else.
    * **B-3 / B-4** — the publisher may not also be the approving authority. "A
      benchmark **author/publisher** cannot approve its own benchmark ... No
      component occupies two adjacent roles for the same benchmark version."
      Checking this over the declared identifiers is what B-4 means by "checked
      by the Registry itself, not merely assumed of the verifier"; verifying that
      either identity is genuine remains BR-2's.
    """

    coordinate: BenchmarkCoordinate
    content_digest: str
    measurement: BenchmarkMeasurementSemantics
    effective_period: BenchmarkEffectivePeriod
    source_requirements: BenchmarkSourceRequirements
    approval: BenchmarkApprovalReference
    publisher_id: str
    lifecycle_state: BenchmarkLifecycleState
    supersession: BenchmarkSupersessionDeclaration

    def __post_init__(self) -> None:
        require_exact_type(
            self.coordinate,
            BenchmarkCoordinate,
            "CanonicalBenchmarkDefinitionIdentity.coordinate",
        )
        require_digest(
            self.content_digest,
            "CanonicalBenchmarkDefinitionIdentity.content_digest",
        )
        require_exact_type(
            self.measurement,
            BenchmarkMeasurementSemantics,
            "CanonicalBenchmarkDefinitionIdentity.measurement",
        )
        require_exact_type(
            self.effective_period,
            BenchmarkEffectivePeriod,
            "CanonicalBenchmarkDefinitionIdentity.effective_period",
        )
        require_exact_type(
            self.source_requirements,
            BenchmarkSourceRequirements,
            "CanonicalBenchmarkDefinitionIdentity.source_requirements",
        )
        require_exact_type(
            self.approval,
            BenchmarkApprovalReference,
            "CanonicalBenchmarkDefinitionIdentity.approval",
        )
        require_exact_coordinate_token(
            self.publisher_id, "CanonicalBenchmarkDefinitionIdentity.publisher_id"
        )
        require_exact_type(
            self.lifecycle_state,
            BenchmarkLifecycleState,
            "CanonicalBenchmarkDefinitionIdentity.lifecycle_state",
        )
        require_exact_type(
            self.supersession,
            BenchmarkSupersessionDeclaration,
            "CanonicalBenchmarkDefinitionIdentity.supersession",
        )

        if self.approval.approved_content_digest != self.content_digest:
            raise _fail(
                "CanonicalBenchmarkDefinitionIdentity.approval binds content "
                f"digest {self.approval.approved_content_digest!r}, which is "
                f"not this definition's content_digest {self.content_digest!r}. "
                "ADR B-5: approval binds an exact content digest, so an "
                "approval for different content is not this definition's "
                "approval",
                _R.BENCHMARK_APPROVAL_REFERENCE_INVALID,
            )
        if self.approval.approval_authority_ref == self.publisher_id:
            raise _fail(
                "CanonicalBenchmarkDefinitionIdentity names "
                f"{self.publisher_id!r} as both publisher and approving "
                "authority. ADR B-3/B-4: a publisher cannot approve its own "
                "benchmark, and no component occupies two adjacent roles for "
                "the same benchmark version",
                _R.BENCHMARK_ROLE_SEPARATION_VIOLATED,
            )

    # ------------------------------------------------------------------ #
    # Honest, non-settable status (ADR §14.5's discipline, B-9)
    # ------------------------------------------------------------------ #
    @property
    def structural_status(self) -> BenchmarkStructuralStatus:
        """Always ``STRUCTURAL_UNVERIFIED``.

        A read-only property, not a field: there is no assignment, constructor
        argument or subclass hook that can raise it. Raising it requires a
        registry, an approval boundary, publisher key trust and a resolver —
        BR-2.
        """

        return BenchmarkStructuralStatus.STRUCTURAL_UNVERIFIED

    @property
    def trusted_resolution_performed(self) -> bool:
        """Always ``False`` — constructing an identity resolves nothing (B-9)."""

        return False

    @property
    def unresolved_reason(self) -> BenchmarkRefusalReason:
        """Always ``BENCHMARK_RESOLUTION_NOT_PERFORMED``.

        A read-only property naming the honest state of every identity this
        package can build: a definition exists as a shape, and no registry has
        resolved it. A consumer that requires a trusted benchmark refuses on this
        code. It is not settable, and there is no member of
        :class:`~.reasons.BenchmarkRefusalReason` that would represent success.
        """

        return _R.BENCHMARK_RESOLUTION_NOT_PERFORMED

    # ------------------------------------------------------------------ #
    # Structural coordinates and structural refusals
    # ------------------------------------------------------------------ #
    @property
    def identity_coordinate(self) -> tuple:
        """The load-bearing coordinate tuple, for structural comparison.

        Mutating any element produces a different tuple **and** a different
        :meth:`canonical_digest`.
        """

        return (
            self.coordinate.exact_identity
            + (self.content_digest,)
            + self.measurement.measurement_identity
            + (
                self.approval.approval_ref,
                self.approval.approval_authority_ref,
                self.publisher_id,
                self.source_requirements.source_ref,
            )
        )

    @property
    def lifecycle_refusal(self):
        """``BENCHMARK_REVOKED`` when the definition declares itself revoked.

        ``None`` otherwise, and ``None`` is **not** an admissibility decision:
        ADR §16.2 stage 5's "state admissible" rule belongs to BR-2, which alone
        can check a signed, entitled, verified revocation record (§17.10-11).
        What BR-1 can say is that an artifact declaring ``REVOKED`` about itself
        must never be treated as usable.
        """

        if self.lifecycle_state is BenchmarkLifecycleState.REVOKED:
            return _R.BENCHMARK_REVOKED
        return None

    def is_effective_at(self, instant: datetime) -> bool:
        """Delegate to the declared effective period (ADR §17.9).

        ``instant`` is a mandatory caller-supplied parameter; no clock is read.
        A ``True`` here is a statement about a declared interval and nothing
        else — not currency, not validity, not resolvability.
        """

        return self.effective_period.is_effective_at(instant)

    def temporal_refusal_at(self, instant: datetime):
        """The typed temporal refusal at ``instant``, or ``None`` if within.

        ``None`` means no *temporal* refusal applies. It is not a pass:
        :attr:`unresolved_reason` still holds for every identity this package can
        build.
        """

        return self.effective_period.temporal_refusal_at(instant)

    def structural_refusals_at(self, instant: datetime) -> tuple:
        """Every BR-1-decidable refusal for this identity at ``instant``.

        Returns the typed reasons in :class:`~.reasons.BenchmarkRefusalReason`
        declaration order, so the sequence is deterministic for identical inputs
        (ADR §22.13) and a digest taken over a refusal set is stable.

        The tuple **always contains** ``BENCHMARK_RESOLUTION_NOT_PERFORMED``,
        because it always applies: BR-1 has no registry. There is therefore no
        input for which this method returns an empty tuple, and no way to read a
        pass out of it — which is the point. A caller that wants only the
        *conditional* refusals can filter that member out, and is then reading a
        list of structural faults, not an admission decision.
        """

        require_aware_datetime(
            instant, "CanonicalBenchmarkDefinitionIdentity.structural_refusals_at.instant"
        )
        refusals = {_R.BENCHMARK_RESOLUTION_NOT_PERFORMED}
        temporal = self.temporal_refusal_at(instant)
        if temporal is not None:
            refusals.add(temporal)
        lifecycle = self.lifecycle_refusal
        if lifecycle is not None:
            refusals.add(lifecycle)
        order = list(BenchmarkRefusalReason)
        return tuple(sorted(refusals, key=order.index))

    def canonical_bytes(self) -> bytes:
        """The exact bytes :meth:`canonical_digest` is computed over.

        See :mod:`..contracts.canonical` for the complete rule set. Two
        identities that are ``==`` — including ones whose instants were written
        with different UTC offsets — produce byte-identical output.
        """

        return canonical_bytes(self)

    def canonical_digest(self) -> str:
        """Deterministic sha-256 over the **complete** benchmark identity.

        Two identities differing in any of ADR §15's twenty coordinates — the
        tenant, the geography, the domain, the metric, the unit, the population,
        the aggregation, the observation window, the effective period, the
        source, the approval, the publisher, the lifecycle state, the
        supersession declaration — produce different digests.

        This is **not** the ADR §15 row 4 **content digest**. That coordinate is
        a value the definition *declares* about content this package never holds;
        this is a fingerprint of the identity. Confusing them would let an
        identity digest stand in for a check on the benchmark's actual bytes,
        which is §16.2 stage 2 and is BR-2's.
        """

        return canonical_digest(self)


#: ADR §15's twenty coordinates, as dotted paths into
#: :class:`CanonicalBenchmarkDefinitionIdentity`, in §15 row order.
#:
#: The machine-readable form of the table in this module's docstring. It exists so
#: coordinate coverage is *checked* rather than asserted in prose: the package
#: tests walk it to prove every §15 row resolves to a real attribute, and walk
#: every **leaf** beneath the identity to prove each one is present in the
#: canonical body and independently changes the digest.
#:
#: Rows 1-3 and 5-7 resolve into the nested
#: :class:`BenchmarkCoordinate`; rows 8-14 into
#: :class:`BenchmarkMeasurementSemantics`. Rows 15-17 and 20 name whole
#: sub-contracts, each of which carries more than one leaf.
BENCHMARK_IDENTITY_COORDINATES: tuple = (
    "coordinate.benchmark_id",
    "coordinate.benchmark_family",
    "coordinate.benchmark_version",
    "content_digest",
    "coordinate.scope",
    "coordinate.geography",
    "coordinate.domain",
    "measurement.intended_outcome_ref",
    "measurement.metric_ref",
    "measurement.unit",
    "measurement.measurement_protocol_ref",
    "measurement.population_ref",
    "measurement.aggregation_semantics_ref",
    "measurement.observation_window_ref",
    "effective_period",
    "source_requirements",
    "approval",
    "publisher_id",
    "lifecycle_state",
    "supersession",
)
