"""Ugence Benchmark Registry — BR-1 benchmark-definition contracts.

The shared, platform-wide Benchmark Registry's contract package, ratified in
``docs/architecture/ADR_UGENCE_TRUSTED_EVIDENCE_AND_BENCHMARK_REGISTRY.md``
(B-1, §6.2) and implementing milestone **BR-1** of §30: "Benchmark Definition
Contracts — benchmark identity (§15), lifecycle state, structured references.
**Contracts only; no registry.**"

The question BR-1 answers
-------------------------
*Which exact benchmark definition is this, and what does it declare about
itself?* — precisely enough that swapping any one of ADR §15's twenty
coordinates is mechanically detectable, and that a floating reference to "the
latest version" cannot be written down at all.

It does **not** answer *may this benchmark be trusted?* Nothing in this package
can. That question needs admission, approval verification, publisher key trust,
append-only registration and exact-coordinate resolution — the whole of §16.2 and
§17 — and every one of those is **BR-2**.

What this package is
--------------------
* the exact benchmark coordinate (:class:`BenchmarkCoordinate`) — ADR §15 rows
  1, 2, 3, 5, 6, 7 — in which a wildcard, a version range, a partial identity and
  a floating ``latest``/``current`` token are each **unrepresentable**, as B-8
  requires;
* the complete twenty-coordinate benchmark-definition identity
  (:class:`CanonicalBenchmarkDefinitionIdentity`) and its nested contracts:
  :class:`BenchmarkScope`, :class:`BenchmarkApplicabilityCoordinate`,
  :class:`BenchmarkMeasurementSemantics`, :class:`BenchmarkEffectivePeriod`,
  :class:`BenchmarkSourceRequirements`, :class:`BenchmarkApprovalReference` and
  :class:`BenchmarkSupersessionDeclaration`;
* one deterministic canonicalization path and one digest path, versioned and
  domain-separated (ADR §22, DD-9);
* the ADR §29 lifecycle vocabulary and its closed transition relation;
* the typed ADR §16.3 refusal vocabulary (DD-1), every member of which is a
  refusal.

What this package is **not**
----------------------------
It is **not a registry** and mints **no** authority. There is no store, no
resolver, no lookup, no registration, no admission ordering, no approval
verification, no publisher or key trust, no signature, no trust anchor, no
revocation record, no successor resolution and no service. It contains no
placeholder registry, no permissive stub and no field reserved for a later
milestone.

In particular:

* **A benchmark definition is not a benchmark result.** ADR §18 separates four
  artifacts — definition, observed measurement, comparison result, policy
  decision — and rules that "no renaming promotes one into another". B-12 is
  categorical: "the Registry computes nothing". Nothing here holds a measured
  value, performs a comparison, or produces a verdict.
* **A definition is not its content.** The benchmark's content is authored by
  domain owners (§7.2 row 1) and appears here only as ADR §15 row 4's declared
  content digest. Checking that digest against real content is §16.2 stage 2, and
  that is BR-2's.
* **A Policy Authority citation is not a resolution.** §19: "A policy reference
  to a benchmark is not proof that the benchmark resolved successfully. A policy
  artifact may name benchmark coordinates that are unregistered, revoked,
  superseded, expired, or belong to another tenant." A coordinate built from this
  package is a name; resolving it is BR-2's.
* **Possession is not validity.** B-9. Constructing any object here is
  possession, and nothing more.

It is explicitly **not** the ``comparative_governance_benchmark`` dataset that
gates ``platform_freeze.verify`` (§6.3 — "unrelated; an evaluation dataset, not a
governed benchmark definition"), **not** any ML or performance benchmark harness
in this repository, **not** ``BenchmarkReference`` (the neutral reference *type*,
already merged in ``ugence-governance-contracts``; §6.3 assigns this capability
the **values** it points at, not the type), and **not** the Trusted Evidence
Authority, the Policy Authority, the Risk Authority, the Decision Authority,
ActionGate, Agent Value Readiness or Governed Value.

It is a **leaf**: stdlib only, no Ugence package, no third-party runtime
dependency. ADR §23 permits the Benchmark Registry to depend on
``governance-contracts``; BR-1 takes the narrower zero-dependency option because
**DD-2** — which contracts land in that leaf — is explicitly blocked on "the
concrete contract shapes from TEV-1/**BR-1**", and pre-empting it here would
decide DD-2 by implementation. ``BenchmarkReference``, ``AssessedSystemBinding``
and ``EvidenceReference`` stay Governance Contracts' single definitions; this
package redefines none of them. No ``SystemManifest`` is defined (DD-11).

Nothing here proves anything about a benchmark
----------------------------------------------
Constructing any object in this package is a structural act. It establishes
internal consistency and digest-bound identity, and nothing else: not approval,
not publication, not registration, not currency, not unrevoked status, not
supersession status, not scope entitlement and not fitness for any comparison. A
caller-written approval reference, publisher name and lifecycle label are
enumerated non-proofs (B-5). No result of this package authorizes deployment,
runtime action, policy approval, evidence admission, readiness, monetary value or
causal attribution.

Import the curated surface from :mod:`ugence_benchmark_registry.api`.
"""

