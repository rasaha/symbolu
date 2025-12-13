"""
P20 - Unified Cognitive Snapshot

Phase 20 is a read-only aggregation layer that collects outputs from Phases 1-19
into a unified, immutable snapshot for observability, dashboards, audits, and
regression verification.

This module provides:
    - UnifiedCognitiveSnapshot: Immutable dataclass containing all cognitive metrics
    - P20UnifiedSnapshotResolver: Resolver that assembles snapshots from context
    - maybe_run_p20(): Integration function to run P20 in the pipeline

Usage:
    from symbolu.mechanical.pipeline.p20_snapshot import maybe_run_p20

    # In pipeline after P19:
    ctx = maybe_run_p20(ctx)

    # Access snapshot:
    if ctx.phase_20_snapshot is not None:
        print(f"Run ID: {ctx.phase_20_snapshot.run_id}")
        print(f"Coherence v3: {ctx.phase_20_snapshot.coherence_v3}")
        print(f"Drift index: {ctx.phase_20_snapshot.drift_fusion_index}")

CRITICAL CONSTRAINTS:
    - Read-Only: Does NOT modify any upstream state
    - Deterministic: Same inputs always produce same outputs
    - No Computation: No formulas, thresholds, or conditionals
    - No Gating: Does NOT influence routing, intent, regime, discourse, or rendering
    - No Side Effects: Pure observation only
"""

from symbolu.mechanical.pipeline.p20_snapshot.p20_unified_snapshot_schema import (
    P20_VERSION,
    UnifiedCognitiveSnapshot,
    create_snapshot,
)
from symbolu.mechanical.pipeline.p20_snapshot.p20_snapshot_resolver import (
    P20UnifiedSnapshotResolver,
)
from symbolu.mechanical.pipeline.p20_snapshot.p20_integration import (
    get_p20_resolver,
    maybe_run_p20,
    run_p20,
    is_p20_disabled,
    has_p20_snapshot,
    get_p20_snapshot,
    get_p20_version,
)


__all__ = [
    # Version
    "P20_VERSION",
    # Schema
    "UnifiedCognitiveSnapshot",
    "create_snapshot",
    # Resolver
    "P20UnifiedSnapshotResolver",
    # Integration
    "get_p20_resolver",
    "maybe_run_p20",
    "run_p20",
    "is_p20_disabled",
    "has_p20_snapshot",
    "get_p20_snapshot",
    "get_p20_version",
]
