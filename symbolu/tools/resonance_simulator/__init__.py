"""
Resonance Scenario Presets & What-If Simulator v1.0 - Phase 25

Zero-LLM, deterministic "what-if" simulator for Phase 24 Resonance Weighting Function (RWF).

This module provides:
  • Named resonance presets (safety_first, insight_heavy, identity_careful, etc.)
  • What-if simulation on UnifiedOutput/SessionSummary/UnifiedSessionAnalytics
  • Read-only analytics and diagnostics

CRITICAL:
    - Zero-LLM: Purely deterministic math
    - Observation-only: NO changes to pipeline behavior, routing, mappers, coherence
    - Non-invasive: Does not modify live state or policy flags
    - Backward-compatible: All existing tests remain green
"""

from .presets import ResonancePreset, PRESETS, get_preset, list_presets, is_valid_preset
from .simulator import (
    SimulatedResonanceScenario,
    simulate_resonance_with_preset,
    simulate_all_presets,
)

__all__ = [
    "ResonancePreset",
    "PRESETS",
    "get_preset",
    "list_presets",
    "is_valid_preset",
    "SimulatedResonanceScenario",
    "simulate_resonance_with_preset",
    "simulate_all_presets",
]
