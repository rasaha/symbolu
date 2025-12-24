"""
P28 Delivery Harmonization Phase
==================================

Formal phase wrapper for DHA Engine within the
Delivery Adaptation Band (P27-P31).

Phase Authority: MEDIUM (HIGH for safety-critical decisions)
Band Position: P28 (Second in Delivery Adaptation Band)

Usage:
    from symbolu.mechanical.pipeline.p28_dha import (
        maybe_run_p28,
        get_p28_output,
        get_p28_guarded_text,
        get_p28_tone_profile,
    )

    # In orchestrator (after P27)
    p28_result = maybe_run_p28(ctx, p27_output=ctx.p27_persona)
    if p28_result:
        ctx.p28_dha = p28_result
"""

from .p28_dha_schema import (
    VERSION,
    P28Authority,
    DeliveryProfileType,
    ReadinessLevel,
    ResistanceLevel,
    SafetyStatus,
    P28InputSignals,
    P28ToneProfile,
    P28SafetyResult,
    P28Output,
)

from .p28_integration import (
    get_dha_engine,
    get_tone_selector,
    get_readiness_analyzer,
    get_resistance_detector,
    get_safety_filters,
    extract_p28_signals,
    run_p28_adaptation,
    maybe_run_p28,
    get_p28_output,
    get_p28_guarded_text,
    get_p28_tone_profile,
)

__version__ = VERSION
__all__ = [
    # Schema
    "VERSION",
    "P28Authority",
    "DeliveryProfileType",
    "ReadinessLevel",
    "ResistanceLevel",
    "SafetyStatus",
    "P28InputSignals",
    "P28ToneProfile",
    "P28SafetyResult",
    "P28Output",
    # Integration
    "get_dha_engine",
    "get_tone_selector",
    "get_readiness_analyzer",
    "get_resistance_detector",
    "get_safety_filters",
    "extract_p28_signals",
    "run_p28_adaptation",
    "maybe_run_p28",
    "get_p28_output",
    "get_p28_guarded_text",
    "get_p28_tone_profile",
]
