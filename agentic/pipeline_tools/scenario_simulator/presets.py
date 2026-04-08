"""
Scenario Presets - Phase 43

Named, deterministic presets that express different "philosophies" of scenario bias.

Each preset defines multipliers that adjust scenario fusion metrics before recomputation.
All multipliers are deterministic floats that bias the simulation in controlled ways.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ScenarioPreset:
    """
    A named scenario preset with metric multipliers.

    Attributes:
        name: Unique preset identifier (e.g., "neutral_baseline")
        description: Human-readable explanation of the preset philosophy
        alignment_multiplier: Multiplier for scenario_alignment_score
        divergence_multiplier: Multiplier for scenario_divergence_index
        consensus_multiplier: Multiplier for multi_regime_consensus
        uncertainty_multiplier: Multiplier for future_uncertainty_band calculations
        path_shift_bias: Bias for shifting dominant path selection [-1.0, +1.0]
                         -1 = conservative (favor lower-ranked paths)
                         0 = neutral (no change)
                         +1 = expansive (favor higher-ranked paths)
    """

    name: str
    description: str
    alignment_multiplier: float
    divergence_multiplier: float
    consensus_multiplier: float
    uncertainty_multiplier: float
    path_shift_bias: float


# ====== PRESET DEFINITIONS ======

PRESETS: Dict[str, ScenarioPreset] = {
    "neutral_baseline": ScenarioPreset(
        name="neutral_baseline",
        description="No change to computed scenario fusion metrics.",
        alignment_multiplier=1.0,
        divergence_multiplier=1.0,
        consensus_multiplier=1.0,
        uncertainty_multiplier=1.0,
        path_shift_bias=0.0,
    ),
    "conservative_bias": ScenarioPreset(
        name="conservative_bias",
        description="Decrease alignment, increase divergence - favors caution and uncertainty.",
        alignment_multiplier=0.75,
        divergence_multiplier=1.30,
        consensus_multiplier=0.80,
        uncertainty_multiplier=1.25,
        path_shift_bias=-1.0,  # Conservative path selection
    ),
    "expansive_bias": ScenarioPreset(
        name="expansive_bias",
        description="Increase alignment, reduce divergence - favors confidence and convergence.",
        alignment_multiplier=1.30,
        divergence_multiplier=0.70,
        consensus_multiplier=1.25,
        uncertainty_multiplier=0.75,
        path_shift_bias=1.0,  # Expansive path selection
    ),
    "stability_bias": ScenarioPreset(
        name="stability_bias",
        description="Boost consensus, lower uncertainty - emphasizes stable, predictable futures.",
        alignment_multiplier=1.15,
        divergence_multiplier=0.80,
        consensus_multiplier=1.40,
        uncertainty_multiplier=0.65,
        path_shift_bias=0.0,  # Neutral path selection
    ),
    "uncertainty_spike": ScenarioPreset(
        name="uncertainty_spike",
        description="Increase uncertainty band and divergence - explores high-variance scenarios.",
        alignment_multiplier=0.70,
        divergence_multiplier=1.45,
        consensus_multiplier=0.70,
        uncertainty_multiplier=1.50,
        path_shift_bias=0.0,  # Neutral path selection
    ),
}


# ====== HELPER FUNCTIONS ======


def get_preset(name: str) -> ScenarioPreset:
    """
    Retrieve a preset by name.

    Args:
        name: Preset identifier

    Returns:
        ScenarioPreset object

    Raises:
        KeyError: If preset name not found
    """
    if name not in PRESETS:
        available = ", ".join(sorted(PRESETS.keys()))
        raise KeyError(
            f"Preset '{name}' not found. Available presets: {available}"
        )
    return PRESETS[name]


def list_presets() -> Dict[str, ScenarioPreset]:
    """
    Get all available presets.

    Returns:
        Dict mapping preset name -> ScenarioPreset object
    """
    return PRESETS.copy()


def is_valid_preset(name: str) -> bool:
    """
    Check if a preset name is valid.

    Args:
        name: Preset identifier to check

    Returns:
        True if preset exists, False otherwise
    """
    return name in PRESETS


def get_preset_names() -> list[str]:
    """
    Get list of all preset names.

    Returns:
        Sorted list of preset names
    """
    return sorted(PRESETS.keys())


def get_multiplier(preset: ScenarioPreset, field_name: str) -> float:
    """
    Get the multiplier for a specific field in a preset.

    Args:
        preset: ScenarioPreset object
        field_name: Name of the field (e.g., 'alignment_multiplier')

    Returns:
        Multiplier value (default 1.0 if not found)
    """
    return getattr(preset, field_name, 1.0)
