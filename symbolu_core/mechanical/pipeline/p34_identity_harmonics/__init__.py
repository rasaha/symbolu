"""
P34 Identity Harmonics Layer Pipeline Integration
===================================================

Pipeline wrapper for the Identity Harmonics Layer (IHL) formula.

Phase Authority: OBSERVER (witness-only, non-actuating)
Band: Formula/Consciousness (P25-P35)

This phase computes identity resonance patterns across semantic, emotional,
symbolic, and temporal dimensions. It produces three identity-resonance harmonics:

- CIH (Core Identity Harmonic): Stability of identity signals across turns
- AIH (Adaptive Identity Harmonic): Ability to shift identity expression coherently
- RIH (Relational Identity Harmonic): Resonance between persona tone + symbolic harmonization

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NO changes to routing, TTOR, MLCR, mappers, Fusion, DHA, Renderer
    - Tone-level only: NEVER semantic changes (bounded +/-0.02)
    - Non-invasive: Does not modify any existing coherence formulas or behaviors
    - Deterministic: Same inputs -> same outputs always
    - Graceful degradation: Returns None if core inputs missing

Usage in orchestrator:
    from .p34_identity_harmonics import maybe_run_p34, get_p34_output

    # After P27-P33 stages
    p34_result = maybe_run_p34(ctx)
    if p34_result:
        ctx.p34_identity_harmonics = p34_result

Version: 1.0.0
"""

from .p34_identity_harmonics_schema import (
    VERSION,
    P34Authority,
    P34Output,
)

from .p34_integration import (
    extract_p34_signals,
    run_p34_harmonics,
    maybe_run_p34,
    get_p34_output,
    get_p34_identity_harmonics_index,
    get_p34_stability_score,
    get_p34_flexibility_score,
)

__all__ = [
    # Schema
    "VERSION",
    "P34Authority",
    "P34Output",
    # Integration
    "extract_p34_signals",
    "run_p34_harmonics",
    "maybe_run_p34",
    "get_p34_output",
    "get_p34_identity_harmonics_index",
    "get_p34_stability_score",
    "get_p34_flexibility_score",
]
