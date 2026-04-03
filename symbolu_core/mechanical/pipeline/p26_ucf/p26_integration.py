"""
P26 - Unified Consciousness Formula Integration

Integration functions for running P26 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu_core.mechanical.pipeline.p26_ucf import maybe_run_p26

    # In pipeline after P18/P19/P33:
    maybe_run_p26(ctx)

    # Access UCF state:
    if ctx.p26 is not None:
        print(f"UCF Score: {ctx.p26.ucf_score}")
        print(f"Stability: {ctx.p26.stability_band.value}")

CRITICAL: P26 is observation-only. The state MUST NOT be used for:
    - Routing decisions
    - Regime selection
    - Discourse determination
    - Semantic slot filling
    - Lexical selection
    - Delivery mode selection
    - Any behavioral modification

Invariants:
    - INV-P26-1: UCF is read-only truth, not a decision
    - INV-P26-2: Observer data cannot affect UCF
    - INV-P26-3: UCF monotonic with respect to instability
    - INV-P26-4: UCF never opens gates directly
    - INV-P26-5: Absence of optional inputs never destabilizes output
"""

from __future__ import annotations

from typing import Any, Optional

from agentic.core.consciousness.ucf_schema import (
    P26_VERSION,
    UnifiedConsciousnessState,
    StabilityBand,
    create_neutral_state,
)

from agentic.core.consciousness.ucf_resolver import (
    UCFResolver,
    get_ucf_resolver,
)


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p26(ctx: Any) -> Optional[UnifiedConsciousnessState]:
    """
    Run P26 Unified Consciousness Formula if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P26 should run (not disabled)
    2. Runs the UCF computation
    3. Attaches the state to ctx.p26
    4. Updates coherence_state with UCF metrics (if available)

    P26 is designed to run after P18/P19/P33 and after coherence computation.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The UnifiedConsciousnessState if run, None if skipped

    Note:
        The returned state is observation-only and MUST NOT be used
        for any routing or behavioral decisions.
    """
    # Check if P26 is disabled on this context
    if is_p26_disabled(ctx):
        return None

    # P26 can run with minimal inputs (will use neutral defaults)
    # Skip if ctx has no coherence_state or coherence_state is None
    coherence_state = getattr(ctx, "coherence_state", None)

    if coherence_state is None:
        # Context has no coherence_state, skip P26
        return None

    try:
        # Run the resolver
        resolver = get_ucf_resolver()
        state = resolver.compute(ctx)

        # Attach to context
        _attach_to_context(ctx, state)

        # Update coherence_state with UCF metrics
        _update_coherence_state(ctx, state)

        return state

    except Exception:
        # P26 must not break the pipeline (INV-P26-5)
        # Return neutral state on error
        neutral = create_neutral_state()
        _attach_to_context(ctx, neutral)
        return neutral


