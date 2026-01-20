"""
Configuration for Phase-Quad Image Generator.

This module defines the configuration hierarchy for the Phase-Quad
architecture, including presets for different use cases.
"""

from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum


class VAEType(Enum):
    """Supported VAE types."""
    SDXL = "sdxl"  # 4 channels, 8x compression
    SD15 = "sd15"  # 4 channels, 8x compression
    FLUX = "flux"  # 16 channels, 8x compression (deferred to v2)


class TextEncoderType(Enum):
    """Supported text encoder types."""
    CLIP_L = "clip_l"  # CLIP ViT-L/14, 768-dim
    CLIP_G = "clip_g"  # CLIP ViT-bigG, 1280-dim
    T5_XXL = "t5_xxl"  # T5-XXL, 4096-dim (deferred to v2)


@dataclass
class VAEConfig:
    """
    VAE configuration.

    Per design doc Appendix E.2.1:
    - Default: SDXL VAE (4 channels, 8x compression)
    - Well-understood latent statistics
    - Compatible with many datasets
    """
    vae_type: VAEType = VAEType.SDXL
    in_channels: int = 4  # Latent channels
    compression_factor: int = 8  # Spatial compression
    scaling_factor: float = 0.13025  # SDXL VAE scaling


@dataclass
class TextEncoderConfig:
    """
    Text encoder configuration.

    Per design doc Appendix E.2.1:
    - Default: CLIP (768-dim)
    - Matches SD/SDXL ecosystem
    - Simpler LocalMixer integration
    """
    encoder_type: TextEncoderType = TextEncoderType.CLIP_L
    embed_dim: int = 768  # Text embedding dimension
    max_length: int = 77  # Maximum token length


@dataclass
class PhaseConfig:
    """Configuration for Phase Integrator."""
    decay_gamma: float = 0.9  # Default EMA decay
    learned_decay: bool = True  # Learn per-head decay
    bounded_phase: bool = True  # MANDATORY: Use pi*sin() for bounded phase


@dataclass
class QuadConfig:
    """Configuration for Quad Retriever."""
    topk: int = 64  # Number of proposals per position
    use_2d_rope: bool = True  # Use standard 2D RoPE


@dataclass
class GateConfig:
    """Configuration for Gate Mixer."""
    default_gamma: float = 0.9  # EMA decay for state update
    default_alpha: float = 0.1  # Alignment authority coefficient
    clamp_min: float = 0.8  # Minimum alignment clamp
    clamp_max: float = 1.2  # Maximum alignment clamp


@dataclass
class LocalMixerConfig:
    """Configuration for Local Mixer."""
    window_size: int = 8  # Local attention window
    use_cross_attn: bool = True  # Include cross-attention to text


@dataclass
class BlockConfig:
    """Configuration for CognadeVisionBlock."""
    embed_dim: int = 768  # Model width D
    num_heads: int = 12  # Number of attention heads H
    ffn_ratio: float = 4.0  # FFN hidden dimension ratio
    dropout: float = 0.1  # Dropout rate
    phase: PhaseConfig = field(default_factory=PhaseConfig)
    quad: QuadConfig = field(default_factory=QuadConfig)
    gate: GateConfig = field(default_factory=GateConfig)
    local: LocalMixerConfig = field(default_factory=LocalMixerConfig)


@dataclass
class DiffusionConfig:
    """Configuration for diffusion training."""
    num_train_timesteps: int = 1000
    prediction_type: Literal["epsilon", "v_prediction"] = "epsilon"
    beta_schedule: str = "scaled_linear"
    beta_start: float = 0.00085
    beta_end: float = 0.012


@dataclass
class TemperatureScheduleConfig:
    """Configuration for temperature schedule."""
    start: float = 2.0  # Initial temperature (soft gates)
    end: float = 1.0  # Final temperature (sharper selection)
    warmup_steps: int = 50000  # Steps to reach final temperature
    schedule_type: Literal["linear", "cosine"] = "linear"


@dataclass
class TrainingConfig:
    """Configuration for training loop."""
    batch_size: int = 32
    learning_rate: float = 1e-4
    weight_decay: float = 0.01
    max_steps: int = 500000
    warmup_steps: int = 10000
    gradient_clip: float = 1.0
    mixed_precision: bool = True
    compile_model: bool = False  # torch.compile
    temperature: TemperatureScheduleConfig = field(default_factory=TemperatureScheduleConfig)
    diffusion: DiffusionConfig = field(default_factory=DiffusionConfig)


