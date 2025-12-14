"""
Phase 50: Cognitive Consistency Regression

P50 is the first phase in the final governance band.
It evaluates whether cognition has remained internally consistent over time.

P50 is non-actuating: it observes but does not act.

It answers only one question:
    "Is the system contradicting itself compared to its own prior cognitive state?"

P50 is self-reflection without self-control.
It witnesses contradiction, but never corrects it.

Usage:
    from symbolu.mechanical.pipeline.p50_cognitive_consistency import (
        maybe_run_p50,
        CognitiveConsistencyReport,
        get_consistency_score,
        get_consistency_band,
    )

    # Run P50 in pipeline
    report = maybe_run_p50(ctx, previous_ctx)

    # Access results
    if report is not None:
        print(f"Score: {report.consistency_score}")
        print(f"Band: {report.consistency_band}")
        print(f"Contradictions: {report.detected_contradictions}")

INVARIANTS:
    INV-P50-A1: P50 cannot modify any upstream phase output
    INV-P50-A2: P50 cannot gate any action or delivery
    INV-P50-A3: P50 cannot be read by P6-P21
    INV-P50-A4: P50 output is observer-only
    INV-P50-D1: Same history + same input -> same report (bitwise)
    INV-P50-D2: No randomness, no thresholds learned at runtime
    INV-P50-S1: No semantic reinterpretation
    INV-P50-S2: No acoustic interpretation
    INV-P50-S3: No persona influence
"""

from .p50_schema import (
    # Version
    P50_VERSION,
    # Type Aliases
    ConsistencyBand,
    # Constants
    VALID_CONSISTENCY_BANDS,
    STABLE_THRESHOLD,
    STRAINED_THRESHOLD,
    W_REGIME_STABILITY,
    W_DISCOURSE_CONTINUITY,
    W_SEMANTIC_PRESERVATION,
    W_LEXICAL_POLARITY,
    W_DRIFT_ENTROPY,
    # Dataclasses
    CognitiveConsistencyReport,
    # Factory
    create_cognitive_consistency_report,
)

from .p50_analyzer import (
    compute_cognitive_consistency,
    run_p50_directly,
)

from .p50_integration import (
    # Integration
    maybe_run_p50,
    # Helpers
    is_p50_disabled,
    has_p50_report,
    get_p50_report,
    get_consistency_score,
    get_consistency_band,
    get_detected_contradictions,
    get_regression_flags,
    get_p50_version,
)


__all__ = [
    # Version
    "P50_VERSION",
    # Type Aliases
    "ConsistencyBand",
    # Constants
    "VALID_CONSISTENCY_BANDS",
    "STABLE_THRESHOLD",
    "STRAINED_THRESHOLD",
    "W_REGIME_STABILITY",
    "W_DISCOURSE_CONTINUITY",
    "W_SEMANTIC_PRESERVATION",
    "W_LEXICAL_POLARITY",
    "W_DRIFT_ENTROPY",
    # Dataclasses
    "CognitiveConsistencyReport",
    # Factory
    "create_cognitive_consistency_report",
    # Core computation
    "compute_cognitive_consistency",
    "run_p50_directly",
    # Integration
    "maybe_run_p50",
    # Helpers
    "is_p50_disabled",
    "has_p50_report",
    "get_p50_report",
    "get_consistency_score",
    "get_consistency_band",
    "get_detected_contradictions",
    "get_regression_flags",
    "get_p50_version",
]
