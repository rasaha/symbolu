"""
DHA Engine v3.0 - Delivery Harmonization & Adaptation Engine
=============================================================

Main module for determining HOW the system should deliver responses to users.

Core Components:
    - DHAEngine: Main orchestrator
    - ToneSelector: Chooses delivery profile
    - DeliveryModulator: Transforms messages
    - ReadinessAnalyzer: Assesses user readiness
    - ResistanceDetector: Detects resistance patterns
    - SafetyFilters: Applies safety guardrails

Delivery Profiles:
    - SWEET_RESONANCE: Gentle, supportive tone for receptive users
    - INVERSE_JOLT: Direct approach to break through resistance
    - SYMBOLIC_METAPHOR: Indirect, metaphorical framing

Usage:
    from symbolu.mechanical.dha import DHAEngine

    engine = DHAEngine()
    result = engine.run(
        renderer_output={"text": "Your message here"},
        metadata={
            "readiness_score": 0.7,
            "resistance_score": 0.3,
            "emotional_entropy": 0.4
        }
    )
    print(result.adapted_message)

Integration:
    The DHA Engine sits after FusionRenderer in the pipeline:
    FusionEngine -> PersonaEngine -> FusionRenderer -> DHAEngine -> Output
"""

from mechanical.dha.dha_engine import (
    DHAEngine,
    DHAInput,
    DHAOutput,
    run_dha,
    adapt_message
)
from mechanical.dha.adaptation_rules import (
    DeliveryProfile,
    Level
)
from mechanical.dha.tone_selector import (
    ToneSelector,
    select_tone,
    get_delivery_profile
)
from mechanical.dha.delivery_modulator import (
    DeliveryModulator,
    modulate_delivery,
    get_adapted_message
)
from mechanical.dha.readiness_analyzer import (
    ReadinessAnalyzer,
    analyze_readiness,
    get_readiness_level
)
from mechanical.dha.resistance_detector import (
    ResistanceDetector,
    detect_resistance,
    get_resistance_level
)
from mechanical.dha.safety_filters import (
    SafetyFilters,
    filter_text,
    is_text_safe,
    get_safe_text
)

__version__ = "3.0.0"
__author__ = "Symbol-U AGI"

__all__ = [
    # Main engine
    "DHAEngine",
    "DHAInput",
    "DHAOutput",
    "run_dha",
    "adapt_message",
    # Enums
    "DeliveryProfile",
    "Level",
    # Tone selection
    "ToneSelector",
    "select_tone",
    "get_delivery_profile",
    # Delivery modulation
    "DeliveryModulator",
    "modulate_delivery",
    "get_adapted_message",
    # Readiness analysis
    "ReadinessAnalyzer",
    "analyze_readiness",
    "get_readiness_level",
    # Resistance detection
    "ResistanceDetector",
    "detect_resistance",
    "get_resistance_level",
    # Safety filters
    "SafetyFilters",
    "filter_text",
    "is_text_safe",
    "get_safe_text",
]
