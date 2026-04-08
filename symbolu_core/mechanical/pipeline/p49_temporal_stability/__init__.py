"""
Phase 49: Temporal Stability Index

Final observer-only stability signal before governance (P50+).

Phase 49 answers:
    "How stable is this system over time, as a single interpretable index?"

This is synthesis of temporal signals - not action, not gating, not decision authority.

Usage:
    from symbolu_core.mechanical.pipeline.p49_temporal_stability import (
        maybe_run_p49,
        run_p49_directly,
        TemporalStabilityIndex,
    )

    # In pipeline after P38, P40, P45, P46, P47:
    report = maybe_run_p49(ctx)

    if report is not None:
        print(f"Index: {report.temporal_stability_index}")
        print(f"Band: {report.stability_band}")

Invariants:
    INV-P49-1: Observer-only (no downstream influence)
    INV-P49-2: Deterministic (pure math, no state)
    INV-P49-3: No authority (cannot gate, block, or trigger)
    INV-P49-4: Absence-safe (missing inputs -> None)
    INV-P49-5: Temporal meaning only (index reflects time stability, not intent or emotion)
"""

from .p49_schema import (
    P49_VERSION,
    StabilityBand,
    TemporalStabilityIndex,
    create_temporal_stability_index,
    VALID_STABILITY_BANDS,
    STABLE_THRESHOLD,
    STRAINED_THRESHOLD,
    W_FORECAST,
    W_HORIZON,
    W_TRAJECTORY,
    W_CONVERGENCE,
    W_ALIGNMENT,
)

from .p49_index import (
    compute_temporal_stability,
    run_p49_directly,
)

from .p49_integration import (
    maybe_run_p49,
    is_p49_disabled,
    has_p49_stability_index,
    get_p49_stability_index,
    get_temporal_stability_index,
    get_stability_band,
    get_p49_version,
)


__all__ = [
    # Schema
    "P49_VERSION",
    "StabilityBand",
    "TemporalStabilityIndex",
    "create_temporal_stability_index",
    "VALID_STABILITY_BANDS",
    # Thresholds
    "STABLE_THRESHOLD",
    "STRAINED_THRESHOLD",
    # Weights
    "W_FORECAST",
    "W_HORIZON",
    "W_TRAJECTORY",
    "W_CONVERGENCE",
    "W_ALIGNMENT",
    # Engine
    "compute_temporal_stability",
    "run_p49_directly",
    # Integration
    "maybe_run_p49",
    "is_p49_disabled",
    "has_p49_stability_index",
    "get_p49_stability_index",
    "get_temporal_stability_index",
    "get_stability_band",
    "get_p49_version",
]
