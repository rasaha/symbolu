"""
P41 - Coherence-Regime Scenario Mapper Pipeline Integration

Integration functions for running P41 within the pipeline.
Provides pipeline-friendly entry points and context extraction.

Usage:
    from symbolu.mechanical.pipeline.p41_scenario_regime_mapper import maybe_run_p41

    # In pipeline after P40:
    maybe_run_p41(ctx)

    # Access scenario regime map:
    if ctx.p41_scenario_regime_map is not None:
        print(f"Regime: {ctx.p41_scenario_regime_map.scenario_regime}")
        print(f"Confidence: {ctx.p41_scenario_regime_map.confidence}")
        print(f"Signals: {ctx.p41_scenario_regime_map.supporting_signals}")

INPUTS (Read-Only):
    Phase 41 MAY read:
        - Phase 10 Coherence v3 score (ctx.coherence_state.coherence_score_v3)
        - Phase 12 Coherence v3 Quality (ctx.coherence_state.coherence_v3_quality)
        - Phase 19 Drift Fusion Report (ctx.p19.drift_fusion_index)
        - Phase 40 Cross-Horizon Alignment (ctx.p40_cross_horizon_alignment.alignment_score)

    Phase 41 MUST NOT read:
        - Raw user text
        - Semantics, intent, discourse, lexical frames
        - Acoustic / vrtti / kosha data
        - Any governance or eligibility phase (>=50)

CRITICAL CONSTRAINTS:
    - Must NOT change regime, discourse, semantics, or lexical selection
    - Must NOT influence DHA, Persona Engine, Renderer
    - Must NOT influence insight gating (P32)
    - Must NOT infer intent or emotion
    - Must NOT gate actions or trigger side effects
    - Must NOT choose actions or recommend paths

INVARIANTS:
    - INV-P41-1: Observer-only (no influence on regimes, discourse, routing, or action)
    - INV-P41-2: Deterministic (same inputs -> same outputs)
    - INV-P41-3: Scenario labels only (no probabilities, no forecasts, no optimization)
    - INV-P41-4: Monotonic consistency (lower coherence / alignment cannot yield "better" regimes)
    - INV-P41-5: Absence-safe (missing optional inputs degrade confidence, never improve it)
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu.mechanical.pipeline.p41_scenario_regime_mapper.p41_schema import (
    ScenarioRegimeMap,
    P41_VERSION,
)
from symbolu.mechanical.pipeline.p41_scenario_regime_mapper.p41_mapper import (
    resolve_scenario_regime,
)


# ============================================================================
# SIGNAL EXTRACTION
# ============================================================================


def _extract_coherence_v3_quality(ctx: Any) -> Optional[float]:
    """
    Extract Phase 12 coherence v3 quality from context.

    Reads from:
    - ctx.coherence_state.coherence_v3_quality (primary)

    INV-P41-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Coherence v3 quality in [0.0, 1.0], or None if unavailable
    """
    if hasattr(ctx, "coherence_state") and ctx.coherence_state is not None:
        quality = getattr(ctx.coherence_state, "coherence_v3_quality", None)
        if quality is not None:
            return float(quality)

    return None


def _extract_alignment_score(ctx: Any) -> Optional[float]:
    """
    Extract Phase 40 alignment score from context.

    Reads from:
    - ctx.p40_cross_horizon_alignment.alignment_score (primary)

    INV-P41-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Alignment score in [0.0, 1.0], or None if unavailable
    """
    if (
        hasattr(ctx, "p40_cross_horizon_alignment")
        and ctx.p40_cross_horizon_alignment is not None
    ):
        score = getattr(ctx.p40_cross_horizon_alignment, "alignment_score", None)
        if score is not None:
            return float(score)

    return None


def _extract_drift_fusion_index(ctx: Any) -> Optional[float]:
    """
    Extract Phase 19 drift fusion index from context.

    Reads from:
    - ctx.p19.drift_fusion_index (primary)

    INV-P41-1: We read this value but NEVER modify it.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Drift fusion index in [0.0, 1.0], or None if unavailable
    """
    if hasattr(ctx, "p19") and ctx.p19 is not None:
        dfi = getattr(ctx.p19, "drift_fusion_index", None)
        if dfi is not None:
            return float(dfi)

    return None


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p41(ctx: Any) -> Optional[ScenarioRegimeMap]:
    """
    Run P41 scenario regime mapping if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P41 should run
    2. Extracts input signals from context (all optional)
    3. Runs the scenario mapping computation
    4. Attaches the result to ctx.p41_scenario_regime_map

    P41 is designed to run after P40 (cross-horizon alignment).
    All inputs are optional - missing inputs degrade confidence.

    INV-P41-1: Observer-only - we only write to ctx.p41_scenario_regime_map.
    INV-P41-2: Deterministic - same inputs always produce same outputs.
    INV-P41-5: Absence-safe - missing inputs cannot improve classification.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The ScenarioRegimeMap if run, None if skipped
    """
    # Check if P41 is disabled on this context
    if is_p41_disabled(ctx):
        return None

    # Extract input signals (all optional)
    coherence_v3_quality = _extract_coherence_v3_quality(ctx)
    alignment_score = _extract_alignment_score(ctx)
    drift_fusion_index = _extract_drift_fusion_index(ctx)

    # Run the resolver
    scenario_map = resolve_scenario_regime(
        coherence_v3_quality=coherence_v3_quality,
        alignment_score=alignment_score,
        drift_fusion_index=drift_fusion_index,
    )

    if scenario_map is None:
        return None

    # Attach to context (observer-only append)
    _attach_scenario_map_to_context(ctx, scenario_map)

    return scenario_map


def run_p41_directly(
    coherence_v3_quality: Optional[float] = None,
    alignment_score: Optional[float] = None,
    drift_fusion_index: Optional[float] = None,
) -> Optional[ScenarioRegimeMap]:
    """
    Run P41 directly with explicit inputs (for testing).

    This bypasses context extraction and allows direct testing
    with mock values.

    INV-P41-2: Deterministic - same inputs always produce same outputs.

    Args:
        coherence_v3_quality: P12 coherence v3 quality [0.0, 1.0]
        alignment_score: P40 alignment score [0.0, 1.0]
        drift_fusion_index: P19 drift fusion index [0.0, 1.0]

    Returns:
        ScenarioRegimeMap if computation succeeds, None otherwise
    """
    return resolve_scenario_regime(
        coherence_v3_quality=coherence_v3_quality,
        alignment_score=alignment_score,
        drift_fusion_index=drift_fusion_index,
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p41_disabled(ctx: Any) -> bool:
    """
    Check if P41 is disabled on this context.

    P41 can be disabled by setting ctx._p41_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P41 is disabled, False otherwise
    """
    return getattr(ctx, "_p41_disabled", False)


def has_p41_scenario_map(ctx: Any) -> bool:
    """
    Check if context has a P41 scenario map attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p41_scenario_regime_map is set and not None
    """
    return getattr(ctx, "p41_scenario_regime_map", None) is not None


def get_p41_scenario_map(ctx: Any) -> Optional[ScenarioRegimeMap]:
    """
    Get the P41 scenario map from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The ScenarioRegimeMap if present, None otherwise
    """
    return getattr(ctx, "p41_scenario_regime_map", None)


def get_scenario_regime(ctx: Any) -> str:
    """
    Get the scenario regime from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Scenario regime string, or "ambiguous_mixed" if no map
    """
    scenario_map = get_p41_scenario_map(ctx)
    if scenario_map is None:
        return "ambiguous_mixed"
    return scenario_map.scenario_regime


def get_regime_confidence(ctx: Any) -> float:
    """
    Get the regime confidence from context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Confidence score in [0.0, 1.0], or 0.5 if no map
    """
    scenario_map = get_p41_scenario_map(ctx)
    if scenario_map is None:
        return 0.5
    return scenario_map.confidence


def is_stable_regime(ctx: Any) -> bool:
    """
    Check if the scenario regime is stable_continuity.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if regime is stable_continuity, False otherwise
    """
    scenario_map = get_p41_scenario_map(ctx)
    if scenario_map is None:
        return False
    return scenario_map.is_stable()


def is_divergent_regime(ctx: Any) -> bool:
    """
    Check if the scenario regime is divergent_instability.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if regime is divergent_instability, False otherwise
    """
    scenario_map = get_p41_scenario_map(ctx)
    if scenario_map is None:
        return False
    return scenario_map.is_divergent()


def get_p41_version() -> str:
    """
    Get the current P41 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P41_VERSION


def _attach_scenario_map_to_context(
    ctx: Any,
    scenario_map: ScenarioRegimeMap,
) -> None:
    """
    Attach the P41 scenario map to context.

    This is observer-only: we only append to ctx.p41_scenario_regime_map,
    we do NOT modify any other context fields or influence behavior.

    INV-P41-1: Only writes to ctx.p41_scenario_regime_map, nothing else.

    Args:
        ctx: PipelineContext
        scenario_map: The P41 scenario map to attach
    """
    # Attach to p41_scenario_regime_map attribute
    if hasattr(ctx, "p41_scenario_regime_map"):
        ctx.p41_scenario_regime_map = scenario_map
    else:
        try:
            setattr(ctx, "p41_scenario_regime_map", scenario_map)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Integration
    "maybe_run_p41",
    "run_p41_directly",
    # Helpers
    "is_p41_disabled",
    "has_p41_scenario_map",
    "get_p41_scenario_map",
    "get_scenario_regime",
    "get_regime_confidence",
    "is_stable_regime",
    "is_divergent_regime",
    "get_p41_version",
]
