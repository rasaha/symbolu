"""
Configuration for Phase-Quad Video Generator.

This module defines the configuration hierarchy for the video extension
of the Phase-Quad architecture, extending the image config with temporal
settings.
"""

from dataclasses import dataclass, field
from typing import Optional, Literal
from enum import Enum

from symbolu.vision.config import (
    PhaseConfig,
    QuadConfig,
    GateConfig,
    LocalMixerConfig,
    TextEncoderConfig,
    DiffusionConfig,
    TemperatureScheduleConfig,
)


class VideoVAEType(Enum):
    """Supported video VAE types."""
    COGVIDEOX_2B = "cogvideox_2b"  # 16 channels, 4x temporal, 8x spatial
    COGVIDEOX_5B = "cogvideox_5b"  # Same compression ratios
    MOCK = "mock"  # For testing without pretrained weights


@dataclass
class VideoVAEConfig:
    """
    Video VAE configuration.

    Video VAEs handle both temporal and spatial compression:
    - Temporal: T -> T' (typically 4:1)
    - Spatial: H,W -> H',W' (typically 8:1)
    """
    vae_type: VideoVAEType = VideoVAEType.COGVIDEOX_2B
    latent_channels: int = 16  # CogVideoX uses 16 channels
    temporal_compression: int = 4  # T -> T/4
    spatial_compression: int = 8  # H,W -> H/8, W/8
    scaling_factor: float = 0.7  # CogVideoX specific

    @property
    def model_id(self) -> str:
        """Get HuggingFace model ID for this VAE type."""
        mapping = {
            VideoVAEType.COGVIDEOX_2B: "THUDM/CogVideoX-2b",
            VideoVAEType.COGVIDEOX_5B: "THUDM/CogVideoX-5b",
            VideoVAEType.MOCK: "mock",
        }
        return mapping[self.vae_type]


@dataclass
class VideoPhaseConfig(PhaseConfig):
    """
    Configuration for Phase Integrator 3D.

    Extends image PhaseConfig with temporal settings.
    """
    # Temporal-specific decay settings
    temporal_decay_gamma: float = 0.95  # Higher default for temporal coherence
    independent_time_decay: bool = True  # Learn separate decay for time axis


@dataclass
class LocalMixer3DConfig(LocalMixerConfig):
    """Configuration for 3D Local Mixer."""
    window_size: int = 8  # Spatial window
    temporal_window: int = 4  # Temporal window (frames)
    use_cross_attn: bool = True


@dataclass
class VideoBlockConfig:
    """Configuration for Phase-Quad 3D Block."""
    embed_dim: int = 768
    num_heads: int = 12
    ffn_ratio: float = 4.0
    dropout: float = 0.1
    phase: VideoPhaseConfig = field(default_factory=VideoPhaseConfig)
    quad: QuadConfig = field(default_factory=QuadConfig)
    gate: GateConfig = field(default_factory=GateConfig)
    local: LocalMixer3DConfig = field(default_factory=LocalMixer3DConfig)


@dataclass
class VideoTrainingConfig:
    """Configuration for video training loop."""
    batch_size: int = 4  # Smaller batch size due to memory
    learning_rate: float = 1e-5  # Lower LR for fine-tuning from image
    weight_decay: float = 0.01
    max_steps: int = 200000
    warmup_steps: int = 5000
    gradient_clip: float = 1.0
    mixed_precision: bool = True
    compile_model: bool = False
    gradient_accumulation_steps: int = 4  # Effective batch = 16
    temperature: TemperatureScheduleConfig = field(default_factory=TemperatureScheduleConfig)
    diffusion: DiffusionConfig = field(default_factory=DiffusionConfig)


@dataclass
class VideoInferenceConfig:
    """Configuration for video inference."""
    num_inference_steps: int = 50  # DDIM steps
    guidance_scale: float = 7.5  # CFG scale
    fps: int = 8  # Output frames per second
    eta: float = 0.0  # DDIM eta (0 = deterministic)


