"""
Phase 50: Cognitive Consistency Regression Pipeline Integration

Integration functions for running P50 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu_core.mechanical.pipeline.p50_cognitive_consistency import (
        maybe_run_p50,
    )

    # In pipeline after P6-P9, P16, P18, P19, P20:
    maybe_run_p50(ctx, history)

    # Access consistency report:
    if ctx.p50_cognitive_consistency is not None:
        print(f"Score: {ctx.p50_cognitive_consistency.consistency_score}")
        print(f"Band: {ctx.p50_cognitive_consistency.consistency_band}")

INPUTS (Read-Only):
    Phase 50 MAY read:
        - ctx.p6_regime (P6 RegimeEnvelope)
        - ctx.p7_discourse_envelope (P7 DiscourseEnvelope)
        - ctx.semantic_frame (P8 SemanticFrame)
        - ctx.lexical_frame (P9 LexicalFrame)
        - ctx.p16_guard_result (P16 Regression Guard)
        - ctx.p18 (P18 Temporal Entropy Differential)
        - ctx.p19_drift_fusion (P19 Drift Fusion Report)
        - ctx.phase_20_snapshot (P20 Unified Cognitive Snapshot)
        - Historical context (previous turn data)

    Phase 50 MUST NOT read:
        - ctx.request (raw user text)
        - ctx.p10_acoustic, p11_prosodic_evidence (acoustic content)
        - ctx.p22_acoustic_witness, p23_alignment_report, p24_projection_report
        - Any P38+ forecast phases

CRITICAL CONSTRAINTS:
    - Must NOT influence regime (P6)
    - Must NOT affect discourse or semantics
    - Must NOT trigger actions
    - Must NOT import observer acoustic phases
    - Must NOT import governance / eligibility code
    - P50 is observer-only: output goes to observability, not behavior

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

from __future__ import annotations

from typing import Any, Optional

from .p50_schema import (
    P50_VERSION,
    CognitiveConsistencyReport,
)
from .p50_analyzer import run_p50_directly


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_p6_regime(ctx: Any) -> Any:
    """
    Extract P6 RegimeEnvelope from context.

    INV-P50-A1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        RegimeEnvelope if present, None otherwise
    """
    return getattr(ctx, "p6_regime", None)


def _extract_p7_discourse(ctx: Any) -> Any:
    """
    Extract P7 DiscourseEnvelope from context.

    INV-P50-A1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        DiscourseEnvelope if present, None otherwise
    """
    return getattr(ctx, "p7_discourse_envelope", None)


def _extract_p8_semantic_frame(ctx: Any) -> Any:
    """
    Extract P8 SemanticFrame from context.

    INV-P50-A1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        SemanticFrame if present, None otherwise
    """
    return getattr(ctx, "semantic_frame", None)


def _extract_p9_lexical_frame(ctx: Any) -> Any:
    """
    Extract P9 LexicalFrame from context.

    INV-P50-A1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        LexicalFrame if present, None otherwise
    """
    return getattr(ctx, "lexical_frame", None)


def _extract_p18_entropy(ctx: Any) -> Any:
    """
    Extract P18 Temporal Entropy report from context.

    INV-P50-A1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        P18TemporalEntropyReport if present, None otherwise
    """
    return getattr(ctx, "p18", None)


def _extract_p19_drift(ctx: Any) -> Any:
    """
    Extract P19 Drift Fusion report from context.

    INV-P50-A1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        P19DriftFusionReport if present, None otherwise
    """
    # Try multiple attribute names for compatibility
    drift = getattr(ctx, "p19_drift_fusion", None)
    if drift is None:
        drift = getattr(ctx, "p19", None)
    return drift


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p50(
    ctx: Any,
    previous_ctx: Optional[Any] = None,
) -> Optional[CognitiveConsistencyReport]:
    """
    Run P50 cognitive consistency regression if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P50 should run
    2. Extracts P6, P7, P8, P9, P18, P19 outputs from context
    3. Extracts previous turn data if available
    4. Runs the consistency computation
    5. Attaches the result to ctx.p50_cognitive_consistency

    P50 is designed to run after P6-P21.
    Returns None if disabled (INV-P50-A4: observer-only).

    INV-P50-A1: We only read from ctx, never modify upstream fields.
    INV-P50-A4: Output is observer-only - only write to p50_cognitive_consistency.
    INV-P50-D1: Same inputs always produce same outputs.

    Args:
        ctx: PipelineContext or compatible object
        previous_ctx: Previous turn's context for historical comparison

    Returns:
        The CognitiveConsistencyReport if run, None if skipped
    """
    # Check if P50 is disabled on this context
    if is_p50_disabled(ctx):
        return None

    # Extract current state
    p6_regime = _extract_p6_regime(ctx)
    p7_discourse = _extract_p7_discourse(ctx)
    p8_semantic_frame = _extract_p8_semantic_frame(ctx)
    p9_lexical_frame = _extract_p9_lexical_frame(ctx)
    p18_entropy = _extract_p18_entropy(ctx)
    p19_drift = _extract_p19_drift(ctx)

    # Extract previous state
    previous_p6_regime = None
    previous_p7_discourse = None
    previous_p8_semantic_frame = None
    previous_p9_lexical_frame = None

    if previous_ctx is not None:
        previous_p6_regime = _extract_p6_regime(previous_ctx)
        previous_p7_discourse = _extract_p7_discourse(previous_ctx)
        previous_p8_semantic_frame = _extract_p8_semantic_frame(previous_ctx)
        previous_p9_lexical_frame = _extract_p9_lexical_frame(previous_ctx)

    # Run the consistency computation
    report = run_p50_directly(
        p6_regime=p6_regime,
        p7_discourse=p7_discourse,
        p8_semantic_frame=p8_semantic_frame,
        p9_lexical_frame=p9_lexical_frame,
        p18_entropy=p18_entropy,
        p19_drift=p19_drift,
        previous_p6_regime=previous_p6_regime,
        previous_p7_discourse=previous_p7_discourse,
        previous_p8_semantic_frame=previous_p8_semantic_frame,
        previous_p9_lexical_frame=previous_p9_lexical_frame,
    )

    if report is None:
        return None

    # Attach to context (observer-only append)
    _attach_report_to_context(ctx, report)

    return report


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p50_disabled(ctx: Any) -> bool:
    """
    Check if P50 is disabled on this context.

    P50 can be disabled by setting ctx._p50_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P50 is disabled, False otherwise
    """
    return getattr(ctx, "_p50_disabled", False)


def has_p50_report(ctx: Any) -> bool:
    """
    Check if context has a P50 report attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p50_cognitive_consistency is set and not None
    """
    return getattr(ctx, "p50_cognitive_consistency", None) is not None


def get_p50_report(ctx: Any) -> Optional[CognitiveConsistencyReport]:
    """
    Get the P50 report from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The CognitiveConsistencyReport if present, None otherwise
    """
    return getattr(ctx, "p50_cognitive_consistency", None)


def get_consistency_score(ctx: Any) -> float:
    """
    Get the consistency score from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Consistency score value, or 1.0 if no report (assume consistent)
    """
    report = get_p50_report(ctx)
    if report is None:
        return 1.0
    return report.consistency_score


def get_consistency_band(ctx: Any) -> str:
    """
    Get the consistency band from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Consistency band string, or "stable" if no report
    """
    report = get_p50_report(ctx)
    if report is None:
        return "stable"
    return report.consistency_band


def get_detected_contradictions(ctx: Any) -> tuple:
    """
    Get detected contradictions from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Tuple of contradiction strings, or empty tuple if no report
    """
    report = get_p50_report(ctx)
    if report is None:
        return ()
    return report.detected_contradictions


def get_regression_flags(ctx: Any) -> tuple:
    """
    Get regression flags from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Tuple of flag strings, or empty tuple if no report
    """
    report = get_p50_report(ctx)
    if report is None:
        return ()
    return report.regression_flags


def get_p50_version() -> str:
    """
    Get the current P50 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P50_VERSION


def _attach_report_to_context(
    ctx: Any,
    report: CognitiveConsistencyReport,
) -> None:
    """
    Attach the P50 report to context.

    This is observer-only: we only append to ctx.p50_cognitive_consistency,
    we do NOT modify any other context fields or influence behavior.

    INV-P50-A1: Only writes to ctx.p50_cognitive_consistency, nothing else.
    INV-P50-A4: Observer-only output.

    Args:
        ctx: PipelineContext
        report: The P50 report to attach
    """
    # Attach to p50_cognitive_consistency attribute
    if hasattr(ctx, "p50_cognitive_consistency"):
        ctx.p50_cognitive_consistency = report
    else:
        try:
            setattr(ctx, "p50_cognitive_consistency", report)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p50",
    "run_p50_directly",
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
