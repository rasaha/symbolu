"""Canonical public API for the Ugence Benchmark Registry (BR-1).

The deliberately small, supported public surface. Import from here (or the
equivalently-exported top-level :mod:`ugence_benchmark_registry`). Every symbol
below is a stable contract shape, vocabulary or pinned constant;
``public_api.json`` snapshots this surface and
``tests/packaging/test_public_api.py`` asserts they agree — in the source tree,
in the built wheel, and in an isolated installed runtime.

What this surface contains
--------------------------
The structural contract layer of ADR §30's **BR-1** — "Benchmark Definition
Contracts: benchmark identity (§15), lifecycle state, structured references.
Contracts only; **no registry**."

* the exact benchmark coordinate (:class:`BenchmarkCoordinate`) and the complete
  twenty-coordinate identity of ADR §15
  (:class:`CanonicalBenchmarkDefinitionIdentity`), with the nested
  :class:`BenchmarkScope`, :class:`BenchmarkApplicabilityCoordinate`,
  :class:`BenchmarkMeasurementSemantics`, :class:`BenchmarkEffectivePeriod`,
  :class:`BenchmarkSourceRequirements`, :class:`BenchmarkApprovalReference` and
  :class:`BenchmarkSupersessionDeclaration`;
* one deterministic canonicalization path and one digest path, versioned and
  domain-separated;
* the ADR §29 lifecycle vocabulary and its closed transition relation;
* the typed ADR §16.3 refusal vocabulary, every member of which is a refusal.

What this surface does **not** contain
--------------------------------------
**No registry, no store, no resolver, no lookup, no registration, no admission,
no approval verification, no publisher or key trust, no signature, no revocation
record, no successor resolution and no service.** Those are **BR-2** (ADR §30,
§32). There is no ``latest()``, no ``current()``, no mutable alias and no
implicit version selection anywhere in this package, and B-8 requires that a
floating reference be *unrepresentable* rather than merely absent — which is why
:class:`BenchmarkCoordinate` refuses one at construction.

Nothing here is a benchmark result, an observed measurement, a comparison, a
piece of evidence, a verification receipt, a policy decision, a readiness
determination, an authorization or a monetary value. ADR §18 keeps those four
artifacts separate and rules that "no renaming promotes one into another", and
B-12 states flatly that "the Registry computes nothing".

Every constructible object in this API reports its own limits: its
:attr:`structural_status` is permanently ``STRUCTURAL_UNVERIFIED``,
:attr:`trusted_resolution_performed` is permanently ``False``, and
:attr:`unresolved_reason` is permanently
``BENCHMARK_RESOLUTION_NOT_PERFORMED``.
"""

from __future__ import annotations

from .contracts import (
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
from .version import __version__

__all__ = [
    "__version__",
    # typed contract-validation errors
    "BenchmarkContractError",
    "BenchmarkCanonicalizationError",
    "BenchmarkLifecycleError",
    # vocabularies
    "BenchmarkApplicabilityDeclaration",
    "BenchmarkScopeKind",
    "TemporalBoundDeclaration",
    "BenchmarkLifecycleState",
    "BenchmarkStructuralStatus",
    "BenchmarkSupersessionStatus",
    "BenchmarkRefusalReason",
    # contract shapes — ADR §15's twenty coordinates
    "BenchmarkApplicabilityCoordinate",
    "BenchmarkScope",
    "BenchmarkCoordinate",
    "BenchmarkMeasurementSemantics",
    "BenchmarkEffectivePeriod",
    "BenchmarkSourceRequirements",
    "BenchmarkApprovalReference",
    "BenchmarkSupersessionDeclaration",
    "CanonicalBenchmarkDefinitionIdentity",
    # one canonicalization path, one digest path
    "canonical_bytes",
    "canonical_digest",
    # the ADR §29 lifecycle relation
    "is_valid_lifecycle_transition",
    "require_valid_lifecycle_transition",
    # pinned constants
    "BENCHMARK_REGISTRY_CANONICALIZATION_VERSION",
    "BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN",
    "BENCHMARK_IDENTITY_COORDINATES",
    "BENCHMARK_LIFECYCLE_ORDER",
    "BENCHMARK_LIFECYCLE_TRANSITIONS",
    "BENCHMARK_TERMINAL_LIFECYCLE_STATES",
    "BENCHMARK_REFUSAL_REASONS",
    "BR1_BENCHMARK_REFUSAL_REASONS",
]
