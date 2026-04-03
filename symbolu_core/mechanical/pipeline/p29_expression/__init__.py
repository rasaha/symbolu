"""
P29 Expression Finalization Phase
===================================

Final linguistic polish and expression optimization after DHA.
Integrates existing modules:

- VarnaHybridRenderer: Phoneme-based rhythm optimization
- StyleModifiers: Tone-based style application
- Resonance analysis: Bridge meanings and harmony

Phase Authority: LOW
Band Position: P29 (Third in Delivery Adaptation Band)

Purpose:
    - Sentence rhythm optimization via Varṇa phoneme analysis
    - Word choice refinement using bridge meanings
    - Style modifications based on persona/delivery profile

Usage:
    from symbolu_core.mechanical.pipeline.p29_expression import (
        maybe_run_p29,
        get_p29_output,
        get_p29_final_text,
    )

    # In orchestrator (after P28)
    p29_result = maybe_run_p29(ctx)
    if p29_result:
        ctx.p29_expression = p29_result
"""

from .p29_expression_schema import (
    VERSION,
    P29Authority,
    PolishMode,
    RhythmQuality,
    P29InputSignals,
    P29PhonemeAnalysis,
    P29StyleModifications,
    P29Output,
)

from .p29_integration import (
    get_varna_renderer,
    get_style_modifiers,
    extract_p29_signals,
    run_phoneme_analysis,
    apply_style_modifications,
    run_p29_finalization,
    maybe_run_p29,
    get_p29_output,
    get_p29_final_text,
    HAS_VARNA,
    HAS_STYLE,
    HAS_RESONANCE,
)

# New modules (Phase 1 & 2 implementation)
from .phoneme_harmony_engine import (
    TransitionQuality,
    PhonemeClass,
    WordPhonemes,
    WordTransition,
    HarmonyAnalysis,
    PhonemeHarmonyEngine,
    get_phoneme_harmony_engine,
    analyze_harmony,
    HAS_RESONANCE as HARMONY_HAS_RESONANCE,
)

PHASE_STATUS = "implemented"

__version__ = VERSION
__all__ = [
    # Schema
    "VERSION",
    "P29Authority",
    "PolishMode",
    "RhythmQuality",
    "P29InputSignals",
    "P29PhonemeAnalysis",
    "P29StyleModifications",
    "P29Output",
    # Integration
    "get_varna_renderer",
    "get_style_modifiers",
    "extract_p29_signals",
    "run_phoneme_analysis",
    "apply_style_modifications",
    "run_p29_finalization",
    "maybe_run_p29",
    "get_p29_output",
    "get_p29_final_text",
    # Phoneme Harmony Engine
    "TransitionQuality",
    "PhonemeClass",
    "WordPhonemes",
    "WordTransition",
    "HarmonyAnalysis",
    "PhonemeHarmonyEngine",
    "get_phoneme_harmony_engine",
    "analyze_harmony",
    "HARMONY_HAS_RESONANCE",
    # Feature flags
    "HAS_VARNA",
    "HAS_STYLE",
    "HAS_RESONANCE",
    "PHASE_STATUS",
]
