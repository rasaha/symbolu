"""
P18 - Temporal Entropy Differential

Deterministic, observation-only phase that computes temporal entropy metrics
to track pipeline state stability over time.

P18 computes:
- entropy_now: Current instability level [0,1]
- entropy_prev: Previous turn's entropy [0,1] if available
- delta_entropy: Change in entropy [-1,+1]
- trend: INCREASING / DECREASING / STABLE / INSUFFICIENT_HISTORY
- volatility_band: LOW / MED / HIGH based on recent deltas

This phase is observation-only: it does not change routing, planner actions,
regime, discourse, or lexical selection. It only stores metrics in
PipelineContext and logs explainability fields.

Usage:
    from symbolu_core.mechanical.pipeline.p18_temporal_entropy import maybe_run_p18

    # In pipeline after P17:
    maybe_run_p18(ctx)

    # Access report:
    if ctx.p18 is not None:
        print(f"Entropy: {ctx.p18.entropy_now}")
        print(f"Trend: {ctx.p18.trend.value}")
        print(f"Volatility: {ctx.p18.volatility_band.value}")
"""

# Schema exports
from symbolu_core.mechanical.pipeline.p18_temporal_entropy.p18_schema import (
    # Version
    P18_VERSION,
    # Enums
    EntropyTrend,
    VolatilityBand,
    # Dataclasses
    P18TemporalEntropyReport,
    # Helpers
    create_report,
)

# Resolver exports
from symbolu_core.mechanical.pipeline.p18_temporal_entropy.p18_resolver import (
    P18TemporalEntropyDifferential,
    # Constants
    W_COHERENCE,
    W_QUALITY,
    W_INTEGRITY,
    W_TENSION,
    W_VOLATILITY,
    EVIDENCE_MISSING_PENALTY,
    TREND_EPSILON,
    VOLATILITY_LOW_THRESHOLD,
    VOLATILITY_HIGH_THRESHOLD,
    DEFAULT_WINDOW_SIZE,
)

# Integration exports
from symbolu_core.mechanical.pipeline.p18_temporal_entropy.p18_integration import (
    # Singleton
    get_p18_resolver,
    # Integration
    maybe_run_p18,
    run_p18_directly,
    # Helpers
    is_p18_disabled,
    has_p18_report,
    get_p18_report,
    get_entropy_now,
    get_entropy_trend,
    get_volatility_band,
    is_entropy_increasing,
    is_entropy_stable,
    is_high_volatility,
    get_p18_version,
)


__all__ = [
    # Version
    "P18_VERSION",
    # Enums
    "EntropyTrend",
    "VolatilityBand",
    # Dataclasses
    "P18TemporalEntropyReport",
    # Schema helpers
    "create_report",
    # Resolver
    "P18TemporalEntropyDifferential",
    # Constants
    "W_COHERENCE",
    "W_QUALITY",
    "W_INTEGRITY",
    "W_TENSION",
    "W_VOLATILITY",
    "EVIDENCE_MISSING_PENALTY",
    "TREND_EPSILON",
    "VOLATILITY_LOW_THRESHOLD",
    "VOLATILITY_HIGH_THRESHOLD",
    "DEFAULT_WINDOW_SIZE",
    # Singleton
    "get_p18_resolver",
    # Integration
    "maybe_run_p18",
    "run_p18_directly",
    # Helpers
    "is_p18_disabled",
    "has_p18_report",
    "get_p18_report",
    "get_entropy_now",
    "get_entropy_trend",
    "get_volatility_band",
    "is_entropy_increasing",
    "is_entropy_stable",
    "is_high_volatility",
    "get_p18_version",
]
