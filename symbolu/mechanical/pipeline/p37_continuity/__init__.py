"""
P37 Adaptive Continuity Engine Pipeline Integration
=====================================================

Pipeline wrapper for the Adaptive Continuity Engine (ACE) formula.

Phase Authority: PREDICTIVE / READ-ONLY (non-actuating)
Band: Advanced Pipeline (P36-P54)

This phase computes session-wide continuity across narrative, identity,
emotional, and symbolic dimensions. It produces three canonical continuity signals:

- NCC (Narrative Continuity Coefficient): Theme/intent/motivation stability
- ICC (Identity Continuity Coefficient): Identity pattern continuity
- CSS (Continuity Stability Score): Session-wide resilience and alignment

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Tone-level only: NEVER semantic changes (bounded +/-0.015)
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Deterministic: Same inputs -> same outputs always
    - Graceful degradation: Returns None if insufficient data

Usage in orchestrator:
    from .p37_continuity import maybe_run_p37, get_p37_output

    # After P34-P36 stages
    p37_result = maybe_run_p37(ctx)
    if p37_result:
        ctx.p37_continuity = p37_result

Version: 1.0.0
"""

from .p37_continuity_schema import (
    VERSION,
    P37Authority,
    ContinuityBand,
    P37Output,
)

from .p37_integration import (
    extract_p37_signals,
    run_p37_continuity,
    maybe_run_p37,
    get_p37_output,
    get_p37_ncc,
    get_p37_icc,
    get_p37_css,
    get_p37_continuity_band,
)

__all__ = [
    # Schema
    "VERSION",
    "P37Authority",
    "ContinuityBand",
    "P37Output",
    # Integration
    "extract_p37_signals",
    "run_p37_continuity",
    "maybe_run_p37",
    "get_p37_output",
    "get_p37_ncc",
    "get_p37_icc",
    "get_p37_css",
    "get_p37_continuity_band",
]
