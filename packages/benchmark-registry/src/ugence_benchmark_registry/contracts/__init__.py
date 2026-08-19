"""Benchmark-definition contract shapes, enums, canonicalization and vocabulary.

Import the curated surface from :mod:`ugence_benchmark_registry.api` (or the
equivalently-exported top-level package) rather than from these modules directly.
"""

from __future__ import annotations

from .canonical import (
    BENCHMARK_DEFINITION_IDENTITY_DIGEST_DOMAIN,
    BENCHMARK_REGISTRY_CANONICALIZATION_VERSION,
    canonical_bytes,
    canonical_digest,
)
from .enums import (
    BENCHMARK_LIFECYCLE_ORDER,
    BENCHMARK_TERMINAL_LIFECYCLE_STATES,
    BenchmarkApplicabilityDeclaration,
    BenchmarkLifecycleState,
    BenchmarkScopeKind,
    BenchmarkStructuralStatus,
    BenchmarkSupersessionStatus,
    TemporalBoundDeclaration,
)
from .errors import (
    BenchmarkCanonicalizationError,
    BenchmarkContractError,
    BenchmarkLifecycleError,
)
from .identity import (
    BENCHMARK_IDENTITY_COORDINATES,
    BenchmarkApplicabilityCoordinate,
    BenchmarkApprovalReference,
    BenchmarkCoordinate,
    BenchmarkEffectivePeriod,
    BenchmarkMeasurementSemantics,
    BenchmarkScope,
    BenchmarkSourceRequirements,
    BenchmarkSupersessionDeclaration,
    CanonicalBenchmarkDefinitionIdentity,
)
from .lifecycle import (
    BENCHMARK_LIFECYCLE_TRANSITIONS,
    is_valid_lifecycle_transition,
    require_valid_lifecycle_transition,
)
from .reasons import (
    BENCHMARK_REFUSAL_REASONS,
    BR1_BENCHMARK_REFUSAL_REASONS,
    BenchmarkRefusalReason,
)

__all__ = [
    # errors
    "BenchmarkContractError",
    "BenchmarkCanonicalizationError",
    "BenchmarkLifecycleError",
    # enums
    "BenchmarkApplicabilityDeclaration",
    "BenchmarkScopeKind",
    "TemporalBoundDeclaration",
    "BenchmarkLifecycleState",
    "BenchmarkStructuralStatus",
    "BenchmarkSupersessionStatus",
    "BenchmarkRefusalReason",
    # contracts
    "BenchmarkApplicabilityCoordinate",
    "BenchmarkScope",
    "BenchmarkCoordinate",
    "BenchmarkMeasurementSemantics",
    "BenchmarkEffectivePeriod",
    "BenchmarkSourceRequirements",
    "BenchmarkApprovalReference",
    "BenchmarkSupersessionDeclaration",
    "CanonicalBenchmarkDefinitionIdentity",
    # canonicalization
    "canonical_bytes",
    "canonical_digest",
    # lifecycle
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
