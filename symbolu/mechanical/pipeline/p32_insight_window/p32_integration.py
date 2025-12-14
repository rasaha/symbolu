"""
P32 - Insight Window Gating Integration

Integration functions for running P32 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu.mechanical.pipeline.p32_insight_window import maybe_run_p32

    # In pipeline after P18/P19/P26/P33:
    maybe_run_p32(ctx)

    # Access envelope:
    if ctx.p32 is not None:
        print(f"Is Open: {ctx.p32.is_open}")
        print(f"Depth: {ctx.p32.insight_depth}")

CRITICAL: P32 is observation-only. The envelope MUST NOT be used for:
    - Routing decisions
    - Regime selection
    - Discourse determination
    - Semantic slot filling
    - Lexical selection
    - Delivery mode selection
    - Any behavioral modification

Invariants:
    - INV-P32-1: Insight gating never opens due to observers
    - INV-P32-2: Gate monotonicity enforced
    - INV-P32-3: No upstream influence
    - INV-P32-4: Deterministic behavior
    - INV-P32-5: Envelope is advisory only
"""

from __future__ import annotations

from typing import Any, Optional, Tuple

from symbolu.policy.insight_window import (
    P32_VERSION,
    InsightWindowEnvelope,
    ConfidenceBand,
    get_insight_gating_engine,
    create_closed_envelope,
)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p32(ctx: Any) -> Optional[InsightWindowEnvelope]:
    """
    Run P32 Insight Window Gating if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P32 should run (not disabled)
    2. Runs the insight gating computation
    3. Attaches the envelope to ctx.p32

    P32 is designed to run after P18/P19/P26/P33 and after coherence computation.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The InsightWindowEnvelope if run, None if skipped

    Note:
        The returned envelope is observation-only and MUST NOT be used
        for any routing or behavioral decisions.
    """
    # Check if P32 is disabled on this context
    if is_p32_disabled(ctx):
        return None

    # P32 can run with minimal inputs (will use defaults for missing)
    # Only skip if ctx has no relevant attributes at all
    has_any_input = (
        hasattr(ctx, "coherence_state") or
        hasattr(ctx, "p26") or
        hasattr(ctx, "p33")
    )

    if not has_any_input:
        # Context has none of the expected attributes, skip P32
        return None

    try:
        # Run the engine
        engine = get_insight_gating_engine()
        envelope = engine.compute(ctx)

        # Attach to context
        _attach_to_context(ctx, envelope)

        return envelope

    except Exception:
        # P32 must not break the pipeline (INV-P32-5)
        # Return closed envelope on error
        closed = create_closed_envelope(
            reason="INSUFFICIENT_DATA",
            debug={"error": "computation_failed"},
        )
        _attach_to_context(ctx, closed)
        return closed


def run_p32_directly(
    coherence_v3_quality: Optional[float] = None,
    ucf_score: Optional[float] = None,
    schema_stability: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    temporal_entropy_diff: Optional[float] = None,
    acoustic_alignment_score: Optional[float] = None,
) -> InsightWindowEnvelope:
    """
    Run P32 directly with explicit inputs (for testing).

    This bypasses the context extraction and allows direct testing
    of the insight gating formula with explicit values.

    Args:
        coherence_v3_quality: P10/P12 coherence v3 quality [0.0, 1.0]
        ucf_score: P26 unified consciousness formula score [0.0, 1.0]
        schema_stability: P33 schema stability [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]
        temporal_entropy_diff: P18 temporal entropy differential [0.0, 1.0]
        acoustic_alignment_score: Optional acoustic alignment [0.0, 1.0]

    Returns:
        InsightWindowEnvelope with computed gating decision
    """
    engine = get_insight_gating_engine()
    return engine.compute_directly(
        coherence_v3_quality=coherence_v3_quality,
        ucf_score=ucf_score,
        schema_stability=schema_stability,
        drift_fusion_index=drift_fusion_index,
        temporal_entropy_diff=temporal_entropy_diff,
        acoustic_alignment_score=acoustic_alignment_score,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p32_disabled(ctx: Any) -> bool:
    """
    Check if P32 is disabled on this context.

    P32 can be disabled by setting ctx._p32_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P32 is disabled, False otherwise
    """
    return getattr(ctx, "_p32_disabled", False)


def has_p32_envelope(ctx: Any) -> bool:
    """
    Check if context has a P32 envelope attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p32 is set and not None
    """
    return getattr(ctx, "p32", None) is not None


def get_p32_envelope(ctx: Any) -> Optional[InsightWindowEnvelope]:
    """
    Get the P32 envelope from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The InsightWindowEnvelope if present, None otherwise
    """
    return getattr(ctx, "p32", None)


def get_insight_depth(ctx: Any) -> float:
    """
    Get the insight depth from context.

    Convenience function for downstream observability access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Insight depth in [0.0, 1.0], or 0.0 if no envelope
    """
    envelope = get_p32_envelope(ctx)
    if envelope is None:
        return 0.0
    return envelope.insight_depth


def get_confidence_band(ctx: Any) -> ConfidenceBand:
    """
    Get the confidence band from context.

    Convenience function for downstream observability access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        ConfidenceBand, or LOW if no envelope
    """
    envelope = get_p32_envelope(ctx)
    if envelope is None:
        return ConfidenceBand.LOW
    return envelope.confidence_band


def is_gate_open(ctx: Any) -> bool:
    """
    Check if insight gate is open.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if gate is open (depth >= 0.55), False otherwise
    """
    envelope = get_p32_envelope(ctx)
    if envelope is None:
        return False
    return envelope.is_open


def is_gate_closed(ctx: Any) -> bool:
    """
    Check if insight gate is closed.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if gate is closed, False otherwise
    """
    return not is_gate_open(ctx)


def has_acoustic_penalty(ctx: Any) -> bool:
    """
    Check if an acoustic penalty was applied.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if acoustic penalty was applied, False otherwise
    """
    envelope = get_p32_envelope(ctx)
    if envelope is None:
        return False
    return envelope.has_acoustic_penalty()


def get_reason_codes(ctx: Any) -> Tuple[str, ...]:
    """
    Get the gating reason codes from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Tuple of reason codes, or empty tuple if no envelope
    """
    envelope = get_p32_envelope(ctx)
    if envelope is None:
        return ()
    return envelope.gating_reason_codes


def get_p32_version() -> str:
    """
    Get the current P32 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P32_VERSION


# ============================================================================
# INTERNAL FUNCTIONS
# ============================================================================


def _attach_to_context(ctx: Any, envelope: InsightWindowEnvelope) -> None:
    """
    Attach P32 envelope to context.

    Args:
        ctx: PipelineContext or compatible object
        envelope: The InsightWindowEnvelope to attach
    """
    if hasattr(ctx, "p32"):
        ctx.p32 = envelope
    else:
        # Context doesn't have p32 attribute, try to set it anyway
        try:
            setattr(ctx, "p32", envelope)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p32",
    "run_p32_directly",
    # Helpers
    "is_p32_disabled",
    "has_p32_envelope",
    "get_p32_envelope",
    "get_insight_depth",
    "get_confidence_band",
    "is_gate_open",
    "is_gate_closed",
    "has_acoustic_penalty",
    "get_reason_codes",
    "get_p32_version",
]
