"""
P26 - Unified Consciousness Formula Pipeline Integration

This module provides pipeline integration for Phase 26: Unified Consciousness
Formula (UCF).

UCF computes a single scalar that answers:
"How internally coherent and stable is the system's cognitive state right now?"

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

UCF is consumed by downstream phases (P32, P35+) for observability,
but never performs gating itself.

Invariants:
    - INV-P26-1: UCF is read-only truth, not a decision
    - INV-P26-2: Observer data cannot affect UCF
    - INV-P26-3: UCF monotonic with respect to instability
    - INV-P26-4: UCF never opens gates directly
    - INV-P26-5: Absence of optional inputs never destabilizes output
"""

from symbolu_core.mechanical.pipeline.p26_ucf.p26_integration import (
    # Integration
    maybe_run_p26,
    run_p26_directly,
    # Helpers
    is_p26_disabled,
    has_p26_state,
    get_p26_state,
    get_ucf_score,
    get_stability_band,
    is_stable,
    is_transitional,
    is_unstable,
    get_p26_version,
)

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
]
