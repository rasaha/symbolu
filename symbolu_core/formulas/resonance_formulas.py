"""
Resonance Formulas — Core/Substrate Utility
============================================

╔═══════════════════════════════════════════════════════════════════════════════╗
║                         CORE/SUBSTRATE LAYER                                   ║
║                                                                                ║
║  This module is part of the Core/Substrate layer.                              ║
║  It is NOT a pipeline phase and has no authority over intent, regime,          ║
║  semantics, or delivery.                                                       ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Deterministic, zero-LLM formulas for temporal analysis.

This module computes the four foundational formulas:
- SMI (Symbolic Mental Index): Normalized scalar of consciousness state
- ΔSMI (delta SMI): Momentum tracking across turns
- Bhava Gap: Distance between consciousness states in the 12-bhava cycle
- Tension Corridor: Composite signal tracking tension dynamics

All formulas are deterministic with placeholder coefficients until
final patent constants are inserted.

This module:
    - Computes temporal resonance metrics
    - Measures consciousness state signals
    - Does NOT interpret meaning
    - Does NOT infer emotion or intent
    - Does NOT affect delivery decisions

ARCHITECTURAL NOTE:
    This module contains foundational formulas for observation layers.
    It does NOT participate in governance cognition. These formulas are:

    - Core/Substrate: Stateless mathematical utilities
    - Foundational: Mathematical primitives for P10+ layers
    - Non-semantic: They do not influence intent, regime, or lexical decisions
    - Non-authoritative: Cannot influence governance or routing decisions

    Authoritative phases (PO1-PO5, P6-P9) govern meaning and authority.
    Core/Substrate formulas may only be observed by allowed sinks.

    See: Project_documentation/repository/docs/architecture/core_vs_pipeline.md

HISTORICAL NOTE: Legacy docstrings may reference "Phase 1". This is a
historical development label, NOT an authoritative pipeline phase.

Version: 1.0 (Core/Substrate Utility)
Date: 2025-12-09
"""

from typing import Optional


def compute_smi(
    dimensional_resonance: float,
    vrtti_intensity: float,
    bhava_position: float,
) -> float:
    """
    Compute SMI (Symbolic Mental Index).

    SMI is a normalized scalar ∈ [0, 1] representing consciousness state,
    computed from three components:
    - dimensional_resonance: Resonance across dimensional space
    - vrtti_intensity: Mental fluctuation intensity
    - bhava_position: Position in consciousness state space

    Temporary canonical definition (placeholder coefficients):
        smi = 0.5 * dimensional_resonance + 0.3 * vrtti_intensity + 0.2 * bhava_position
        smi = clamp(smi, 0.0, 1.0)

    Args:
        dimensional_resonance: Dimensional resonance value (0.0 to 1.0)
        vrtti_intensity: Vrtti (mental fluctuation) intensity (0.0 to 1.0)
        bhava_position: Bhava position value (0.0 to 1.0)

    Returns:
        SMI value normalized to [0.0, 1.0]

    Raises:
        ValueError: If any input is outside [0.0, 1.0] range
    """
    # Input validation
    if not (0.0 <= dimensional_resonance <= 1.0):
        raise ValueError(f"dimensional_resonance must be in [0.0, 1.0], got {dimensional_resonance}")
    if not (0.0 <= vrtti_intensity <= 1.0):
        raise ValueError(f"vrtti_intensity must be in [0.0, 1.0], got {vrtti_intensity}")
    if not (0.0 <= bhava_position <= 1.0):
        raise ValueError(f"bhava_position must be in [0.0, 1.0], got {bhava_position}")

    # Compute weighted sum with placeholder coefficients
    smi = 0.5 * dimensional_resonance + 0.3 * vrtti_intensity + 0.2 * bhava_position

    # Clamp to [0.0, 1.0] (should already be in range, but ensure safety)
    smi = max(0.0, min(1.0, smi))

    return smi


