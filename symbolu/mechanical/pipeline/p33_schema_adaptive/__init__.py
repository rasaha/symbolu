"""
P33 - Schema Adaptive Routing (Observation-Only)

Phase 33 computes schema-level stability and alignment metrics ONLY.
It answers: "Which internal cognitive schema is currently most stable
and aligned — without influencing behavior?"

This phase is observation-only and read-only.

CRITICAL CONSTRAINTS (NON-NEGOTIABLE):
- MUST NOT affect Regime (P6), Discourse (P7), Semantics (P8), Lexical (P9), Delivery (P21)
- MUST NOT gate, block, or route anything
- MUST NOT influence Phase 10/12 results
- MUST NOT import P6, P7, P8, P9, Policy, Planner, Renderer, or Observer modules (P22-P24)
- Same inputs → same outputs (bitwise deterministic)
- No randomness, no LLM calls

INVARIANTS:
- INV-P33-1: Phase 33 cannot influence any decision
- INV-P33-2: Schema scores are observational only
- INV-P33-3: Dominant schema selection has zero side effects
- INV-P33-4: Observer data (P22-P24) cannot enter Phase 33
- INV-P33-5: Absence of schema metadata does not break pipeline

Usage:
    from symbolu.mechanical.pipeline.p33_schema_adaptive import maybe_run_p33

    # In pipeline after coherence computation:
    maybe_run_p33(ctx)

    # Access snapshot (observation only):
    if ctx.p33 is not None:
        print(f"Dominant schema: {ctx.p33.dominant_schema}")
        print(f"Confidence: {ctx.p33.confidence}")
        print(f"Stability: {ctx.p33.stability_band.value}")
"""

# Schema definitions
from symbolu.mechanical.pipeline.p33_schema_adaptive.p33_schema_snapshot import (
    # Version
    P33_VERSION,
    # Enums
    SchemaStabilityBand,
    SchemaConfidenceBand,
    # Constants
    ALLOWED_SCHEMA_TAGS,
    # Dataclasses
    SchemaAdaptiveRoutingSnapshot,
    # Helpers
    create_snapshot,
    create_empty_snapshot,
)

# Resolver
from symbolu.mechanical.pipeline.p33_schema_adaptive.p33_schema_resolver import (
    P33SchemaAdaptiveResolver,
    # Weights (for testing/validation)
    W_COHERENCE_V3,
    W_COHERENCE_QUALITY,
    W_DRIFT_INVERSE,
    W_ENTROPY_INVERSE,
    W_ALIGN_COHERENCE,
    W_ALIGN_QUALITY,
    W_ALIGN_IDENTITY,
    W_DRIFT_FUSION,
    W_DRIFT_ENTROPY,
    # Thresholds
    STABILITY_HIGH_THRESHOLD,
    STABILITY_LOW_THRESHOLD,
    CONFIDENCE_HIGH_THRESHOLD,
    CONFIDENCE_LOW_THRESHOLD,
    DOMINANCE_MARGIN,
    NEUTRAL_DEFAULT,
    # Defaults
    DEFAULT_SCHEMA_IDS,
)

# Integration
from symbolu.mechanical.pipeline.p33_schema_adaptive.p33_integration import (
    # Singleton
    get_p33_resolver,
    # Integration
    maybe_run_p33,
    run_p33_directly,
    # Helpers
    is_p33_disabled,
    has_p33_snapshot,
    get_p33_snapshot,
    get_dominant_schema,
    get_schema_confidence,
    get_stability_band,
    get_confidence_band,
    is_highly_stable,
    is_low_stability,
    has_dominant_schema,
    get_schema_stability_score,
    get_schema_alignment_score,
    get_schema_drift_score,
    get_p33_version,
)


__all__ = [
    # Version
    "P33_VERSION",
    # Enums
    "SchemaStabilityBand",
    "SchemaConfidenceBand",
    # Constants
    "ALLOWED_SCHEMA_TAGS",
    # Dataclasses
    "SchemaAdaptiveRoutingSnapshot",
    # Helpers
    "create_snapshot",
    "create_empty_snapshot",
    # Resolver
    "P33SchemaAdaptiveResolver",
    # Weights
    "W_COHERENCE_V3",
    "W_COHERENCE_QUALITY",
    "W_DRIFT_INVERSE",
    "W_ENTROPY_INVERSE",
    "W_ALIGN_COHERENCE",
    "W_ALIGN_QUALITY",
    "W_ALIGN_IDENTITY",
    "W_DRIFT_FUSION",
    "W_DRIFT_ENTROPY",
    # Thresholds
    "STABILITY_HIGH_THRESHOLD",
    "STABILITY_LOW_THRESHOLD",
    "CONFIDENCE_HIGH_THRESHOLD",
    "CONFIDENCE_LOW_THRESHOLD",
    "DOMINANCE_MARGIN",
    "NEUTRAL_DEFAULT",
    # Defaults
    "DEFAULT_SCHEMA_IDS",
    # Singleton
    "get_p33_resolver",
    # Integration
    "maybe_run_p33",
    "run_p33_directly",
    # Helper functions
    "is_p33_disabled",
    "has_p33_snapshot",
    "get_p33_snapshot",
    "get_dominant_schema",
    "get_schema_confidence",
    "get_stability_band",
    "get_confidence_band",
    "is_highly_stable",
    "is_low_stability",
    "has_dominant_schema",
    "get_schema_stability_score",
    "get_schema_alignment_score",
    "get_schema_drift_score",
    "get_p33_version",
]
