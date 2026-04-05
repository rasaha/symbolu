"""
Resonance What-If Simulator - Phase 25

Pure-math simulator that applies preset multipliers to existing ResonanceWeightingSnapshot
and computes simulated outcomes without modifying any live state.

This is a read-only analytics tool for exploring "what-if" scenarios.
"""

from dataclasses import dataclass
from typing import Dict, Optional
import math

from symbolu_core.formulas.resonance_weighting import ResonanceWeightingSnapshot
from .presets import ResonancePreset, get_multiplier


@dataclass
class SimulatedResonanceScenario:
    """
    Result of a what-if simulation with a specific preset.

    Attributes:
        preset_name: Name of the preset applied
        original_weights: Raw weights from the original snapshot
        original_normalized: Normalized weights from the original snapshot
        simulated_normalized: Simulated normalized weights after preset applied
        entropy_original: Shannon entropy of original weights [0.0, 1.0]
        entropy_simulated: Shannon entropy of simulated weights [0.0, 1.0]
        dominant_original: Top N metrics from original snapshot
        dominant_simulated: Top N metrics from simulated scenario
        notes: Diagnostic observations about the simulation
    """

    preset_name: str
    original_weights: Dict[str, float]
    original_normalized: Dict[str, float]
    simulated_normalized: Dict[str, float]
    entropy_original: float
    entropy_simulated: float
    dominant_original: Dict[str, float]
    dominant_simulated: Dict[str, float]
    notes: list[str]


def _clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """
    Clamp value to [min_val, max_val] range.

    Args:
        value: Value to clamp
        min_val: Minimum value (default 0.0)
        max_val: Maximum value (default 1.0)

    Returns:
        float: Clamped value
    """
    return max(min_val, min(max_val, value))


def _normalize_weights(raw_weights: Dict[str, float]) -> tuple[Dict[str, float], float]:
    """
    Normalize weights to sum to 1.0 and compute Shannon entropy.

    Args:
        raw_weights: Raw weight values (must be >= 0)

    Returns:
        tuple: (normalized_weights dict, entropy value [0.0, 1.0])
               Returns ({}, 0.0) if sum is zero or empty
    """
    if not raw_weights:
        return {}, 0.0

    # Clamp all weights to >= 0
    clamped = {k: max(0.0, v) for k, v in raw_weights.items()}

    total = sum(clamped.values())
    if total <= 0.0:
        return {}, 0.0

    # Normalize to sum to 1.0
    normalized = {k: v / total for k, v in clamped.items()}

    # Compute Shannon entropy: H = -Σ(p_i * log2(p_i))
    # Normalized to [0.0, 1.0] by dividing by log2(N)
    entropy_raw = 0.0
    n = len(normalized)
    if n > 1:
        for weight in normalized.values():
            if weight > 0.0:
                entropy_raw -= weight * math.log2(weight)
        # Normalize by max entropy (log2(N))
        max_entropy = math.log2(n)
        entropy = entropy_raw / max_entropy if max_entropy > 0 else 0.0
    else:
        # Single metric = zero entropy (fully focused)
        entropy = 0.0

    return normalized, _clamp(entropy, 0.0, 1.0)


def _get_dominant_metrics(
    normalized_weights: Dict[str, float], top_n: int = 3
) -> Dict[str, float]:
    """
    Get top N metrics by normalized weight.

    Args:
        normalized_weights: Normalized weight dict
        top_n: Number of top metrics to return

    Returns:
        Dict of top N metrics
    """
    sorted_metrics = sorted(
        normalized_weights.items(), key=lambda x: x[1], reverse=True
    )
    return dict(sorted_metrics[:top_n])


def _compare_dominant_metrics(
    original: Dict[str, float], simulated: Dict[str, float]
) -> list[str]:
    """
    Generate notes about shifts in dominant metrics.

    Args:
        original: Original dominant metrics
        simulated: Simulated dominant metrics

    Returns:
        List of diagnostic notes
    """
    notes = []

    # Get top metric from each
    orig_top = max(original.items(), key=lambda x: x[1])[0] if original else None
    sim_top = max(simulated.items(), key=lambda x: x[1])[0] if simulated else None

    if orig_top and sim_top and orig_top != sim_top:
        notes.append(f"dominant_shifted:{orig_top}->{sim_top}")

    # Check for new metrics entering top N
    orig_keys = set(original.keys())
    sim_keys = set(simulated.keys())

    new_dominant = sim_keys - orig_keys
    if new_dominant:
        for metric in sorted(new_dominant):
            notes.append(f"new_dominant:{metric}")

    lost_dominant = orig_keys - sim_keys
    if lost_dominant:
        for metric in sorted(lost_dominant):
            notes.append(f"lost_dominant:{metric}")

    return notes


