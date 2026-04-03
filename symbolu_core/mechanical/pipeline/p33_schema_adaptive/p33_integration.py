"""
P33 - Schema Adaptive Routing Integration

Integration functions for running P33 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu_core.mechanical.pipeline.p33_schema_adaptive import maybe_run_p33

    # In pipeline after coherence computation:
    maybe_run_p33(ctx)

    # Access snapshot:
    if ctx.p33 is not None:
        print(f"Dominant schema: {ctx.p33.dominant_schema}")
        print(f"Confidence: {ctx.p33.confidence}")

CRITICAL: P33 is observation-only. The snapshot MUST NOT be used for:
- Routing decisions
- Regime selection
- Discourse determination
- Semantic slot filling
- Lexical selection
- Delivery mode selection
- Any behavioral modification

INV-P33-1: Phase 33 cannot influence any decision
INV-P33-2: Schema scores are observational only
INV-P33-3: Dominant schema selection has zero side effects
INV-P33-4: Observer data (P22-P24) cannot enter Phase 33
INV-P33-5: Absence of schema metadata does not break pipeline
"""

from __future__ import annotations

from typing import Any, Dict, FrozenSet, Optional

from symbolu_core.mechanical.pipeline.p33_schema_adaptive.p33_schema_snapshot import (
    SchemaAdaptiveRoutingSnapshot,
    SchemaStabilityBand,
    SchemaConfidenceBand,
    ALLOWED_SCHEMA_TAGS,
    P33_VERSION,
    create_empty_snapshot,
)
from symbolu_core.mechanical.pipeline.p33_schema_adaptive.p33_schema_resolver import (
    P33SchemaAdaptiveResolver,
)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_p33_resolver: Optional[P33SchemaAdaptiveResolver] = None


def get_p33_resolver() -> P33SchemaAdaptiveResolver:
    """
    Get the singleton P33SchemaAdaptiveResolver instance.

    Returns:
        The shared P33SchemaAdaptiveResolver instance
    """
    global _p33_resolver
    if _p33_resolver is None:
        _p33_resolver = P33SchemaAdaptiveResolver()
    return _p33_resolver


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p33(ctx: Any) -> Optional[SchemaAdaptiveRoutingSnapshot]:
    """
    Run P33 schema adaptive routing if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P33 should run (not disabled)
    2. Runs the schema adaptive routing computation
    3. Attaches the snapshot to ctx.p33
    4. Updates coherence_state history if available

    P33 is designed to run after P18/P19 and after coherence computation.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The SchemaAdaptiveRoutingSnapshot if run, None if skipped

    Note:
        The returned snapshot is observation-only and MUST NOT be used
        for any routing or behavioral decisions.
    """
    # Check if P33 is disabled on this context
    if is_p33_disabled(ctx):
        return None

    # P33 can run with minimal inputs (will use neutral defaults)
    # Only skip if ctx has no relevant attributes at all
    has_any_input = hasattr(ctx, "coherence_state")

    if not has_any_input:
        # Context has none of the expected attributes, skip P33
        return None

    try:
        # Run the resolver
        resolver = get_p33_resolver()
        snapshot = resolver.compute(ctx)

        # Attach to context
        if hasattr(ctx, "p33"):
            ctx.p33 = snapshot
        else:
            # Context doesn't have p33 attribute, try to set it anyway
            try:
                setattr(ctx, "p33", snapshot)
            except AttributeError:
                # Context is frozen or doesn't allow attribute setting
                pass

        # Update coherence_state history if available
        _update_coherence_state(ctx, snapshot)

        return snapshot

    except Exception:
        # P33 must not break the pipeline (INV-P33-5)
        # Return empty snapshot on error
        return create_empty_snapshot()


def run_p33_directly(
    coherence_state: Optional[Any] = None,
    persona_schema_metadata: Optional[Any] = None,
) -> SchemaAdaptiveRoutingSnapshot:
    """
    Run P33 directly with explicit inputs (for testing).

    This bypasses the context extraction and allows direct testing
    of the schema adaptive routing with mock objects.

    Args:
        coherence_state: CoherenceState object (optional)
        persona_schema_metadata: PersonaSchemaMetadata object (optional)

    Returns:
        SchemaAdaptiveRoutingSnapshot with computed metrics
    """
    # Create a simple namespace to hold the inputs
    class MockContext:
        pass

    ctx = MockContext()
    ctx.coherence_state = coherence_state
    ctx.persona_schema_metadata = persona_schema_metadata
    ctx.p33 = None  # Add p33 attribute so it can be set

    resolver = get_p33_resolver()
    return resolver.compute(ctx)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p33_disabled(ctx: Any) -> bool:
    """
    Check if P33 is disabled on this context.

    P33 can be disabled by setting ctx._p33_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P33 is disabled, False otherwise
    """
    return getattr(ctx, "_p33_disabled", False)


def has_p33_snapshot(ctx: Any) -> bool:
    """
    Check if context has a P33 snapshot attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.p33 is set and not None
    """
    return getattr(ctx, "p33", None) is not None


