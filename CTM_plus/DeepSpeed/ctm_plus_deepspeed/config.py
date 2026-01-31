"""
Configuration for CTM+ DeepSpeed integration.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CTMDeepSpeedConfig:
    """
    Configuration for CTM+ offload management in DeepSpeed.

    Attributes:
        victim_sample_size: Number of tensors to sample for eviction decisions.
        promotion_threshold: Minimum score to move tensor to GPU.
        offload_threshold: Score below which tensor is offloaded to CPU.
        enable_smart_offload: Use CTM+ scoring vs simple LRU.
        shadow_size: Size of ghost cache for tracking offloaded tensors.
        neighbor_window: Window size for access pattern tracking.
        prefetch_ahead: Number of tensors to prefetch ahead.
        async_offload: Enable async CPU-GPU transfers.
        pin_optimizer_states: Pin optimizer states to prevent offload.
        adaptive_p_learning_rate: Learning rate for ARC-style adaptation.
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

    # Scoring weights
    weight_recency: float = 0.35
    weight_frequency: float = 0.30
    weight_size: float = 0.15  # Larger tensors penalized
    weight_compute: float = 0.10  # Tensors in compute graph protected
    weight_gradient: float = 0.10  # Gradient tensors protected during backward

    @classmethod
    def for_training(cls) -> "CTMDeepSpeedConfig":
        """Optimized for training (frequent param/grad access)."""
        return cls(
            victim_sample_size=64,
            promotion_threshold=0.25,
            offload_threshold=0.15,
            prefetch_ahead=3,
            pin_optimizer_states=True,
            pin_gradients=True,
            weight_recency=0.30,
            weight_frequency=0.25,
            weight_size=0.15,
            weight_compute=0.15,
            weight_gradient=0.15,
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
        """Optimized for ZeRO-Offload (optimizer states on CPU)."""
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
        )

    @classmethod
    def for_large_model(cls) -> "CTMDeepSpeedConfig":
        """Optimized for large models (aggressive offloading)."""
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
        )