def run_p26_directly(
    coherence_v3_quality: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
    entropy_volatility: Optional[float] = None,
    schema_stability: Optional[float] = None,
    identity_harmonics_stability: Optional[float] = None,
) -> UnifiedConsciousnessState:
    """
    Run P26 directly with explicit inputs (for testing).

    This bypasses the context extraction and allows direct testing
    of the UCF formula with explicit values.

    Args:
        coherence_v3_quality: P10/P12 coherence quality [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]
        entropy_volatility: P18 entropy volatility [0.0, 1.0]
        schema_stability: P33 schema stability [0.0, 1.0]
        identity_harmonics_stability: Identity harmonics [0.0, 1.0]

    Returns:
        UnifiedConsciousnessState with computed metrics
    """
    resolver = get_ucf_resolver()
    return resolver.compute_directly(
        coherence_v3_quality=coherence_v3_quality,
        drift_fusion_index=drift_fusion_index,
        entropy_volatility=entropy_volatility,
        schema_stability=schema_stability,
        identity_harmonics_stability=identity_harmonics_stability,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p26_disabled(ctx: Any) -> bool:
    """
    Check if P26 is disabled on this context.

    P26 can be disabled by setting ctx._p26_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P26 is disabled, False otherwise
    """
    return getattr(ctx, "_p26_disabled", False)


def has_p26_state(ctx: Any) -> bool:
    """
    Check if context has a P26 state attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p26 is set and not None
    """
    return getattr(ctx, "p26", None) is not None


def get_p26_state(ctx: Any) -> Optional[UnifiedConsciousnessState]:
    """
    Get the P26 state from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The UnifiedConsciousnessState if present, None otherwise
    """
    return getattr(ctx, "p26", None)


def get_ucf_score(ctx: Any) -> float:
    """
    Get the UCF score from context.

    Convenience function for downstream observability access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        UCF score in [0.0, 1.0], or 0.5 (neutral) if no state
    """
    state = get_p26_state(ctx)
    if state is None:
        return 0.5
    return state.ucf_score


def get_stability_band(ctx: Any) -> StabilityBand:
    """
    Get the stability band from context.

    Convenience function for downstream observability access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        StabilityBand, or TRANSITIONAL if no state
    """
    state = get_p26_state(ctx)
    if state is None:
        return StabilityBand.TRANSITIONAL
    return state.stability_band


def is_stable(ctx: Any) -> bool:
    """
    Check if UCF indicates stable cognitive state.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if stability_band is STABLE, False otherwise
    """
    state = get_p26_state(ctx)
    if state is None:
        return False
    return state.is_stable()


def is_transitional(ctx: Any) -> bool:
    """
    Check if UCF indicates transitional cognitive state.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if stability_band is TRANSITIONAL, False otherwise
    """
    state = get_p26_state(ctx)
    if state is None:
        return True  # Default is transitional when no state
    return state.is_transitional()


def is_unstable(ctx: Any) -> bool:
    """
    Check if UCF indicates unstable cognitive state.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if stability_band is UNSTABLE, False otherwise
    """
    state = get_p26_state(ctx)
    if state is None:
        return False
    return state.is_unstable()


def get_p26_version() -> str:
    """
    Get the current P26 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P26_VERSION


def get_contributing_factors(ctx: Any) -> dict:
    """
    Get the contributing factors from P26 state.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Dictionary of factor names to values, or empty dict if no state
    """
    state = get_p26_state(ctx)
    if state is None:
        return {}
    return dict(state.contributing_factors)


def get_ucf_confidence(ctx: Any) -> float:
    """
    Get the confidence level of the UCF computation.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Confidence in [0.0, 1.0], or 0.0 if no state
    """
    state = get_p26_state(ctx)
    if state is None:
        return 0.0
    return state.confidence


# ============================================================================
# INTERNAL FUNCTIONS
# ============================================================================


def _attach_to_context(ctx: Any, state: UnifiedConsciousnessState) -> None:
    """
    Attach P26 state to context.

    Args:
        ctx: PipelineContext or compatible object
        state: The UCF state to attach
    """
    if hasattr(ctx, "p26"):
        ctx.p26 = state
    else:
        # Context doesn't have p26 attribute, try to set it anyway
        try:
            setattr(ctx, "p26", state)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


def _update_coherence_state(ctx: Any, state: UnifiedConsciousnessState) -> None:
    """
    Update coherence_state with UCF metrics.

    This stores the UCF metrics in the coherence state for observability
    and history tracking purposes.

    Args:
        ctx: PipelineContext with coherence_state
        state: The P26 state to store
    """
    coherence_state = getattr(ctx, "coherence_state", None)
    if coherence_state is None:
        return

    # Update UCF fields in coherence_state if they exist
    # These fields are already defined in CoherenceState

    # Store the full snapshot
    if hasattr(coherence_state, "unified_consciousness_snapshot"):
        coherence_state.unified_consciousness_snapshot = state

    # Store individual metrics
    if hasattr(coherence_state, "current_coi"):
        # Note: P26 doesn't compute COI/CSI/CIP separately
        # We store ucf_score in current_coi for observability
        coherence_state.current_coi = state.ucf_score

    if hasattr(coherence_state, "current_csi"):
        # Use ucf_score as proxy for CSI as well
        coherence_state.current_csi = state.ucf_score

    if hasattr(coherence_state, "current_cip"):
        # Use confidence as proxy for CIP
        coherence_state.current_cip = state.confidence

    if hasattr(coherence_state, "ucf_entropy"):
        # No entropy in this P26 implementation - use confidence instead
        coherence_state.ucf_entropy = 1.0 - state.confidence

    # Append to history
    if hasattr(coherence_state, "ucf_history"):
        coherence_state.ucf_history.append(state)


# Public exports
__all__ = [
    # Integration
    "maybe_run_p26",
    "run_p26_directly",
    # Helpers
    "is_p26_disabled",
    "has_p26_state",
    "get_p26_state",
    "get_ucf_score",
    "get_stability_band",
    "is_stable",
    "is_transitional",
    "is_unstable",
    "get_p26_version",
    "get_contributing_factors",
    "get_ucf_confidence",
]