@dataclass
class PhaseQuadVisionConfig:
    """
    Main configuration for Phase-Quad Image Generator.

    Aggregates all sub-configurations and provides presets.

    Attributes:
        patch_size: Patch size in latent space (2, 4, or 8)
        num_blocks: Number of CognadeVisionBlock layers
        block: Block-level configuration
        vae: VAE configuration
        text_encoder: Text encoder configuration
        training: Training configuration
    """
    # Model architecture
    patch_size: int = 2
    num_blocks: int = 12
    block: BlockConfig = field(default_factory=BlockConfig)

    # External models
    vae: VAEConfig = field(default_factory=VAEConfig)
    text_encoder: TextEncoderConfig = field(default_factory=TextEncoderConfig)

    # Training
    training: TrainingConfig = field(default_factory=TrainingConfig)

    @property
    def embed_dim(self) -> int:
        """Model embedding dimension."""
        return self.block.embed_dim

    @property
    def num_heads(self) -> int:
        """Number of attention heads."""
        return self.block.num_heads

    @property
    def head_dim(self) -> int:
        """Dimension per head."""
        return self.embed_dim // self.num_heads

    @property
    def topk(self) -> int:
        """Number of TopK proposals."""
        return self.block.quad.topk

    @classmethod
    def tiny(cls) -> "PhaseQuadVisionConfig":
        """
        Tiny configuration for quick testing.

        - 4 blocks, 256 width, 4 heads
        - ~10M parameters
        """
        return cls(
            patch_size=4,
            num_blocks=4,
            block=BlockConfig(
                embed_dim=256,
                num_heads=4,
                ffn_ratio=4.0,
                quad=QuadConfig(topk=32),
                local=LocalMixerConfig(window_size=4),
            ),
        )

    @classmethod
    def small(cls) -> "PhaseQuadVisionConfig":
        """
        Small configuration for development.

        - 8 blocks, 512 width, 8 heads
        - ~100M parameters
        """
        return cls(
            patch_size=2,
            num_blocks=8,
            block=BlockConfig(
                embed_dim=512,
                num_heads=8,
                ffn_ratio=4.0,
                quad=QuadConfig(topk=64),
                local=LocalMixerConfig(window_size=8),
            ),
        )

    @classmethod
    def base(cls) -> "PhaseQuadVisionConfig":
        """
        Base configuration (recommended for PoC).

        - 12 blocks, 768 width, 12 heads
        - ~300M parameters
        """
        return cls(
            patch_size=2,
            num_blocks=12,
            block=BlockConfig(
                embed_dim=768,
                num_heads=12,
                ffn_ratio=4.0,
                quad=QuadConfig(topk=64),
                local=LocalMixerConfig(window_size=8),
            ),
        )

    @classmethod
    def large(cls) -> "PhaseQuadVisionConfig":
        """
        Large configuration for full-scale experiments.

        - 24 blocks, 1024 width, 16 heads
        - ~700M parameters
        """
        return cls(
            patch_size=2,
            num_blocks=24,
            block=BlockConfig(
                embed_dim=1024,
                num_heads=16,
                ffn_ratio=4.0,
                quad=QuadConfig(topk=64),
                local=LocalMixerConfig(window_size=8),
            ),
        )

    def validate(self) -> None:
        """Validate configuration consistency."""
        # Embed dim must be divisible by num_heads
        if self.embed_dim % self.num_heads != 0:
            raise ValueError(
                f"embed_dim ({self.embed_dim}) must be divisible by "
                f"num_heads ({self.num_heads})"
            )

        # Bounded phase is mandatory
        if not self.block.phase.bounded_phase:
            raise ValueError(
                "bounded_phase must be True. Unbounded phase is explicitly disabled "
                "per design specification (invariant 10.1.2)."
            )

        # Temperature schedule must start >= 1.5
        if self.training.temperature.start < 1.5:
            raise ValueError(
                f"Temperature start ({self.training.temperature.start}) must be >= 1.5 "
                "per design specification (invariant 10.1.5)."
            )
