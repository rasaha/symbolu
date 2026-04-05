"""
Resonance Presets - Phase 25

Named, deterministic presets that express different "philosophies" of trusting metrics.

Each preset defines multipliers that adjust raw resonance weights before normalization.
Multipliers are soft: they enhance or suppress specific metrics, then the system re-normalizes.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ResonancePreset:
    """
    A named resonance preset with metric multipliers.

    Attributes:
        name: Unique preset identifier (e.g., "safety_first")
        description: Human-readable explanation of the preset philosophy
        metric_multipliers: Dict mapping metric_name -> multiplier
                           Default multiplier is 1.0 if not specified
    """

    name: str
    description: str
    metric_multipliers: Dict[str, float]


# ====== PRESET DEFINITIONS ======

PRESETS: Dict[str, ResonancePreset] = {
    "safety_first": ResonancePreset(
        name="safety_first",
        description="Emphasize stability, integrity, and low drift.",
        metric_multipliers={
            "semantic_integrity": 1.3,
            "drift_inverse": 1.3,
            "entropy_stability": 1.2,
            "coherence_fused": 1.1,
            "cognitive_stability": 1.2,
        },
    ),
    "insight_heavy": ResonancePreset(
        name="insight_heavy",
        description="Emphasize arc, resonance, and identity exploration.",
        metric_multipliers={
            "resonance_index": 1.3,
            "arc_alignment_index": 1.3,
            "guna_resonance_index": 1.2,
            "kosha_resonance_index": 1.2,
            "arc_tension_harmonizer": 1.2,
        },
    ),
    "identity_careful": ResonancePreset(
        name="identity_careful",
        description="Balance exploration with strict drift and tension constraints.",
        metric_multipliers={
            "semantic_integrity": 1.3,
            "drift_inverse": 1.4,
            "tension_inverse": 1.2,
            "cognitive_stability": 1.3,
        },
    ),
    "coherence_focused": ResonancePreset(
        name="coherence_focused",
        description="Prioritize all coherence signals strongly.",
        metric_multipliers={
            "coherence_fused": 1.4,
            "coherence_v3": 1.3,
            "coherence_v2": 1.3,
            "coherence_v1": 1.2,
            "semantic_integrity": 1.2,
        },
    ),
    "formula_balanced": ResonancePreset(
        name="formula_balanced",
        description="Balanced trust across all formula categories.",
        metric_multipliers={
            "enhanced_smi": 1.1,
            "vritti_momentum": 1.1,
            "arc_tension_harmonizer": 1.1,
            "resonance_index": 1.1,
            "guna_resonance_index": 1.1,
            "kosha_resonance_index": 1.1,
        },
    ),
    "neutral_baseline": ResonancePreset(
        name="neutral_baseline",
        description="No change to computed resonance weighting.",
        metric_multipliers={},
    ),
}


# ====== HELPER FUNCTIONS ======


def get_preset(name: str) -> ResonancePreset:
    """
    Retrieve a preset by name.

    Args:
        name: Preset identifier

    Returns:
        ResonancePreset object

    Raises:
        KeyError: If preset name not found
    """
    if name not in PRESETS:
        available = ", ".join(sorted(PRESETS.keys()))
        raise KeyError(
            f"Preset '{name}' not found. Available presets: {available}"
        )
    return PRESETS[name]


def list_presets() -> Dict[str, ResonancePreset]:
    """
    Get all available presets.

    Returns:
        Dict mapping preset name -> ResonancePreset object
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


def get_multiplier(preset: ResonancePreset, metric_name: str) -> float:
    """
    Get the multiplier for a specific metric in a preset.

    Args:
        preset: ResonancePreset object
        metric_name: Name of the metric

    Returns:
        Multiplier value (default 1.0 if not specified in preset)
    """
    return preset.metric_multipliers.get(metric_name, 1.0)
