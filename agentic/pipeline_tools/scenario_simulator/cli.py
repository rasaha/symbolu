"""
Scenario Simulator CLI Tools - Phase 43

Command-line interface for running scenario what-if simulations on sessions.

This module provides read-only diagnostic tools for exploring scenario fusion
what-if scenarios without modifying any live pipeline state.
"""

from typing import Optional
import sys

from symbolu_core.service.sessions.session_store import SessionStore
from symbolu_core.formulas.scenario_fusion_engine import ScenarioFusionSnapshot
from .presets import get_preset, list_presets, is_valid_preset, get_preset_names
from .simulator import (
    simulate_scenario_with_preset,
    simulate_all_presets,
    get_simulation_summary,
)


def print_presets() -> None:
    """
    Print all available scenario presets with descriptions.

    This is a read-only informational function.
    """
    presets = list_presets()

    print("=" * 70)
    print("Available Scenario Presets")
    print("=" * 70)
    print()

    for preset_name in sorted(presets.keys()):
        preset = presets[preset_name]
        print(f"[{preset_name}]")
        print(f"  Description: {preset.description}")
        print(f"  Multipliers:")
        print(f"    - alignment_multiplier:    {preset.alignment_multiplier:.2f}x")
        print(f"    - divergence_multiplier:   {preset.divergence_multiplier:.2f}x")
        print(f"    - consensus_multiplier:    {preset.consensus_multiplier:.2f}x")
        print(f"    - uncertainty_multiplier:  {preset.uncertainty_multiplier:.2f}x")
        print(f"    - path_shift_bias:         {preset.path_shift_bias:+.2f}")
        print()


def _extract_scenario_snapshot(
    session_store: SessionStore, session_id: str
) -> Optional[ScenarioFusionSnapshot]:
    """
    Extract the latest scenario fusion snapshot from a session.

    Args:
        session_store: SessionStore instance
        session_id: Session identifier

    Returns:
        ScenarioFusionSnapshot if available, None otherwise
    """
    session = session_store.get(session_id)
    if session is None:
        return None

    # Look for latest scenario fusion snapshot in coherence history
    if not session.coherence_history:
        return None

    # Check most recent coherence state
    for coherence_dict in reversed(session.coherence_history):
        if not isinstance(coherence_dict, dict):
            continue

        # Check for scenario_fusion_snapshot
        if "scenario_fusion_snapshot" in coherence_dict:
            snapshot = coherence_dict["scenario_fusion_snapshot"]
            if snapshot is not None:
                return snapshot

    return None


def print_simulation_for_session(
    session_id: str,
    preset_name: str,
    session_store: Optional[SessionStore] = None,
) -> None:
    """
    Print scenario simulation results for a specific session and preset.

    Args:
        session_id: Session identifier
        preset_name: Preset to apply
        session_store: SessionStore instance (optional, will create if None)
    """
    if session_store is None:
        session_store = SessionStore()

    print("=" * 70)
    print(f"Scenario Simulation for Session: {session_id}")
    print("=" * 70)
    print()

    # Validate preset
    if not is_valid_preset(preset_name):
        available = ", ".join(get_preset_names())
        print(f"ERROR: Invalid preset '{preset_name}'")
        print(f"Available presets: {available}")
        return

    # Retrieve session
    session = session_store.get(session_id)
    if session is None:
        print(f"ERROR: Session '{session_id}' not found")
        return

    # Extract scenario snapshot
    snapshot = _extract_scenario_snapshot(session_store, session_id)
    if snapshot is None:
        print("ERROR: No scenario fusion snapshot available for this session")
        print("(Session may not have any turns with scenario fusion computed)")
        return

    # Get preset and run simulation
    preset = get_preset(preset_name)
    result = simulate_scenario_with_preset(snapshot, preset)

    if result is None:
        print(f"ERROR: Simulation failed")
        return

    # Print results
    print(get_simulation_summary(result))
    print()


def print_comparison_for_session(
    session_id: str,
    session_store: Optional[SessionStore] = None,
) -> None:
    """
    Print scenario simulation comparison across all presets for a session.

    Args:
        session_id: Session identifier
        session_store: SessionStore instance (optional, will create if None)
    """
    if session_store is None:
        session_store = SessionStore()

    print("=" * 70)
    print(f"Scenario Preset Comparison for Session: {session_id}")
    print("=" * 70)
    print()

    # Retrieve session
    session = session_store.get(session_id)
    if session is None:
        print(f"ERROR: Session '{session_id}' not found")
        return

    # Extract scenario snapshot
    snapshot = _extract_scenario_snapshot(session_store, session_id)
    if snapshot is None:
        print("ERROR: No scenario fusion snapshot available for this session")
        print("(Session may not have any turns with scenario fusion computed)")
        return

    # Run all simulations
    results = simulate_all_presets(snapshot)

    if not results:
        print("ERROR: No valid simulations could be run")
        return

    # Print original state first
    print("ORIGINAL STATE (no preset)")
    print("-" * 70)
    print(f"Alignment:   {snapshot.scenario_alignment_score:.3f}")
    print(f"Divergence:  {snapshot.scenario_divergence_index:.3f}")
    print(f"Consensus:   {snapshot.multi_regime_consensus:.3f}")
    print(f"Uncertainty: {snapshot.future_uncertainty_band}")
    print(f"Dominant:    {snapshot.dominant_future_path}")
    print()
    print()

    # Print each preset's results
    for preset_name in sorted(results.keys()):
        result = results[preset_name]

        print(f"PRESET: {preset_name}")
        print("-" * 70)
        print(get_simulation_summary(result))
        print()
        print()


def main() -> None:
    """
    Main CLI entry point for scenario simulator.

    Usage:
        python -m symbolu.tools.scenario_simulator.cli list-presets
        python -m symbolu.tools.scenario_simulator.cli simulate <session_id> <preset_name>
        python -m symbolu.tools.scenario_simulator.cli compare <session_id>
    """
    args = sys.argv[1:]

    if len(args) == 0:
        print("Usage:")
        print("  python -m symbolu.tools.scenario_simulator.cli list-presets")
        print("  python -m symbolu.tools.scenario_simulator.cli simulate <session_id> <preset_name>")
        print("  python -m symbolu.tools.scenario_simulator.cli compare <session_id>")
        sys.exit(1)

    command = args[0]

    if command == "list-presets":
        print_presets()

    elif command == "simulate":
        if len(args) < 3:
            print("ERROR: Missing arguments for simulate command")
            print("Usage: simulate <session_id> <preset_name>")
            sys.exit(1)

        session_id = args[1]
        preset_name = args[2]

        # Note: In real usage, you would need to pass a SessionStore instance
        # This is a placeholder for CLI usage
        print("ERROR: This CLI requires integration with a running SessionStore")
        print(f"Requested: simulate session={session_id} preset={preset_name}")
        sys.exit(1)

    elif command == "compare":
        if len(args) < 2:
            print("ERROR: Missing arguments for compare command")
            print("Usage: compare <session_id>")
            sys.exit(1)

        session_id = args[1]

        # Note: In real usage, you would need to pass a SessionStore instance
        # This is a placeholder for CLI usage
        print("ERROR: This CLI requires integration with a running SessionStore")
        print(f"Requested: compare session={session_id}")
        sys.exit(1)

    else:
        print(f"ERROR: Unknown command '{command}'")
        print("Available commands: list-presets, simulate, compare")
        sys.exit(1)


if __name__ == "__main__":
    main()
