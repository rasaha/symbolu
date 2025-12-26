"""
Symbol-U Vision Configuration
=============================

Configuration for the 10-layer ontological hierarchy and
frequency parameters based on Symbol-U patent principles.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
import math


# ============================================================================
# Ontological Layer Definitions
# ============================================================================

# Symbol-U prescribed frequencies (Hz) for each cognitive layer
# These map to neural oscillation bands in cognitive neuroscience
LAYER_FREQUENCIES: Dict[int, float] = {
    1: 10000.0,  # Sensory: Gamma burst (raw input processing)
    2: 500.0,    # Feature: High gamma (edge/texture detection)
    3: 200.0,    # Object: Gamma (object part binding)
    4: 100.0,    # Language: Beta-gamma (nameable objects)
    5: 40.0,     # Semantic: Gamma (conceptual binding)
    6: 20.0,     # Episodic: Beta (contextual memory)
    7: 10.0,     # Reasoning: Alpha (logical relations)
    8: 5.0,      # Social: Theta (agent/intention modeling)
    9: 1.0,      # Existential: Delta (scene meaning)
    10: 0.1,     # Universal: Infra-slow (global coherence)
}

# Semantic names for each layer
LAYER_NAMES: Dict[int, str] = {
    1: "Sensory",      # Raw pixel processing
    2: "Feature",      # Edges, textures, colors
    3: "Object",       # Object parts, shapes
    4: "Language",     # Nameable entities
    5: "Semantic",     # Concepts, categories
    6: "Episodic",     # Context, memory
    7: "Reasoning",    # Logical relations
    8: "Social",       # Agents, intentions
    9: "Existential",  # Scene meaning, purpose
    10: "Universal",   # Global coherence, unity
}

# Mapping to robotics 12D ontology (for integration)
LAYER_TO_ROBOTICS_12D: Dict[int, str] = {
    1: "O1_POTENTIAL",    # Sensor readiness
    2: "O5_COGNITION",    # Perception processing
    3: "O5_COGNITION",    # Perception processing
    4: "O4_STRUCTURE",    # Body schema/kinematics
    5: "O5_COGNITION",    # Perception processing
    6: "O9_WITNESSES",    # World model
    7: "O7_REASONING",    # Path/task planning
    8: "O10_UNIFYING",    # Multi-agent coordination
    9: "O8_PURPOSE",      # Goal hierarchy
    10: "O11_INTEGRATION", # Sensor fusion
}


@dataclass
class OntologicalLayerConfig:
    """Configuration for a single ontological layer."""

    layer_idx: int
    name: str
    frequency: float
    channels: int

    # Coherence thresholds
    coherence_threshold: float = 0.7

    # Phase parameters
    phase_trainable: bool = True

    # Attention parameters
    num_heads: int = 8

    @property
    def harmonic_ratio(self) -> float:
        """Ratio to Layer 10 (master) frequency."""
        return self.frequency / LAYER_FREQUENCIES[10]

    @property
    def wavelength_tokens(self) -> float:
        """Wavelength in terms of token positions."""
        # Normalize so Layer 10 has wavelength of ~1000 tokens
        return 1000.0 / self.harmonic_ratio


@dataclass
class SymbolUViTConfig:
    """Configuration for Symbol-U Vision Transformer."""

    # Image parameters
    img_size: int = 224
    patch_size: int = 16
    in_channels: int = 3

    # Model dimensions
    embed_dim: int = 512

    # Layer-specific channel progression
    # Follows cognitive principle: lower layers process more, higher integrate
    layer_channels: Dict[int, int] = field(default_factory=lambda: {
        1: 64,    # Sensory: Many features
        2: 128,   # Feature: Edge combinations
        3: 256,   # Object: Part assemblies
        4: 512,   # Language: Rich representations
        5: 512,   # Semantic: Concept space
        6: 512,   # Episodic: Context
        7: 512,   # Reasoning: Relations
        8: 512,   # Social: Agents
        9: 512,   # Existential: Meaning
        10: 512,  # Universal: Unity
    })

    # Attention configuration
    num_heads: int = 8
    mlp_ratio: float = 4.0

    # Coherence parameters
    coherence_threshold: float = 0.7
    use_coherence_gating: bool = True

    # Phase-locking parameters
    use_phase_locking: bool = True
    phase_trainable: bool = True

    # BCVF parameters
    use_bcvf: bool = True
    bcvf_threshold: float = 0.8

    # Dropout
    dropout: float = 0.1
    attention_dropout: float = 0.1

    # Output
    num_classes: int = 1000

    # Training
    layer_drop_rate: float = 0.0  # Stochastic depth

    @property
    def num_patches(self) -> int:
        return (self.img_size // self.patch_size) ** 2

    @property
    def patch_dim(self) -> int:
        return self.in_channels * self.patch_size * self.patch_size

    def get_layer_config(self, layer_idx: int) -> OntologicalLayerConfig:
        """Get configuration for a specific ontological layer."""
        return OntologicalLayerConfig(
            layer_idx=layer_idx,
            name=LAYER_NAMES[layer_idx],
            frequency=LAYER_FREQUENCIES[layer_idx],
            channels=self.layer_channels.get(layer_idx, self.embed_dim),
            coherence_threshold=self.coherence_threshold,
            phase_trainable=self.phase_trainable,
            num_heads=self.num_heads,
        )


@dataclass
class SymbolUConvConfig:
    """Configuration for Symbol-U Convolutional Encoder."""

    # Image parameters
    img_size: int = 224
    in_channels: int = 3

    # Layer channel progression
    layer_channels: Dict[int, int] = field(default_factory=lambda: {
        1: 32,    # Sensory
        2: 64,    # Feature
        3: 128,   # Object
        4: 256,   # Language
        5: 512,   # Semantic
        6: 512,   # Episodic
        7: 512,   # Reasoning
        8: 512,   # Social
        9: 512,   # Existential
        10: 512,  # Universal
    })

    # Convolution parameters
    kernel_size: int = 3
    stride: int = 1
    padding: int = 1

    # Pooling (applied every 2 layers to reduce spatial size)
    pool_layers: List[int] = field(default_factory=lambda: [2, 4, 6, 8])
    pool_size: int = 2

    # Phase-locking
    use_phase_locking: bool = True

    # Output
    num_classes: int = 1000

    def get_layer_config(self, layer_idx: int) -> OntologicalLayerConfig:
        """Get configuration for a specific layer."""
        return OntologicalLayerConfig(
            layer_idx=layer_idx,
            name=LAYER_NAMES[layer_idx],
            frequency=LAYER_FREQUENCIES[layer_idx],
            channels=self.layer_channels.get(layer_idx, 512),
        )


# ============================================================================
# Preset Configurations
# ============================================================================

def su_vit_tiny() -> SymbolUViTConfig:
    """Tiny Symbol-U ViT for testing."""
    return SymbolUViTConfig(
        img_size=224,
        patch_size=16,
        embed_dim=192,
        num_heads=3,
        layer_channels={i: 192 for i in range(1, 11)},
    )


def su_vit_small() -> SymbolUViTConfig:
    """Small Symbol-U ViT."""
    return SymbolUViTConfig(
        img_size=224,
        patch_size=16,
        embed_dim=384,
        num_heads=6,
        layer_channels={i: 384 for i in range(1, 11)},
    )


def su_vit_base() -> SymbolUViTConfig:
    """Base Symbol-U ViT (default)."""
    return SymbolUViTConfig(
        img_size=224,
        patch_size=16,
        embed_dim=512,
        num_heads=8,
    )


def su_vit_large() -> SymbolUViTConfig:
    """Large Symbol-U ViT."""
    return SymbolUViTConfig(
        img_size=224,
        patch_size=16,
        embed_dim=768,
        num_heads=12,
        layer_channels={i: 768 for i in range(1, 11)},
    )