from __future__ import annotations

from .version import __version__

from .contracts import (  # noqa: E402
    BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN,
    BENCHMARK_IDENTITY_COORDINATES,
    BENCHMARK_LIFECYCLE_ORDER,
    BENCHMARK_LIFECYCLE_TRANSITIONS,
    BENCHMARK_REFUSAL_REASONS,
    BENCHMARK_REGISTRY_CANONICALIZATION_VERSION,
    BENCHMARK_TERMINAL_LIFECYCLE_STATES,
    BR1_BENCHMARK_REFUSAL_REASONS,
    BenchmarkApplicabilityCoordinate,
    BenchmarkApplicabilityDeclaration,
    BenchmarkApprovalReference,
    BenchmarkCanonicalizationError,
    BenchmarkContractError,
    BenchmarkCoordinate,
    BenchmarkEffectivePeriod,
    BenchmarkLifecycleError,
    BenchmarkLifecycleState,
    BenchmarkMeasurementSemantics,
    BenchmarkRefusalReason,
    BenchmarkScope,
    BenchmarkScopeKind,
    BenchmarkSourceRequirements,
    BenchmarkStructuralStatus,
    BenchmarkSupersessionDeclaration,
    BenchmarkSupersessionStatus,
    CanonicalBenchmarkDefinitionIdentity,
    TemporalBoundDeclaration,
    canonical_bytes,
    canonical_digest,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
)

from . import api  # noqa: E402,F401

__all__ = [
    "__version__",
    "BenchmarkContractError",
    "BenchmarkCanonicalizationError",
    "BenchmarkLifecycleError",
    "BenchmarkApplicabilityDeclaration",
    "BenchmarkScopeKind",
    "TemporalBoundDeclaration",
    "BenchmarkLifecycleState",
    "BenchmarkStructuralStatus",
    "BenchmarkSupersessionStatus",
    "BenchmarkRefusalReason",
    "BenchmarkApplicabilityCoordinate",
    "BenchmarkScope",
    "BenchmarkCoordinate",
    "BenchmarkMeasurementSemantics",
    "BenchmarkEffectivePeriod",
    "BenchmarkSourceRequirements",
    "BenchmarkApprovalReference",
    "BenchmarkSupersessionDeclaration",
    "CanonicalBenchmarkDefinitionIdentity",
    "canonical_bytes",
    "canonical_digest",
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
    "BENCHMARK_REGISTRY_CANONICALIZATION_VERSION",
    "BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN",
    "BENCHMARK_IDENTITY_COORDINATES",
    "BENCHMARK_LIFECYCLE_ORDER",
    "BENCHMARK_LIFECYCLE_TRANSITIONS",
    "BENCHMARK_TERMINAL_LIFECYCLE_STATES",
    "BENCHMARK_REFUSAL_REASONS",
    "BR1_BENCHMARK_REFUSAL_REASONS",
    "api",
]