def get_p33_snapshot(ctx: Any) -> Optional[SchemaAdaptiveRoutingSnapshot]:
    """
    Get the P33 snapshot from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The SchemaAdaptiveRoutingSnapshot if present, None otherwise
    """
    return getattr(ctx, "p33", None)


def get_dominant_schema(ctx: Any) -> Optional[str]:
    """
    Get the dominant schema from context.

    Convenience function for downstream observability access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Dominant schema ID, or None if no snapshot or no dominant schema
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return None
    return snapshot.dominant_schema


def get_schema_confidence(ctx: Any) -> float:
    """
    Get the schema confidence from context.

    Convenience function for downstream observability access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        Confidence value in [0.0, 1.0], or 0.0 if no snapshot
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return 0.0
    return snapshot.confidence


def get_stability_band(ctx: Any) -> SchemaStabilityBand:
    """
    Get the stability band from context.

    Convenience function for downstream observability access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        SchemaStabilityBand, or UNKNOWN if no snapshot
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return SchemaStabilityBand.UNKNOWN
    return snapshot.stability_band


def get_confidence_band(ctx: Any) -> SchemaConfidenceBand:
    """
    Get the confidence band from context.

    Convenience function for downstream observability access.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        SchemaConfidenceBand, or INSUFFICIENT if no snapshot
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return SchemaConfidenceBand.INSUFFICIENT
    return snapshot.confidence_band


def is_highly_stable(ctx: Any) -> bool:
    """
    Check if schema stability is HIGH.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if stability_band is HIGH, False otherwise
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return False
    return snapshot.is_highly_stable()


def is_low_stability(ctx: Any) -> bool:
    """
    Check if schema stability is LOW.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if stability_band is LOW, False otherwise
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return False
    return snapshot.is_low_stability()


def has_dominant_schema(ctx: Any) -> bool:
    """
    Check if a dominant schema was identified.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if dominant_schema is not None, False otherwise
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return False
    return snapshot.has_dominant_schema()


def get_schema_stability_score(ctx: Any, schema_id: str) -> Optional[float]:
    """
    Get stability score for a specific schema.

    Args:
        ctx: PipelineContext or compatible object
        schema_id: Schema identifier

    Returns:
        Stability score in [0.0, 1.0], or None if not found
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return None
    return snapshot.get_stability_for_schema(schema_id)


def get_schema_alignment_score(ctx: Any, schema_id: str) -> Optional[float]:
    """
    Get alignment score for a specific schema.

    Args:
        ctx: PipelineContext or compatible object
        schema_id: Schema identifier

    Returns:
        Alignment score in [0.0, 1.0], or None if not found
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return None
    return snapshot.get_alignment_for_schema(schema_id)


def get_schema_drift_score(ctx: Any, schema_id: str) -> Optional[float]:
    """
    Get drift score for a specific schema.

    Args:
        ctx: PipelineContext or compatible object
        schema_id: Schema identifier

    Returns:
        Drift score in [0.0, 1.0], or None if not found
    """
    snapshot = get_p33_snapshot(ctx)
    if snapshot is None:
        return None
    return snapshot.get_drift_for_schema(schema_id)


def get_p33_version() -> str:
    """
    Get the current P33 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P33_VERSION


def _update_coherence_state(ctx: Any, snapshot: SchemaAdaptiveRoutingSnapshot) -> None:
    """
    Update coherence_state with P33 metrics.

    This stores the current schema scores in the coherence state
    for observability purposes.

    Args:
        ctx: PipelineContext with coherence_state
        snapshot: The P33 snapshot to store
    """
    coherence_state = getattr(ctx, "coherence_state", None)
    if coherence_state is None:
        return

    # Update persona_schema_* fields if they exist
    if hasattr(coherence_state, "persona_schema_alignment"):
        coherence_state.persona_schema_alignment = dict(snapshot.schema_alignment_scores)

    if hasattr(coherence_state, "persona_schema_confidence"):
        coherence_state.persona_schema_confidence = snapshot.confidence

    if hasattr(coherence_state, "persona_schema_stability"):
        # Compute average stability for scalar field
        if snapshot.schema_stability_scores:
            avg_stability = sum(snapshot.schema_stability_scores.values()) / len(snapshot.schema_stability_scores)
            coherence_state.persona_schema_stability = avg_stability
        else:
            coherence_state.persona_schema_stability = 0.0

    if hasattr(coherence_state, "persona_schema_drift"):
        # Compute average drift for scalar field
        if snapshot.schema_drift_scores:
            avg_drift = sum(snapshot.schema_drift_scores.values()) / len(snapshot.schema_drift_scores)
            coherence_state.persona_schema_drift = avg_drift
        else:
            coherence_state.persona_schema_drift = 0.0


# Public exports
__all__ = [
    # Singleton
    "get_p33_resolver",
    # Integration
    "maybe_run_p33",
    "run_p33_directly",
    # Helpers
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
