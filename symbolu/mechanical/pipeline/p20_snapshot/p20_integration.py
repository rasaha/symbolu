"""
P20 - Unified Cognitive Snapshot Integration

Integration functions for running P20 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu.mechanical.pipeline.p20_snapshot import maybe_run_p20

    # In pipeline after P19:
    ctx = maybe_run_p20(ctx)

    # Access snapshot:
    if ctx.phase_20_snapshot is not None:
        print(f"Run ID: {ctx.phase_20_snapshot.run_id}")
        print(f"Drift: {ctx.phase_20_snapshot.drift_fusion_index}")

CRITICAL CONSTRAINTS:
    - Read-Only: Does NOT modify any upstream state
    - No Computation: Pure observation only
    - No Gating: Does NOT influence any pipeline behavior
    - No Side Effects: Safe for logging and dashboards
"""

from __future__ import annotations

from typing import Any, Optional

from symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema import (
    P20_VERSION,
    UnifiedCognitiveSnapshot,
)
from symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver import (
    P20UnifiedSnapshotResolver,
)


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_p20_resolver: Optional[P20UnifiedSnapshotResolver] = None


def get_p20_resolver() -> P20UnifiedSnapshotResolver:
    """
    Get the singleton P20UnifiedSnapshotResolver instance.

    Returns:
        The shared P20UnifiedSnapshotResolver instance
    """
    global _p20_resolver
    if _p20_resolver is None:
        _p20_resolver = P20UnifiedSnapshotResolver()
    return _p20_resolver


# ============================================================================
# INTEGRATION FUNCTIONS
# ============================================================================


def maybe_run_p20(ctx: Any) -> Any:
    """
    Run P20 unified snapshot if prerequisites are met.

    This is the main integration entry point. It:
    1. Checks if P20 should run (requires some upstream phases)
    2. Resolves the unified cognitive snapshot
    3. Attaches the snapshot to ctx.phase_20_snapshot
    4. Returns the context (unchanged except for snapshot attachment)

    P20 is designed to run after all other phases (especially P17, P18, P19)
    as it aggregates their outputs.

    IMPORTANT: This function does NOT modify any context state except
    attaching the read-only snapshot. It has no effect on routing, intent,
    regime, discourse, or rendering.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The same context with phase_20_snapshot attached (if run)
    """
    # Check if P20 is disabled on this context
    if is_p20_disabled(ctx):
        return ctx

    # Check if we have any upstream phases to snapshot
    if not _has_any_upstream_data(ctx):
        return ctx

    # Resolve the snapshot
    resolver = get_p20_resolver()
    snapshot = resolver.resolve(ctx)

    # Attach to context
    _attach_snapshot(ctx, snapshot)

    return ctx


def run_p20(ctx: Any) -> UnifiedCognitiveSnapshot:
    """
    Run P20 directly and return the snapshot (for testing).

    This bypasses the context attachment and returns the snapshot directly.
    Useful for testing without modifying context.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        UnifiedCognitiveSnapshot with collected metrics
    """
    resolver = get_p20_resolver()
    return resolver.resolve(ctx)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def is_p20_disabled(ctx: Any) -> bool:
    """
    Check if P20 is disabled on this context.

    P20 can be disabled by setting ctx._p20_disabled = True.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if P20 is disabled, False otherwise
    """
    return getattr(ctx, "_p20_disabled", False)


def has_p20_snapshot(ctx: Any) -> bool:
    """
    Check if context has a P20 snapshot attached.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        True if ctx.phase_20_snapshot is set and not None
    """
    return getattr(ctx, "phase_20_snapshot", None) is not None


def get_p20_snapshot(ctx: Any) -> Optional[UnifiedCognitiveSnapshot]:
    """
    Get the P20 snapshot from context if present.

    Args:
        ctx: PipelineContext or compatible object

    Returns:
        The UnifiedCognitiveSnapshot if present, None otherwise
    """
    return getattr(ctx, "phase_20_snapshot", None)


def get_p20_version() -> str:
    """
    Get the current P20 schema version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return P20_VERSION


def _has_any_upstream_data(ctx: Any) -> bool:
    """
    Check if context has any upstream phase data worth snapshotting.

    P20 can run with minimal data but requires at least some
    pipeline or coherence state information.

    Args:
        ctx: Pipeline context

    Returns:
        True if there's any upstream data, False otherwise
    """
    # Check for coherence state
    if getattr(ctx, "coherence_state", None) is not None:
        return True

    # Check for any phase envelopes
    phase_attrs = [
        "phase_minus_one", "phase_zero", "allowed_actions",
        "po4_proposal", "po5_execution_eligibility", "p6_regime",
        "p7_discourse_envelope", "semantic_frame", "lexical_frame",
        "p10_acoustic", "p11_prosodic_evidence", "p12_consistency",
        "p13_safety_envelope", "p14_surface", "interaction_directive",
        "p16_guard_result", "p17", "p18", "p19",
    ]

    for attr in phase_attrs:
        if getattr(ctx, attr, None) is not None:
            return True

    # Check for MLCR or fusion data
    if getattr(ctx, "mlcr", None) is not None:
        return True
    if getattr(ctx, "fusion", None) is not None:
        return True

    return False


def _attach_snapshot(ctx: Any, snapshot: UnifiedCognitiveSnapshot) -> None:
    """
    Attach the snapshot to context.

    Args:
        ctx: Pipeline context
        snapshot: The snapshot to attach
    """
    if hasattr(ctx, "phase_20_snapshot"):
        ctx.phase_20_snapshot = snapshot
    else:
        try:
            setattr(ctx, "phase_20_snapshot", snapshot)
        except AttributeError:
            # Context is frozen or doesn't allow attribute setting
            pass


# Public exports
__all__ = [
    # Singleton
    "get_p20_resolver",
    # Integration
    "maybe_run_p20",
    "run_p20",
    # Helpers
    "is_p20_disabled",
    "has_p20_snapshot",
    "get_p20_snapshot",
    "get_p20_version",
]
