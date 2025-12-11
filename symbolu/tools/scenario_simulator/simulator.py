"""
Scenario What-If Simulator - Phase 43

Pure-math simulator that applies preset multipliers to existing ScenarioFusionSnapshot
and computes simulated outcomes without modifying any live state.

This is a read-only analytics tool for exploring "what-if" scenarios.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
import math

from symbolu.formulas.scenario_fusion_engine import ScenarioFusionSnapshot
from .presets import ScenarioPreset


@dataclass
class SimulatedScenarioResult:
    """
    Result of a what-if simulation with a specific preset.

    Attributes:
        original_snapshot: Original ScenarioFusionSnapshot
        simulated_snapshot: Simulated ScenarioFusionSnapshot after preset applied
        applied_preset: Name of the preset applied
        diagnostic_notes: Observations about the simulation
    """

    original_snapshot: ScenarioFusionSnapshot
    simulated_snapshot: ScenarioFusionSnapshot
    applied_preset: str
    diagnostic_notes: List[str]


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


def _recompute_uncertainty_band(
    alignment: float, divergence: float, consensus: float
) -> Optional[str]:
    """
    Recompute future_uncertainty_band based on simulated metrics.

    Uses same thresholds as Phase 42:
    - LOW: high alignment (>=0.65), high consensus (>=0.65), low divergence (<=0.35)
    - HIGH: low alignment (<=0.40), low consensus (<=0.40), high divergence (>=0.65)
    - MEDIUM: everything else

    Args:
        alignment: Simulated alignment score [0.0, 1.0]
        divergence: Simulated divergence index [0.0, 1.0]
        consensus: Simulated consensus [0.0, 1.0]

    Returns:
        str: "low" | "medium" | "high"
    """
    # LOW uncertainty: strong alignment, strong consensus, low divergence
    if alignment >= 0.65 and consensus >= 0.65 and divergence <= 0.35:
        return "low"

    # HIGH uncertainty: weak alignment, weak consensus, high divergence
    elif alignment <= 0.40 and consensus <= 0.40 and divergence >= 0.65:
        return "high"

    # MEDIUM uncertainty: mixed indicators
    else:
        return "medium"


def _recompute_diagnostic_tags(
    alignment: float,
    divergence: float,
    consensus: float,
    uncertainty_band: Optional[str],
    dominant_path: Optional[str],
) -> List[str]:
    """
    Recompute diagnostic tags based on simulated metrics.

    Uses same thresholds as Phase 42.

    Args:
        alignment: Simulated alignment score [0.0, 1.0]
        divergence: Simulated divergence index [0.0, 1.0]
        consensus: Simulated consensus [0.0, 1.0]
        uncertainty_band: Simulated uncertainty band
        dominant_path: Simulated dominant future path

    Returns:
        List of diagnostic tags (sorted, deduplicated)
    """
    tags = []

    # Alignment tags
    if alignment >= 0.70:
        tags.append("SCENARIO_HIGHLY_ALIGNED")
    elif alignment <= 0.35:
        tags.append("SCENARIO_POORLY_ALIGNED")

    # Divergence tags
    if divergence >= 0.70:
        tags.append("SCENARIO_DIVERGING")
    elif divergence <= 0.35:
        tags.append("SCENARIO_CONVERGING")

    # Consensus tags
    if consensus >= 0.70:
        tags.append("SCENARIO_CONSENSUS_STRONG")
    elif consensus <= 0.35:
        tags.append("SCENARIO_CONSENSUS_WEAK")

    # Uncertainty tags
    if uncertainty_band == "low":
        tags.append("SCENARIO_FUTURE_STABLE")
    elif uncertainty_band == "high":
        tags.append("SCENARIO_FUTURE_UNCERTAIN")
    elif uncertainty_band == "medium":
        tags.append("SCENARIO_FUTURE_CAUTIOUS")

    # Pattern tags
    if alignment >= 0.65 and consensus >= 0.65:
        tags.append("SCENARIO_PATH_CONVERGING")

    if divergence >= 0.65 and consensus <= 0.40:
        tags.append("SCENARIO_PATH_DIVERGING")

    # Dominant path tags
    if dominant_path:
        tags.append(f"SCENARIO_PATH_{dominant_path.upper()}")

    return sorted(set(tags))


def _apply_path_shift_bias(
    fused_vector: Dict[str, float],
    original_dominant: Optional[str],
    path_shift_bias: float,
) -> Optional[str]:
    """
    Apply path shift bias to determine simulated dominant future path.

    Args:
        fused_vector: Fused scenario vector (regime scores)
        original_dominant: Original dominant path
        path_shift_bias: Bias value [-1.0, +1.0]
                         -1 = conservative (favor lower-ranked paths)
                         0 = neutral (no change)
                         +1 = expansive (favor higher-ranked paths)

    Returns:
        str: Simulated dominant path, or None if no paths available
    """
    if not fused_vector:
        return None

    # Sort paths by score (descending)
    sorted_paths = sorted(
        fused_vector.items(),
        key=lambda x: (x[1], x[0]),  # Sort by score DESC, then name ASC for determinism
        reverse=True,
    )

    if not sorted_paths:
        return None

    # Neutral bias: return top path (same as original logic)
    if abs(path_shift_bias) < 0.01:
        return sorted_paths[0][0]

    # Conservative bias: favor lower-ranked paths (move down the list)
    if path_shift_bias < 0:
        # Shift down by 1-2 positions based on bias strength
        shift = int(abs(path_shift_bias) * 2)  # -1.0 → shift by 2
        index = min(shift, len(sorted_paths) - 1)
        return sorted_paths[index][0]

    # Expansive bias: favor higher-ranked paths (stay at top, but enhance confidence)
    else:
        # For expansive, we keep the top path (already the highest)
        # The bias is reflected in the multipliers, not path selection
        return sorted_paths[0][0]


def _generate_comparison_notes(
    original: ScenarioFusionSnapshot,
    simulated: ScenarioFusionSnapshot,
    preset_name: str,
) -> List[str]:
    """
    Generate diagnostic notes comparing original and simulated snapshots.

    Args:
        original: Original snapshot
        simulated: Simulated snapshot
        preset_name: Name of applied preset

    Returns:
        List of diagnostic notes (sorted)
    """
    notes = [f"preset_applied:{preset_name}"]

    # Compare alignment
    alignment_diff = simulated.scenario_alignment_score - original.scenario_alignment_score
    if abs(alignment_diff) < 0.01:
        notes.append("alignment_unchanged")
    elif alignment_diff > 0:
        notes.append("alignment_increased")
        if alignment_diff > 0.15:
            notes.append("alignment_shift_significant")
    else:
        notes.append("alignment_decreased")
        if alignment_diff < -0.15:
            notes.append("alignment_shift_significant")

    # Compare divergence
    divergence_diff = simulated.scenario_divergence_index - original.scenario_divergence_index
    if abs(divergence_diff) < 0.01:
        notes.append("divergence_unchanged")
    elif divergence_diff > 0:
        notes.append("divergence_increased")
        if divergence_diff > 0.15:
            notes.append("divergence_shift_significant")
    else:
        notes.append("divergence_decreased")
        if divergence_diff < -0.15:
            notes.append("divergence_shift_significant")

    # Compare consensus
    consensus_diff = simulated.multi_regime_consensus - original.multi_regime_consensus
    if abs(consensus_diff) < 0.01:
        notes.append("consensus_unchanged")
    elif consensus_diff > 0:
        notes.append("consensus_increased")
        if consensus_diff > 0.15:
            notes.append("consensus_shift_significant")
    else:
        notes.append("consensus_decreased")
        if consensus_diff < -0.15:
            notes.append("consensus_shift_significant")

    # Compare uncertainty band
    if original.future_uncertainty_band != simulated.future_uncertainty_band:
        notes.append(
            f"uncertainty_band_changed:{original.future_uncertainty_band}->{simulated.future_uncertainty_band}"
        )
    else:
        notes.append("uncertainty_band_unchanged")

    # Compare dominant path
    if original.dominant_future_path != simulated.dominant_future_path:
        notes.append(
            f"dominant_path_shifted:{original.dominant_future_path}->{simulated.dominant_future_path}"
        )
    else:
        notes.append("dominant_path_unchanged")

    # Simulated state characterization
    if simulated.scenario_alignment_score >= 0.70:
        notes.append("simulated_highly_aligned")
    elif simulated.scenario_alignment_score <= 0.35:
        notes.append("simulated_poorly_aligned")

    if simulated.scenario_divergence_index >= 0.70:
        notes.append("simulated_highly_divergent")
    elif simulated.scenario_divergence_index <= 0.35:
        notes.append("simulated_highly_convergent")

    if simulated.multi_regime_consensus >= 0.70:
        notes.append("simulated_strong_consensus")
    elif simulated.multi_regime_consensus <= 0.35:
        notes.append("simulated_weak_consensus")

    return sorted(set(notes))


def simulate_scenario_with_preset(
    snapshot: ScenarioFusionSnapshot,
    preset: ScenarioPreset,
) -> Optional[SimulatedScenarioResult]:
    """
    Simulate scenario fusion with a specific preset applied.

    Takes an existing ScenarioFusionSnapshot and applies preset multipliers
    to its metrics, then recomputes derived fields (tags, uncertainty band, etc.).

    CRITICAL INVARIANTS:
        - Zero-LLM: Pure math only
        - Observation-only: NEVER modifies live coherence state
        - Deterministic: Same inputs → same outputs
        - Bounded: All metrics clamped to [0.0, 1.0]

    Args:
        snapshot: Original scenario fusion snapshot
        preset: Preset to apply

    Returns:
        SimulatedScenarioResult object, or None if simulation cannot be performed
    """
    if snapshot is None:
        return None

    # ========================================================================
    # STEP 1: APPLY MULTIPLIERS TO CORE METRICS
    # ========================================================================

    # Apply multipliers and clamp to [0.0, 1.0]
    simulated_alignment = _clamp(
        snapshot.scenario_alignment_score * preset.alignment_multiplier
    )
    simulated_divergence = _clamp(
        snapshot.scenario_divergence_index * preset.divergence_multiplier
    )
    simulated_consensus = _clamp(
        snapshot.multi_regime_consensus * preset.consensus_multiplier
    )

    # ========================================================================
    # STEP 2: RECOMPUTE UNCERTAINTY BAND
    # ========================================================================

    # Apply uncertainty multiplier by shifting thresholds
    # Higher multiplier → more likely to be "high" uncertainty
    # We simulate this by adjusting the metrics used in band computation
    uncertainty_adjusted_alignment = _clamp(
        simulated_alignment / preset.uncertainty_multiplier
    )
    uncertainty_adjusted_divergence = _clamp(
        simulated_divergence * preset.uncertainty_multiplier
    )
    uncertainty_adjusted_consensus = _clamp(
        simulated_consensus / preset.uncertainty_multiplier
    )

    simulated_uncertainty_band = _recompute_uncertainty_band(
        uncertainty_adjusted_alignment,
        uncertainty_adjusted_divergence,
        uncertainty_adjusted_consensus,
    )

    # ========================================================================
    # STEP 3: APPLY PATH SHIFT BIAS
    # ========================================================================

    simulated_dominant_path = _apply_path_shift_bias(
        snapshot.fused_scenario_vector,
        snapshot.dominant_future_path,
        preset.path_shift_bias,
    )

    # ========================================================================
    # STEP 4: RECOMPUTE DIAGNOSTIC TAGS
    # ========================================================================

    simulated_tags = _recompute_diagnostic_tags(
        simulated_alignment,
        simulated_divergence,
        simulated_consensus,
        simulated_uncertainty_band,
        simulated_dominant_path,
    )

    # ========================================================================
    # STEP 5: CREATE SIMULATED SNAPSHOT
    # ========================================================================

    simulated_snapshot = ScenarioFusionSnapshot(
        fused_scenario_vector=snapshot.fused_scenario_vector.copy(),  # Vector unchanged
        scenario_alignment_score=simulated_alignment,
        scenario_divergence_index=simulated_divergence,
        multi_regime_consensus=simulated_consensus,
        dominant_future_path=simulated_dominant_path,
        future_uncertainty_band=simulated_uncertainty_band,
        diagnostic_tags=simulated_tags,
    )

    # ========================================================================
    # STEP 6: GENERATE DIAGNOSTIC NOTES
    # ========================================================================

    diagnostic_notes = _generate_comparison_notes(
        snapshot, simulated_snapshot, preset.name
    )

    # ========================================================================
    # STEP 7: RETURN RESULT
    # ========================================================================

    return SimulatedScenarioResult(
        original_snapshot=snapshot,
        simulated_snapshot=simulated_snapshot,
        applied_preset=preset.name,
        diagnostic_notes=diagnostic_notes,
    )


def simulate_all_presets(
    snapshot: ScenarioFusionSnapshot,
) -> Dict[str, SimulatedScenarioResult]:
    """
    Simulate scenario fusion with all available presets.

    Args:
        snapshot: Original scenario fusion snapshot

    Returns:
        Dict mapping preset_name -> SimulatedScenarioResult
        (Presets that fail simulation are omitted)
    """
    from .presets import list_presets

    all_presets = list_presets()
    results = {}

    for preset_name, preset in all_presets.items():
        result = simulate_scenario_with_preset(snapshot, preset)
        if result is not None:
            results[preset_name] = result

    return results


def get_simulation_summary(result: SimulatedScenarioResult) -> str:
    """
    Generate a human-readable summary of a simulation result.

    Args:
        result: SimulatedScenarioResult object

    Returns:
        Multi-line string summary
    """
    orig = result.original_snapshot
    sim = result.simulated_snapshot

    lines = [
        f"Preset: {result.applied_preset}",
        "",
        "Metric Changes:",
        f"  Alignment:   {orig.scenario_alignment_score:.3f} -> {sim.scenario_alignment_score:.3f}",
        f"  Divergence:  {orig.scenario_divergence_index:.3f} -> {sim.scenario_divergence_index:.3f}",
        f"  Consensus:   {orig.multi_regime_consensus:.3f} -> {sim.multi_regime_consensus:.3f}",
        "",
        f"Uncertainty Band: {orig.future_uncertainty_band} -> {sim.future_uncertainty_band}",
        f"Dominant Path:    {orig.dominant_future_path} -> {sim.dominant_future_path}",
    ]

    if result.diagnostic_notes:
        lines.append("")
        lines.append("Diagnostic Notes:")
        for note in result.diagnostic_notes:
            lines.append(f"  - {note}")

    return "\n".join(lines)
