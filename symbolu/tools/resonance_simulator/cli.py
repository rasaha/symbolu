"""
Resonance Simulator CLI Tools - Phase 25

Command-line interface for running resonance what-if simulations on sessions.

This module provides read-only diagnostic tools for exploring resonance scenarios
without modifying any live pipeline state.
"""

from typing import Optional
import sys

from symbolu.service.sessions.session_store import SessionStore
from symbolu.formulas.resonance_weighting import ResonanceWeightingSnapshot
from .presets import get_preset, list_presets, is_valid_preset, get_preset_names
from .simulator import (
    simulate_resonance_with_preset,
    simulate_all_presets,
    get_simulation_summary,
)


def print_presets() -> None:
    """
    Print all available resonance presets with descriptions.

    This is a read-only informational function.
    """
    presets = list_presets()

    print("=" * 70)
    print("Available Resonance Presets")
    print("=" * 70)
    print()

    for preset_name in sorted(presets.keys()):
        preset = presets[preset_name]
        print(f"[{preset_name}]")
        print(f"  Description: {preset.description}")

        if preset.metric_multipliers:
            print(f"  Multipliers:")
            for metric, mult in sorted(preset.metric_multipliers.items()):
                print(f"    - {metric}: {mult:.2f}x")
        else:
            print(f"  Multipliers: (none - baseline)")

        print()


def _extract_resonance_snapshot(
    session_store: SessionStore, session_id: str
) -> Optional[ResonanceWeightingSnapshot]:
    """
    Extract the latest resonance weighting snapshot from a session.

    Args:
        session_store: SessionStore instance
        session_id: Session identifier

    Returns:
        ResonanceWeightingSnapshot if available, None otherwise
    """
    session = session_store.get(session_id)
    if session is None:
        return None

    # Look for latest resonance snapshot in coherence history
    if not session.coherence_history:
        return None

    # Check most recent coherence state
    for coherence_dict in reversed(session.coherence_history):
        if not isinstance(coherence_dict, dict):
            continue

        # Check for resonance_weighting_history
        if "resonance_weighting_history" in coherence_dict:
            rw_history = coherence_dict["resonance_weighting_history"]
            if rw_history and len(rw_history) > 0:
                # Get most recent snapshot
                snapshot = rw_history[-1]
                if snapshot is not None:
                    return snapshot

    return None


def print_resonance_simulation_for_session(
    session_store: SessionStore,
    session_id: str,
    preset_name: str,
    top_n: int = 3,
) -> None:
    """
    Print resonance simulation results for a specific session and preset.

    Args:
        session_store: SessionStore instance
        session_id: Session identifier
        preset_name: Preset to apply
        top_n: Number of top metrics to display (default 3)
    """
    print("=" * 70)
    print(f"Resonance Simulation for Session: {session_id}")
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

    # Extract resonance snapshot
    snapshot = _extract_resonance_snapshot(session_store, session_id)
    if snapshot is None:
        print("ERROR: No resonance weighting snapshot available for this session")
        print("(Session may not have any turns with resonance weighting computed)")
        return

    # Get preset and run simulation
    preset = get_preset(preset_name)
    scenario = simulate_resonance_with_preset(snapshot, preset, top_n)

    if scenario is None:
        print(f"ERROR: Simulation failed (all effective weights may be zero)")
        return

    # Print results
    print(get_simulation_summary(scenario))
    print()


def print_resonance_comparison_for_session(
    session_store: SessionStore,
    session_id: str,
    top_n: int = 3,
) -> None:
    """
    Print resonance simulation comparison across all presets for a session.

    Args:
        session_store: SessionStore instance
        session_id: Session identifier
        top_n: Number of top metrics to display (default 3)
    """
    print("=" * 70)
    print(f"Resonance Preset Comparison for Session: {session_id}")
    print("=" * 70)
    print()

    # Retrieve session
    session = session_store.get(session_id)
    if session is None:
        print(f"ERROR: Session '{session_id}' not found")
        return

    # Extract resonance snapshot
    snapshot = _extract_resonance_snapshot(session_store, session_id)
    if snapshot is None:
        print("ERROR: No resonance weighting snapshot available for this session")
        print("(Session may not have any turns with resonance weighting computed)")
        return

    # Run all simulations
    scenarios = simulate_all_presets(snapshot, top_n)

    if not scenarios:
        print("ERROR: No valid simulations could be run")
        return

    # Print original state first
    print("ORIGINAL STATE (no preset)")
    print("-" * 70)
    print(f"Entropy: {snapshot.entropy_of_weights:.3f}")
    print()
    print("Top Metrics:")
    for metric, weight in snapshot.dominant_metrics.items():
        print(f"  {metric}: {weight:.3f}")
    print()
    print()

    # Print each preset's results
    for preset_name in sorted(scenarios.keys()):
        scenario = scenarios[preset_name]

        print(f"PRESET: {preset_name}")
        print("-" * 70)
        print(get_simulation_summary(scenario))
        print()
        print()


def main() -> None:
    """
    Main CLI entry point for resonance simulator.

    Usage:
        python -m symbolu.tools.resonance_simulator.cli list-presets
        python -m symbolu.tools.resonance_simulator.cli simulate <session_id> <preset_name>
        python -m symbolu.tools.resonance_simulator.cli compare <session_id>
    """
    args = sys.argv[1:]

    if len(args) == 0:
        print("Usage:")
        print("  python -m symbolu.tools.resonance_simulator.cli list-presets")
        print("  python -m symbolu.tools.resonance_simulator.cli simulate <session_id> <preset_name>")
        print("  python -m symbolu.tools.resonance_simulator.cli compare <session_id>")
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
