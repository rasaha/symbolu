"""
P32 - Insight Window Gating Pipeline Integration

Integration functions for running P32 within the pipeline.
Provides singleton access and pipeline-friendly entry points.

Usage:
    from symbolu_core.mechanical.pipeline.p32_insight_window import maybe_run_p32

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

from .p32_integration import (
    # Integration
    maybe_run_p32,
    run_p32_directly,
    # Helpers
    is_p32_disabled,
    has_p32_envelope,
    get_p32_envelope,
    get_insight_depth,
    get_confidence_band,
    is_gate_open,
    is_gate_closed,
    has_acoustic_penalty,
    get_reason_codes,
    get_p32_version,
)


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
