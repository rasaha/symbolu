"""
Symbol-U Vision Module
======================

Novel vision encoder architecture based on Symbol-U principles.

Key Innovations:
- 10-layer Ontological Feature Hierarchy (not arbitrary depth)
- Phase-Locked Convolutional Layers
- Coherence-Gated Attention (prevents hallucinations architecturally)
- Harmonic Positional Encoding (grounded in cognitive frequencies)
- Bidirectional Coherence Verification (BCVF)

This architecture embodies the Symbol-U patent principles directly
in the neural network design, rather than using off-the-shelf ViT/ResNet.
"""

from symbolu_robotics.vision.su_vit import (
    SymbolUViT,
    OntologicalTransformerBlock,
    CoherenceGatedAttention,
    HarmonicPositionalEncoding,
    BCVFBlock,
    PhaseLockConv2d,
    OntologicalConvBlock,
    SymbolUConvEncoder,
)

from symbolu_robotics.vision.config import (
    SymbolUViTConfig,
    OntologicalLayerConfig,
    LAYER_FREQUENCIES,
    LAYER_NAMES,
)

from symbolu_robotics.vision.loss import (
    SymbolULoss,
    compute_alignment_loss,
    compute_consistency_loss,
    compute_phase_loss,
)

__all__ = [
    # Core models
    "SymbolUViT",
    "SymbolUConvEncoder",
    # Building blocks
    "OntologicalTransformerBlock",
    "CoherenceGatedAttention",
    "HarmonicPositionalEncoding",
    "BCVFBlock",
    "PhaseLockConv2d",
    "OntologicalConvBlock",
    # Config
    "SymbolUViTConfig",
    "OntologicalLayerConfig",
    "LAYER_FREQUENCIES",
    "LAYER_NAMES",
    # Loss
    "SymbolULoss",
    "compute_alignment_loss",
    "compute_consistency_loss",
    "compute_phase_loss",
]
