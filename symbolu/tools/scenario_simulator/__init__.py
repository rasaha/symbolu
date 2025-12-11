"""
Scenario What-If Simulator - Phase 43

Observation-only, deterministic simulator that applies scenario presets to Phase 42
Scenario Fusion snapshots, recomputes fusion metrics under controlled biases, and
exposes the results via CLI + Unified API.

CRITICAL INVARIANTS:
    - Zero-LLM: Purely rule-based, deterministic math only
    - Observation-only: NEVER modifies live coherence state
    - Deterministic: Same inputs → same outputs always
    - Pure math only: No LLM calls, no side effects
    - Graceful degradation: Returns None if snapshot missing

This module mirrors the structure of Phase 25 (Resonance What-If Simulator) but
operates on Scenario Fusion Engine snapshots instead of Resonance Weighting snapshots.
"""

from .presets import (
    ScenarioPreset,
    get_preset,
    list_presets,
    is_valid_preset,
    get_preset_names,
    get_multiplier,
    PRESETS,
)

from .simulator import (
    SimulatedScenarioResult,
    simulate_scenario_with_preset,
    simulate_all_presets,
    get_simulation_summary,
)

from .cli import (
    print_presets,
    print_simulation_for_session,
    print_comparison_for_session,
)

__all__ = [
    # Presets
    "ScenarioPreset",
    "get_preset",
    "list_presets",
    "is_valid_preset",
    "get_preset_names",
    "get_multiplier",
    "PRESETS",
    # Simulator
    "SimulatedScenarioResult",
    "simulate_scenario_with_preset",
    "simulate_all_presets",
    "get_simulation_summary",
    # CLI
    "print_presets",
    "print_simulation_for_session",
    "print_comparison_for_session",
]