def simulate_resonance_with_preset(
    snapshot: ResonanceWeightingSnapshot,
    preset: ResonancePreset,
    top_n: int = 3,
) -> Optional[SimulatedResonanceScenario]:
    """
    Simulate resonance weighting with a specific preset applied.

    Takes an existing ResonanceWeightingSnapshot and applies preset multipliers
    to its raw weights, then re-normalizes and recomputes derived metrics.

    Args:
        snapshot: Original resonance weighting snapshot
        preset: Preset to apply
        top_n: Number of top dominant metrics to track (default 3)

    Returns:
        SimulatedResonanceScenario object, or None if simulation cannot be performed
        (e.g., all effective weights are zero)
    """
    # Start with original raw weights
    original_raw_weights = snapshot.weights.copy()

    # Apply preset multipliers to get effective raw weights
    simulated_raw_weights = {}
    for metric_name, orig_weight in original_raw_weights.items():
        multiplier = get_multiplier(preset, metric_name)
        simulated_raw_weights[metric_name] = orig_weight * multiplier

    # Check if all effective weights are zero
    if all(w <= 0.0 for w in simulated_raw_weights.values()):
        return None

    # Re-normalize and compute entropy
    simulated_normalized, simulated_entropy = _normalize_weights(
        simulated_raw_weights
    )

    if not simulated_normalized:
        return None

    # Get dominant metrics
    original_dominant = _get_dominant_metrics(snapshot.normalized_weights, top_n)
    simulated_dominant = _get_dominant_metrics(simulated_normalized, top_n)

    # Generate diagnostic notes
    notes = [f"preset_applied:{preset.name}"]

    # Compare entropies
    entropy_diff = simulated_entropy - snapshot.entropy_of_weights
    if abs(entropy_diff) < 0.01:
        notes.append("entropy_unchanged")
    elif entropy_diff > 0:
        notes.append("entropy_increased")
        if entropy_diff > 0.1:
            notes.append("entropy_shift_significant")
    else:
        notes.append("entropy_decreased")
        if entropy_diff < -0.1:
            notes.append("entropy_shift_significant")

    # Add entropy level notes for simulated state
    if simulated_entropy < 0.35:
        notes.append("simulated_focused_resonance")
    elif simulated_entropy < 0.70:
        notes.append("simulated_balanced_resonance")
    else:
        notes.append("simulated_diffuse_resonance")

    # Compare dominant metrics
    dominant_notes = _compare_dominant_metrics(original_dominant, simulated_dominant)
    notes.extend(dominant_notes)

    # Check for significant weight changes in dominant metrics
    for metric_name in simulated_dominant.keys():
        orig_weight = snapshot.normalized_weights.get(metric_name, 0.0)
        sim_weight = simulated_normalized.get(metric_name, 0.0)
        weight_change = sim_weight - orig_weight

        if abs(weight_change) > 0.1:  # Significant change threshold
            if weight_change > 0:
                notes.append(f"weight_increased:{metric_name}")
            else:
                notes.append(f"weight_decreased:{metric_name}")

    return SimulatedResonanceScenario(
        preset_name=preset.name,
        original_weights=original_raw_weights,
        original_normalized=snapshot.normalized_weights.copy(),
        simulated_normalized=simulated_normalized,
        entropy_original=snapshot.entropy_of_weights,
        entropy_simulated=simulated_entropy,
        dominant_original=original_dominant,
        dominant_simulated=simulated_dominant,
        notes=sorted(set(notes)),  # Deduplicate and sort for determinism
    )


def simulate_all_presets(
    snapshot: ResonanceWeightingSnapshot,
    top_n: int = 3,
) -> Dict[str, SimulatedResonanceScenario]:
    """
    Simulate resonance weighting with all available presets.

    Args:
        snapshot: Original resonance weighting snapshot
        top_n: Number of top dominant metrics to track (default 3)

    Returns:
        Dict mapping preset_name -> SimulatedResonanceScenario
        (Presets that fail simulation are omitted)
    """
    from .presets import list_presets

    all_presets = list_presets()
    results = {}

    for preset_name, preset in all_presets.items():
        scenario = simulate_resonance_with_preset(snapshot, preset, top_n)
        if scenario is not None:
            results[preset_name] = scenario

    return results


def get_simulation_summary(scenario: SimulatedResonanceScenario) -> str:
    """
    Generate a human-readable summary of a simulation scenario.

    Args:
        scenario: SimulatedResonanceScenario object

    Returns:
        Multi-line string summary
    """
    lines = [
        f"Preset: {scenario.preset_name}",
        f"Entropy: {scenario.entropy_original:.3f} -> {scenario.entropy_simulated:.3f}",
        "",
        "Original Top Metrics:",
    ]

    for metric, weight in scenario.dominant_original.items():
        lines.append(f"  {metric}: {weight:.3f}")

    lines.append("")
    lines.append("Simulated Top Metrics:")

    for metric, weight in scenario.dominant_simulated.items():
        lines.append(f"  {metric}: {weight:.3f}")

    if scenario.notes:
        lines.append("")
        lines.append("Notes:")
        for note in scenario.notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)