def compute_delta_smi(smi: float, previous_smi: Optional[float]) -> float:
    """
    Compute ΔSMI (delta SMI) - momentum indicator.

    ΔSMI represents the change in SMI from the previous turn,
    tracking momentum in consciousness state evolution.

    Formula:
        delta_smi = smi - previous_smi
        delta_smi = clamp(delta_smi, -1.0, 1.0)

    Args:
        smi: Current SMI value (0.0 to 1.0)
        previous_smi: Previous turn SMI value (0.0 to 1.0), or None for first turn

    Returns:
        ΔSMI value in [-1.0, 1.0]
        Returns 0.0 if previous_smi is None (first turn)

    Raises:
        ValueError: If smi or previous_smi is outside [0.0, 1.0] range
    """
    # Input validation
    if not (0.0 <= smi <= 1.0):
        raise ValueError(f"smi must be in [0.0, 1.0], got {smi}")

    # Handle first turn (no previous SMI)
    if previous_smi is None:
        return 0.0

    if not (0.0 <= previous_smi <= 1.0):
        raise ValueError(f"previous_smi must be in [0.0, 1.0], got {previous_smi}")

    # Compute delta
    delta_smi = smi - previous_smi

    # Clamp to [-1.0, 1.0] (should already be in range, but ensure safety)
    delta_smi = max(-1.0, min(1.0, delta_smi))

    return delta_smi


def compute_bhava_gap(current_bhava: int, previous_bhava: Optional[int]) -> float:
    """
    Compute Bhava Gap - circular distance in the 12-bhava cycle.

    Bhava Gap measures the shortest distance between two bhava states
    in the circular 12-bhava consciousness cycle, normalized to [0, 1].

    Formula:
        gap = abs(current_bhava - previous_bhava)
        bhava_gap = min(gap, 12 - gap) / 6.0

    The division by 6.0 normalizes to [0, 1] since max distance is 6 steps.

    Args:
        current_bhava: Current bhava ID (0 to 11)
        previous_bhava: Previous bhava ID (0 to 11), or None for first turn

    Returns:
        Bhava gap normalized to [0.0, 1.0]
        Returns 0.0 if previous_bhava is None (first turn)

    Raises:
        ValueError: If bhava IDs are outside [0, 11] range
    """
    # Input validation
    if not (0 <= current_bhava <= 11):
        raise ValueError(f"current_bhava must be in [0, 11], got {current_bhava}")

    # Handle first turn (no previous bhava)
    if previous_bhava is None:
        return 0.0

    if not (0 <= previous_bhava <= 11):
        raise ValueError(f"previous_bhava must be in [0, 11], got {previous_bhava}")

    # Compute circular distance
    gap = abs(current_bhava - previous_bhava)

    # Take the shorter path around the circle
    circular_gap = min(gap, 12 - gap)

    # Normalize to [0.0, 1.0] (max distance is 6, so divide by 6)
    bhava_gap = circular_gap / 6.0

    return bhava_gap


def compute_tension_corridor(delta_smi: float, bhava_gap: float) -> float:
    """
    Compute Tension Corridor - composite tension dynamics signal.

    Tension Corridor tracks whether tension is rising, falling, or stable
    by combining momentum (ΔSMI) and state distance (bhava gap).

    Temporary canonical definition (placeholder coefficients):
        tension_corridor = 0.6 * abs(delta_smi) + 0.4 * bhava_gap
        tension_corridor = clamp(tension_corridor, 0.0, 1.0)

    Args:
        delta_smi: Delta SMI value (-1.0 to 1.0)
        bhava_gap: Bhava gap value (0.0 to 1.0)

    Returns:
        Tension corridor value normalized to [0.0, 1.0]

    Raises:
        ValueError: If inputs are outside expected ranges
    """
    # Input validation
    if not (-1.0 <= delta_smi <= 1.0):
        raise ValueError(f"delta_smi must be in [-1.0, 1.0], got {delta_smi}")
    if not (0.0 <= bhava_gap <= 1.0):
        raise ValueError(f"bhava_gap must be in [0.0, 1.0], got {bhava_gap}")

    # Compute weighted combination with placeholder coefficients
    tension_corridor = 0.6 * abs(delta_smi) + 0.4 * bhava_gap

    # Clamp to [0.0, 1.0] (should already be in range, but ensure safety)
    tension_corridor = max(0.0, min(1.0, tension_corridor))

    return tension_corridor
