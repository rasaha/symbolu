"""
Configuration for CTM+ DeepSpeed integration.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CTMDeepSpeedConfig:
    """
    Configuration for CTM+ offload management in DeepSpeed.

    Eviction / placement attributes:
        victim_sample_size: Number of tensors to sample for eviction decisions.
        promotion_threshold: Minimum score to move tensor to GPU.
        offload_threshold: Score below which tensor is offloaded to CPU.
        enable_smart_offload: Use CTM+ scoring vs simple LRU.
        shadow_size: Size of ghost cache for tracking offloaded tensors.
        neighbor_window: Window size for access pattern tracking.
        prefetch_ahead: Number of tensors to prefetch ahead.
        async_offload: Enable async CPU-GPU transfers.
        pin_optimizer_states: Pin optimizer states to prevent offload.
        pin_gradients: Pin gradient tensors to prevent offload (disable to allow
            TurboQuant compression; weight_gradient scoring still protects them).
        adaptive_p_learning_rate: Learning rate for ARC-style p adaptation.
        initial_p: Starting value for the ARC recency/frequency balance (0-1).

    TurboQuant compression attributes:
        enable_turboquant: Master switch; also controls to_turboquant_config().
        turboquant_angle_bits: PolarQuant angular quantization bits (2/3/4).
        turboquant_enable_qjl: Apply QJL residual correction after PolarQuant.
        turboquant_segment_dim: Chunk size for segmenting training tensors.
        turboquant_compress_gradients: Compress gradient tensors on CPU offload.
        turboquant_compress_optimizer_states: Compress optimizer states on offload.
        turboquant_min_compress_elements: Skip compression for tiny tensors.

    Scoring weights (must sum to ≤ 1.0):
        weight_recency, weight_frequency, weight_size, weight_compute,
        weight_gradient.
    """

    # Victim selection
    victim_sample_size: int = 48
    promotion_threshold: float = 0.3
    offload_threshold: float = 0.2
    enable_smart_offload: bool = True

    # Shadow tiers
    shadow_size: int = 2048

    # Access tracking
    neighbor_window: int = 32

    # Prefetching
    prefetch_ahead: int = 2
    async_offload: bool = True

    # Pinning
    pin_optimizer_states: bool = True
    pin_gradients: bool = False

    # Adaptive p
    adaptive_p_learning_rate: float = 0.1
    initial_p: float = 0.5

    # TurboQuant compression (gradient / optimizer-state offload)
    enable_turboquant: bool = False
    turboquant_angle_bits: int = 3
    turboquant_enable_qjl: bool = True
    turboquant_segment_dim: int = 128
    turboquant_compress_gradients: bool = True
    turboquant_compress_optimizer_states: bool = True
    turboquant_min_compress_elements: int = 512

    # Scoring weights
    weight_recency: float = 0.35
    weight_frequency: float = 0.30
    weight_size: float = 0.15  # Larger tensors penalized
    weight_compute: float = 0.10  # Tensors in compute graph protected
    weight_gradient: float = 0.10  # Gradient tensors protected during backward

    def to_turboquant_config(self) -> "Any":
        """Build a TurboQuantTrainingConfig from the turboquant_* fields on this config.

        This bridges CTMDeepSpeedConfig settings into TurboQuantOffloadManager.create()
        so that customising turboquant_angle_bits (etc.) on CTMDeepSpeedConfig is
        sufficient — no need to build a separate TurboQuantTrainingConfig by hand.

        Returns None when enable_turboquant is False (disables compression entirely).
        """
        if not self.enable_turboquant:
            return None
        from .turboquant_offload import TurboQuantTrainingConfig
        return TurboQuantTrainingConfig(
            angle_bits=self.turboquant_angle_bits,
            enable_qjl=self.turboquant_enable_qjl,
            segment_dim=self.turboquant_segment_dim,
            compress_gradients=self.turboquant_compress_gradients,
            compress_optimizer_states=self.turboquant_compress_optimizer_states,
            min_compress_elements=self.turboquant_min_compress_elements,
        )

    @classmethod
    def for_training(cls) -> "CTMDeepSpeedConfig":
        """Optimized for training (frequent param/grad access). TurboQuant on.

        pin_gradients is False so CTM can offload gradients to CPU where
        TurboQuant then compresses them.  The weight_gradient=0.15 scoring
        bias already protects gradients from eviction during the backward pass
        without hard-pinning them to GPU.
        """
        return cls(
            victim_sample_size=64,
            promotion_threshold=0.25,
            offload_threshold=0.15,
            prefetch_ahead=3,
            pin_optimizer_states=True,
            pin_gradients=False,   # allow eviction so TurboQuant can compress
            weight_recency=0.30,
            weight_frequency=0.25,
            weight_size=0.15,
            weight_compute=0.15,
            weight_gradient=0.15,  # scoring bias protects grads during backward
            enable_turboquant=True,
            turboquant_angle_bits=3,
            turboquant_compress_gradients=True,
            turboquant_compress_optimizer_states=True,
        )

    @classmethod
    def for_inference(cls) -> "CTMDeepSpeedConfig":
        """Optimized for inference (less frequent updates)."""
        return cls(
            victim_sample_size=32,
            promotion_threshold=0.35,
            offload_threshold=0.25,
            prefetch_ahead=1,
            pin_optimizer_states=False,
            pin_gradients=False,
            weight_recency=0.40,
            weight_frequency=0.30,
            weight_size=0.20,
            weight_compute=0.10,
            weight_gradient=0.0,
        )

    @classmethod
    def for_zero_offload(cls) -> "CTMDeepSpeedConfig":
        """Optimized for ZeRO-Offload (optimizer states on CPU). TurboQuant on."""
        return cls(
            victim_sample_size=48,
            promotion_threshold=0.30,
            offload_threshold=0.20,
            prefetch_ahead=2,
            async_offload=True,
            pin_optimizer_states=False,  # Let CTM+ manage
            weight_recency=0.35,
            weight_frequency=0.30,
            weight_size=0.15,
            weight_compute=0.10,
            weight_gradient=0.10,
            enable_turboquant=True,
            turboquant_angle_bits=3,
            turboquant_compress_gradients=True,
            turboquant_compress_optimizer_states=True,
        )

    @classmethod
    def for_large_model(cls) -> "CTMDeepSpeedConfig":
        """Optimized for large models (aggressive offloading). TurboQuant on."""
        return cls(
            victim_sample_size=96,
            promotion_threshold=0.40,
            offload_threshold=0.15,
            prefetch_ahead=4,
            async_offload=True,
            shadow_size=4096,
            neighbor_window=64,
            weight_recency=0.30,
            weight_frequency=0.25,
            weight_size=0.25,  # Penalize large tensors more
            weight_compute=0.10,
            weight_gradient=0.10,
            enable_turboquant=True,
            turboquant_angle_bits=3,
            turboquant_segment_dim=128,
            turboquant_compress_gradients=True,
            turboquant_compress_optimizer_states=True,
        )
