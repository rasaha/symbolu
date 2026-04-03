"""
P19 - Drift Fusion

Deterministic, read-only diagnostic synthesis phase that fuses symbolic,
semantic, and temporal drift signals into a unified drift profile.

P19 computes:
- drift_fusion_index: Overall drift severity [0, 1]
- drift_risk_band: Risk classification ("low" / "moderate" / "high")
- drift_pattern_tags: List of detected drift patterns

CRITICAL CONSTRAINTS:
    - Deterministic: Same inputs → same outputs (no LLM, no randomness)
    - Read-only: Does not modify system behavior
    - Non-Invasive: Zero impact on routing, TTOR, MLCR, Fusion, DHA, Renderer
    - Observation-only: Never used for gating, blocking, or behavior modification

    ❌ Must NOT:
        - Infer intent
        - Infer emotion
        - Select regime
        - Gate actions
        - Trigger any side effects

Usage:
    from symbolu_core.mechanical.pipeline.p19_drift_fusion import maybe_run_p19

    # In pipeline after P17 and P18:
    maybe_run_p19(ctx)

    # Access report:
    if ctx.p19 is not None:
        print(f"Drift index: {ctx.p19.drift_fusion_index}")
        print(f"Risk band: {ctx.p19.drift_risk_band}")
        print(f"Tags: {ctx.p19.drift_pattern_tags}")

Direct testing:
    from symbolu_core.mechanical.pipeline.p19_drift_fusion import run_p19_directly

    report = run_p19_directly(
        semantic_integrity_score=0.6,
        cognitive_drift_v3=0.4,
        temporal_entropy_diff=0.55,
        temporal_entropy_volatility=0.3,
        coherence_fused=0.7,
    )

    print(f"Index: {report.drift_fusion_index}")
    print(f"Band: {report.drift_risk_band}")
"""

# Schema exports
from symbolu_core.mechanical.pipeline.p19_drift_fusion.p19_schema import (
    # Version
    P19_VERSION,
    # Enums
    DriftRiskBand,
    DriftPatternTag,
    # Dataclasses
    P19DriftFusionReport,
    # Constants
    W_COGNITIVE_DRIFT,
    W_INTEGRITY,
    W_VOLATILITY,
    W_ENTROPY_SHIFT,
    W_COHERENCE,
    RISK_BAND_LOW_THRESHOLD,
    RISK_BAND_HIGH_THRESHOLD,
    TAG_SEMANTIC_DRIFT_THRESHOLD,
    TAG_COGNITIVE_DRIFT_THRESHOLD,
    TAG_TEMPORAL_INSTABILITY_THRESHOLD,
    TAG_ENTROPY_SHIFT_THRESHOLD,
    TAG_LOW_COHERENCE_THRESHOLD,
    # Helpers
    create_report,
    risk_band_from_index,
)

# Resolver exports
from symbolu_core.mechanical.pipeline.p19_drift_fusion.p19_resolver import (
    P19DriftFusion,
)

# Integration exports
from symbolu_core.mechanical.pipeline.p19_drift_fusion.p19_integration import (
    # Singleton
    get_p19_resolver,
    # Integration
    maybe_run_p19,
    run_p19_directly,
    # Helpers
    is_p19_disabled,
    has_p19_report,
    get_p19_report,
    get_drift_fusion_index,
    get_drift_risk_band,
    get_drift_pattern_tags,
    is_low_risk,
    is_moderate_risk,
    is_high_risk,
    has_semantic_drift,
    has_cognitive_drift,
    has_temporal_instability,
    get_p19_version,
)


__all__ = [
    # Version
    "P19_VERSION",
    # Enums
    "DriftRiskBand",
    "DriftPatternTag",
    # Dataclasses
    "P19DriftFusionReport",
    # Constants
    "W_COGNITIVE_DRIFT",
    "W_INTEGRITY",
    "W_VOLATILITY",
    "W_ENTROPY_SHIFT",
    "W_COHERENCE",
    "RISK_BAND_LOW_THRESHOLD",
    "RISK_BAND_HIGH_THRESHOLD",
    "TAG_SEMANTIC_DRIFT_THRESHOLD",
    "TAG_COGNITIVE_DRIFT_THRESHOLD",
    "TAG_TEMPORAL_INSTABILITY_THRESHOLD",
    "TAG_ENTROPY_SHIFT_THRESHOLD",
    "TAG_LOW_COHERENCE_THRESHOLD",
    # Schema helpers
    "create_report",
    "risk_band_from_index",
    # Resolver
    "P19DriftFusion",
    # Singleton
    "get_p19_resolver",
    # Integration
    "maybe_run_p19",
    "run_p19_directly",
    # Helpers
    "is_p19_disabled",
    "has_p19_report",
    "get_p19_report",
    "get_drift_fusion_index",
    "get_drift_risk_band",
    "get_drift_pattern_tags",
    "is_low_risk",
    "is_moderate_risk",
    "is_high_risk",
    "has_semantic_drift",
    "has_cognitive_drift",
    "has_temporal_instability",
    "get_p19_version",
]
