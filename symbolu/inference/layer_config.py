"""
Layer Inference Configuration
==============================

Configuration for layer-specific inference behavior reflecting the 9:3
Authority/Sensory hierarchical split from the Symbolu architecture.

The 9:3 split divides the 12-layer transformer into:
- **Authority Layers (O1-O9)**: Core semantic intent and meaning
- **Sensory Layers (O10-O12)**: Phonetic expression and fluency

This configuration enables:
1. KV-cache optimization by prioritizing authority layers
2. Layer-specific temperature adjustments for precise token selection
3. Memory-efficient inference on constrained hardware

Training Reference:
    HierarchicalGradientScaler (train_unified_llm.py) applies different
    gradient scales: full gradients for authority, dampened (α_sens) for sensory.

Usage:
------
    from symbolu.inference import LayerInferenceConfig

    # Get cache priority for memory optimization
    for layer_idx in range(12):
        priority = LayerInferenceConfig.get_cache_priority(layer_idx)
        print(f"Layer {layer_idx}: {priority}")

    # Apply layer-specific temperature
    base_temp = 1.0
    for layer_idx in range(12):
        adjusted = LayerInferenceConfig.get_temperature_adjustment(layer_idx, base_temp)
        print(f"Layer {layer_idx}: {adjusted:.2f}")
"""

from typing import Dict, List, Tuple, Optional, Any
from enum import Enum


class CachePriority(Enum):
    """KV-cache retention priority levels."""
    HIGH = "high"      # Retain aggressively, evict last
    MEDIUM = "medium"  # Standard retention
    LOW = "low"        # Can be recomputed if needed


class LayerType(Enum):
    """Ontological layer classification."""
    AUTHORITY = "authority"  # O1-O9: Meaning and intent
    SENSORY = "sensory"      # O10-O12: Expression and fluency