@dataclass
class PhaseQuadVideoConfig:
    """
    Main configuration for Phase-Quad Video Generator.

    Extends image configuration with temporal settings.

    Attributes:
        num_frames: Number of output video frames
        height: Output video height
        width: Output video width
        patch_size: Spatial patch size in latent space
        temporal_patch_size: Temporal patch size (usually 1)
        num_blocks: Number of Phase-Quad 3D blocks
        block: Block-level configuration
        vae: Video VAE configuration
        text_encoder: Text encoder configuration
        training: Training configuration
        inference: Inference configuration
    """
    # Video dimensions
    num_frames: int = 16
    height: int = 256
    width: int = 256

    # Patch settings
    patch_size: int = 2  # Spatial
    temporal_patch_size: int = 1

    # Model architecture
    num_blocks: int = 12
    block: VideoBlockConfig = field(default_factory=VideoBlockConfig)

    # External models
    vae: VideoVAEConfig = field(default_factory=VideoVAEConfig)
    text_encoder: TextEncoderConfig = field(default_factory=TextEncoderConfig)

    # Training and inference
    training: VideoTrainingConfig = field(default_factory=VideoTrainingConfig)
    inference: VideoInferenceConfig = field(default_factory=VideoInferenceConfig)

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

    @property
    def latent_frames(self) -> int:
        """Number of frames in latent space after VAE compression."""
        return self.num_frames // self.vae.temporal_compression

    @property
    def latent_height(self) -> int:
        """Height in latent space after VAE compression."""
        return self.height // self.vae.spatial_compression

    @property
    def latent_width(self) -> int:
        """Width in latent space after VAE compression."""
        return self.width // self.vae.spatial_compression

    @property
    def num_patches_per_frame(self) -> int:
        """Number of patches per frame."""
        h_patches = self.latent_height // self.patch_size
        w_patches = self.latent_width // self.patch_size
        return h_patches * w_patches

    @property
    def total_patches(self) -> int:
        """Total number of patches in the video."""
        return self.latent_frames * self.num_patches_per_frame

    @classmethod
    def tiny(cls) -> "PhaseQuadVideoConfig":
        """
        Tiny configuration for quick testing.

        - 8 frames at 128x128
        - 4 blocks, 256 width
        - ~15M parameters
        """
        return cls(
            num_frames=8,
            height=128,
            width=128,
            patch_size=2,
            num_blocks=4,
            block=VideoBlockConfig(
                embed_dim=256,
                num_heads=4,
                ffn_ratio=4.0,
                quad=QuadConfig(topk=32),
                local=LocalMixer3DConfig(window_size=4, temporal_window=2),
            ),
            vae=VideoVAEConfig(vae_type=VideoVAEType.MOCK),
        )

    @classmethod
    def small(cls) -> "PhaseQuadVideoConfig":
        """
        Small configuration for development.

        - 16 frames at 256x256
        - 8 blocks, 512 width
        - ~150M parameters
        - Memory: ~8 GB (fp16)
        """
        return cls(
            num_frames=16,
            height=256,
            width=256,
            patch_size=2,
            num_blocks=8,
            block=VideoBlockConfig(
                embed_dim=512,
                num_heads=8,
                ffn_ratio=4.0,
                quad=QuadConfig(topk=64),
                local=LocalMixer3DConfig(window_size=8, temporal_window=4),
            ),
        )

    @classmethod
    def base(cls) -> "PhaseQuadVideoConfig":
        """
        Base configuration for production.

        - 32 frames at 480x720
        - 12 blocks, 768 width
        - ~400M parameters
        - Memory: ~24 GB (fp16)
        """
        return cls(
            num_frames=32,
            height=480,
            width=720,
            patch_size=2,
            num_blocks=12,
            block=VideoBlockConfig(
                embed_dim=768,
                num_heads=12,
                ffn_ratio=4.0,
                quad=QuadConfig(topk=64),
                local=LocalMixer3DConfig(window_size=8, temporal_window=4),
            ),
        )

    @classmethod
    def large(cls) -> "PhaseQuadVideoConfig":
        """
        Large configuration for high-quality generation.

        - 64 frames at 720x1280
        - 24 blocks, 1024 width
        - ~900M parameters
        - Memory: ~48 GB (fp16)
        """
        return cls(
            num_frames=64,
            height=720,
            width=1280,
            patch_size=2,
            num_blocks=24,
            block=VideoBlockConfig(
                embed_dim=1024,
                num_heads=16,
                ffn_ratio=4.0,
                quad=QuadConfig(topk=64),
                local=LocalMixer3DConfig(window_size=8, temporal_window=8),
            ),
        )

    @classmethod
    def from_image_config(
        cls,
        image_config,
        num_frames: int = 16,
        height: int = 256,
        width: int = 256,
    ) -> "PhaseQuadVideoConfig":
        """
        Create video config from an existing image config.

        This is useful for progressive training where we initialize
        from a pretrained image model.

        Args:
            image_config: PhaseQuadVisionConfig instance.
            num_frames: Number of video frames.
            height: Video height.
            width: Video width.

        Returns:
            PhaseQuadVideoConfig with matching model dimensions.
        """
        return cls(
            num_frames=num_frames,
            height=height,
            width=width,
            patch_size=image_config.patch_size,
            num_blocks=image_config.num_blocks,
            block=VideoBlockConfig(
                embed_dim=image_config.block.embed_dim,
                num_heads=image_config.block.num_heads,
                ffn_ratio=image_config.block.ffn_ratio,
                dropout=image_config.block.dropout,
                quad=image_config.block.quad,
                gate=image_config.block.gate,
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

        # Frames must be divisible by temporal compression
        if self.num_frames % self.vae.temporal_compression != 0:
            raise ValueError(
                f"num_frames ({self.num_frames}) must be divisible by "
                f"temporal_compression ({self.vae.temporal_compression})"
            )

        # Spatial dimensions must be divisible by spatial compression
        if self.height % self.vae.spatial_compression != 0:
            raise ValueError(
                f"height ({self.height}) must be divisible by "
                f"spatial_compression ({self.vae.spatial_compression})"
            )
        if self.width % self.vae.spatial_compression != 0:
            raise ValueError(
                f"width ({self.width}) must be divisible by "
                f"spatial_compression ({self.vae.spatial_compression})"
            )

        # Latent dimensions must be divisible by patch size
        if self.latent_height % self.patch_size != 0:
            raise ValueError(
                f"latent_height ({self.latent_height}) must be divisible by "
                f"patch_size ({self.patch_size})"
            )
        if self.latent_width % self.patch_size != 0:
            raise ValueError(
                f"latent_width ({self.latent_width}) must be divisible by "
                f"patch_size ({self.patch_size})"
            )

    def get_memory_estimate_gb(self, batch_size: int = 1, precision: str = "fp16") -> float:
        """
        Estimate GPU memory usage.

        Args:
            batch_size: Batch size.
            precision: "fp16" or "fp32".

        Returns:
            Estimated memory in GB.
        """
        bytes_per_param = 2 if precision == "fp16" else 4

        # Model parameters (rough estimate)
        params_per_block = (
            self.embed_dim * self.embed_dim * 4  # FFN
            + self.embed_dim * self.embed_dim * 3  # Phase projections
            + self.topk * self.embed_dim  # Quad
        )
        total_params = self.num_blocks * params_per_block
        model_memory = total_params * bytes_per_param

        # Activation memory
        seq_len = self.total_patches
        activation_memory = (
            batch_size * seq_len * self.embed_dim * self.num_blocks * bytes_per_param
        )

        # VAE memory (rough)
        vae_memory = 2 * 1024**3  # ~2GB for CogVideoX

        total = (model_memory + activation_memory + vae_memory) / (1024**3)
        return round(total, 1)
