#!/usr/bin/env python3
"""
Layer Inference Configuration
==============================

Configuration for layer-specific inference behavior reflecting
the hierarchical split from training.

Supports both:
- 9:3 Authority/Sensory split (original architecture)
- 6:6 Authority/Sensory split (balanced architecture)

Training Reference: HierarchicalGradientScaler in train_unified_llm.py

Author: Sovereign-1 Training Initiative
Date: January 2026
"""

from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class ArchitectureMode(Enum):
    """Supported layer architecture modes."""
    SPLIT_9_3 = "9:3"  # Original: 9 Authority, 3 Sensory
    SPLIT_6_6 = "6:6"  # Balanced: 6 Authority, 6 Sensory
    SPLIT_12_0 = "12:0"  # All Authority (standard transformer)


@dataclass
class LayerInferenceConfig:
    """
    Configuration for layer-specific inference behavior.

    Reflects Authority/Sensory split from training and provides:
    - Cache priority for KV-cache optimization
    - Temperature adjustments per layer type
    - Interpretability of layer contributions

    Attributes:
        mode: Architecture mode (9:3, 6:6, or 12:0)
        authority_layers: List of authority layer indices
        sensory_layers: List of sensory layer indices
        num_layers: Total number of layers
    """

    mode: ArchitectureMode = ArchitectureMode.SPLIT_6_6
    num_layers: int = 12

    def __post_init__(self):
        """Configure layer splits based on mode."""
        if self.mode == ArchitectureMode.SPLIT_9_3:
            self._authority_layers = list(range(9))  # O1-O9
            self._sensory_layers = list(range(9, 12))  # O10-O12
        elif self.mode == ArchitectureMode.SPLIT_6_6:
            self._authority_layers = list(range(6))  # O1-O6
            self._sensory_layers = list(range(6, 12))  # O7-O12
        else:  # 12:0
            self._authority_layers = list(range(12))
            self._sensory_layers = []

    @property
    def authority_layers(self) -> List[int]:
        """Get authority layer indices."""
        return self._authority_layers

    @property
    def sensory_layers(self) -> List[int]:
        """Get sensory layer indices."""
        return self._sensory_layers

    @classmethod
    def from_checkpoint(cls, checkpoint: Dict) -> 'LayerInferenceConfig':
        """
        Create config from checkpoint metadata.

        Args:
            checkpoint: Checkpoint dict with possible inference_config

        Returns:
            config: LayerInferenceConfig instance
        """
        inference_config = checkpoint.get('inference_config', {})

        # Try to infer mode from checkpoint
        split = inference_config.get('authority_sensory_split', (6, 6))

        if split == (9, 3):
            mode = ArchitectureMode.SPLIT_9_3
        elif split == (6, 6):
            mode = ArchitectureMode.SPLIT_6_6
        elif split == (12, 0):
            mode = ArchitectureMode.SPLIT_12_0
        else:
            # Default to 6:6
            mode = ArchitectureMode.SPLIT_6_6

        num_layers = inference_config.get('num_layers', 12)

        return cls(mode=mode, num_layers=num_layers)

    def get_cache_priority(self, layer_idx: int) -> str:
        """
        Get caching priority for layer (for memory optimization).

        Authority layers: HIGH priority (cache aggressively)
        Sensory layers: MEDIUM priority (can recompute if needed)

        Args:
            layer_idx: Layer index (0-based)

        Returns:
            priority: "HIGH", "MEDIUM", or "LOW"
        """
        if layer_idx in self._authority_layers:
            return "HIGH"
        elif layer_idx in self._sensory_layers:
            return "MEDIUM"
        return "LOW"

    def get_temperature_adjustment(
        self,
        layer_idx: int,
        base_temp: float,
    ) -> float:
        """
        Adjust attention temperature per layer type.

        Sensory layers may benefit from sharper attention (lower temp)
        for more precise token selection.

        Args:
            layer_idx: Layer index
            base_temp: Base temperature

        Returns:
            adjusted_temp: Adjusted temperature
        """
        if layer_idx in self._sensory_layers:
            # Slightly sharper for sensory (expression) layers
            return base_temp * 0.9
        return base_temp

    def get_layer_role(self, layer_idx: int) -> str:
        """
        Get semantic role of layer.

        Args:
            layer_idx: Layer index

        Returns:
            role: "authority" (meaning) or "sensory" (expression)
        """
        if layer_idx in self._authority_layers:
            return "authority"
        return "sensory"

    def get_ontological_name(self, layer_idx: int) -> str:
        """
        Get ontological layer name (O1-O12).

        Args:
            layer_idx: Layer index (0-based)

        Returns:
            name: Ontological name (O1, O2, ..., O12)
        """
        ontological_names = [
            "O1 (Potential)",
            "O2 (Density)",
            "O3 (Activity)",
            "O4 (Binding)",
            "O5 (Structuring)",
            "O6 (Diversifying)",
            "O7 (Integrating)",
            "O8 (Rhythmic)",
            "O9 (Conscious)",
            "O10 (Knowing)",
            "O11 (Manifesting)",
            "O12 (Absolving)",
        ]
        if 0 <= layer_idx < len(ontological_names):
            return ontological_names[layer_idx]
        return f"O{layer_idx + 1}"

    def get_layer_weights(self) -> Dict[int, float]:
        """
        Get importance weights for each layer.

        Authority layers get higher weights for quality scoring.

        Returns:
            weights: Dict mapping layer_idx -> weight
        """
        weights = {}

        for i in range(self.num_layers):
            if i in self._authority_layers:
                # Authority layers: higher weight, decreasing with depth
                weight = 1.0 - (i / len(self._authority_layers)) * 0.3
            else:
                # Sensory layers: lower base weight
                sensory_idx = i - len(self._authority_layers)
                weight = 0.7 - (sensory_idx / len(self._sensory_layers)) * 0.2

            weights[i] = max(0.3, weight)

        return weights

    def get_extraction_layers(self, mode: str = "minimal") -> List[int]:
        """
        Get which layers to extract hidden states from.

        Args:
            mode: "minimal" (O1, O12), "authority" (authority only),
                  "full" (all layers)

        Returns:
            layers: List of layer indices to extract
        """
        if mode == "minimal":
            # Just first and last for karma
            return [0, self.num_layers - 1]
        elif mode == "authority":
            return self._authority_layers
        elif mode == "sensory":
            return self._sensory_layers
        elif mode == "key":
            # Key layers: first, middle, last
            return [0, self.num_layers // 2, self.num_layers - 1]
        else:
            # Full extraction
            return list(range(self.num_layers))

    def describe(self) -> str:
        """Get human-readable description."""
        return (
            f"LayerConfig: {self.mode.value} split\n"
            f"  Authority: layers {self._authority_layers[0]}-{self._authority_layers[-1]} "
            f"({len(self._authority_layers)} layers)\n"
            f"  Sensory: layers {self._sensory_layers[0]}-{self._sensory_layers[-1]} "
            f"({len(self._sensory_layers)} layers)" if self._sensory_layers else ""
        )


# Pre-configured instances
CONFIG_9_3 = LayerInferenceConfig(mode=ArchitectureMode.SPLIT_9_3)
CONFIG_6_6 = LayerInferenceConfig(mode=ArchitectureMode.SPLIT_6_6)
CONFIG_STANDARD = LayerInferenceConfig(mode=ArchitectureMode.SPLIT_12_0)