class LayerInferenceConfig:
    """
    Configuration for layer-specific inference behavior.

    Reflects the 9:3 Authority/Sensory split from the Symbolu architecture.
    Enables heterogeneous layer treatment for memory optimization and
    output precision.

    The 9:3 split is based on the ontological structure:
    - Authority (O1-O9): Potential → Momentum → Restraint → Expansion →
                        Cohesion → Transformation → Refinement →
                        Manifestation → Rhythm
    - Sensory (O10-O12): Stability → Dissolving → Integration

    Attributes:
        AUTHORITY_LAYERS: Layer indices for core semantic processing
        SENSORY_LAYERS: Layer indices for phonetic/expressive output
        LAYER_NAMES: Mapping of layer index to ontological name
    """

    # Authority layers (O1-O9): Core semantic intent
    AUTHORITY_LAYERS: List[int] = list(range(9))

    # Sensory layers (O10-O12): Phonetic and expressive output
    SENSORY_LAYERS: List[int] = list(range(9, 12))

    # Ontological layer names (0-indexed)
    LAYER_NAMES: Dict[int, str] = {
        0: "O1-Potential",
        1: "O2-Momentum",
        2: "O3-Restraint",
        3: "O4-Expansion",
        4: "O5-Cohesion",
        5: "O6-Transformation",
        6: "O7-Refinement",
        7: "O8-Manifestation",
        8: "O9-Rhythm",
        9: "O10-Stability",
        10: "O11-Dissolving",
        11: "O12-Integration",
    }

    # Default temperature multipliers
    AUTHORITY_TEMP_MULTIPLIER: float = 1.0
    SENSORY_TEMP_MULTIPLIER: float = 0.9  # Sharper for precise token selection

    # Cache priority assignments
    AUTHORITY_CACHE_PRIORITY: CachePriority = CachePriority.HIGH
    SENSORY_CACHE_PRIORITY: CachePriority = CachePriority.MEDIUM

    @classmethod
    def get_layer_type(cls, layer_idx: int) -> LayerType:
        """
        Get the ontological type of a layer.

        Args:
            layer_idx: Layer index (0-11)

        Returns:
            LayerType.AUTHORITY or LayerType.SENSORY
        """
        if layer_idx in cls.AUTHORITY_LAYERS:
            return LayerType.AUTHORITY
        return LayerType.SENSORY

    @classmethod
    def get_layer_name(cls, layer_idx: int) -> str:
        """
        Get the ontological name of a layer.

        Args:
            layer_idx: Layer index (0-11)

        Returns:
            Ontological name (e.g., "O1-Potential")
        """
        return cls.LAYER_NAMES.get(layer_idx, f"Layer-{layer_idx}")

    @classmethod
    def get_cache_priority(cls, layer_idx: int) -> str:
        """
        Get KV-cache retention priority for a layer.

        Authority layers are HIGH priority (evict last) because they
        contain core semantic intent that's expensive to recompute.

        Sensory layers are MEDIUM priority and can be recomputed
        more readily if memory pressure requires eviction.

        Args:
            layer_idx: Layer index (0-11)

        Returns:
            Priority string: "high", "medium", or "low"
        """
        if layer_idx in cls.AUTHORITY_LAYERS:
            return cls.AUTHORITY_CACHE_PRIORITY.value
        return cls.SENSORY_CACHE_PRIORITY.value

    @classmethod
    def get_temperature_adjustment(
        cls,
        layer_idx: int,
        base_temp: float,
    ) -> float:
        """
        Get layer-adjusted temperature for attention computation.

        Sensory layers use sharper attention (lower temperature) for
        precise token selection, reducing the risk of "word salad"
        even when authority layers are exploring broader semantic spaces.

        Args:
            layer_idx: Layer index (0-11)
            base_temp: Base temperature value

        Returns:
            Adjusted temperature for the layer
        """
        if layer_idx in cls.SENSORY_LAYERS:
            return base_temp * cls.SENSORY_TEMP_MULTIPLIER
        return base_temp * cls.AUTHORITY_TEMP_MULTIPLIER

    @classmethod
    def get_gradient_scale(
        cls,
        layer_idx: int,
        authority_scale: float = 1.0,
        sensory_scale: float = 0.3,
    ) -> float:
        """
        Get gradient scaling factor for a layer (training reference).

        This mirrors the HierarchicalGradientScaler behavior from training.
        Useful for inference-time gradient-based methods (e.g., guided generation).

        Args:
            layer_idx: Layer index (0-11)
            authority_scale: Scale for authority layers (default 1.0)
            sensory_scale: Scale for sensory layers (default 0.3)

        Returns:
            Gradient scale factor
        """
        if layer_idx in cls.AUTHORITY_LAYERS:
            return authority_scale
        return sensory_scale

    @classmethod
    def get_extraction_layers(
        cls,
        mode: str = "minimal",
    ) -> List[int]:
        """
        Get recommended layers to extract for different use cases.

        Args:
            mode: Extraction mode
                - "minimal": O1 and O12 only (karma/resonance)
                - "authority": All authority layers
                - "sensory": All sensory layers
                - "endpoints": O1, O9 (authority end), O12
                - "full": All 12 layers

        Returns:
            List of layer indices to extract
        """
        modes = {
            "minimal": [0, 11],
            "authority": cls.AUTHORITY_LAYERS,
            "sensory": cls.SENSORY_LAYERS,
            "endpoints": [0, 8, 11],  # O1, O9, O12
            "full": list(range(12)),
        }
        return modes.get(mode, [0, 11])

    @classmethod
    def get_split_config(cls) -> Tuple[int, int]:
        """
        Get the authority/sensory split configuration.

        Returns:
            (authority_count, sensory_count) tuple, e.g., (9, 3)
        """
        return (len(cls.AUTHORITY_LAYERS), len(cls.SENSORY_LAYERS))

    @classmethod
    def get_layer_weights(
        cls,
        authority_weight: float = 1.0,
        sensory_weight: float = 0.5,
    ) -> Dict[int, float]:
        """
        Get per-layer weights for aggregation operations.

        Useful for weighted averaging of layer outputs or
        computing weighted coherence scores.

        Args:
            authority_weight: Weight for authority layers
            sensory_weight: Weight for sensory layers

        Returns:
            Dict mapping layer_idx to weight
        """
        weights = {}
        for idx in cls.AUTHORITY_LAYERS:
            weights[idx] = authority_weight
        for idx in cls.SENSORY_LAYERS:
            weights[idx] = sensory_weight
        return weights

    @classmethod
    def summarize(cls) -> str:
        """Get a summary string of the configuration."""
        auth_count, sens_count = cls.get_split_config()
        return (
            f"LayerInferenceConfig({auth_count}:{sens_count} split)\n"
            f"  Authority (O1-O9): {cls.AUTHORITY_LAYERS}\n"
            f"  Sensory (O10-O12): {cls.SENSORY_LAYERS}\n"
            f"  Cache: Authority={cls.AUTHORITY_CACHE_PRIORITY.value}, "
            f"Sensory={cls.SENSORY_CACHE_PRIORITY.value}\n"
            f"  Temp: Authority={cls.AUTHORITY_TEMP_MULTIPLIER}x, "
            f"Sensory={cls.SENSORY_TEMP_MULTIPLIER}x"
        )


# Convenience aliases for common patterns
AUTHORITY_LAYERS = LayerInferenceConfig.AUTHORITY_LAYERS
SENSORY_LAYERS = LayerInferenceConfig.SENSORY_LAYERS
LAYER_NAMES = LayerInferenceConfig.LAYER_NAMES
