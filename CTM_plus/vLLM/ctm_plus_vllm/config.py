"""
Configuration for CTM+ vLLM integration.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CTMvLLMConfig:
    """
    Configuration for CTM+ block manager in vLLM.

    Attributes:
        victim_sample_size: Number of blocks to sample for victim selection.
            Higher = better decisions, more CPU overhead.
        promotion_threshold: Minimum score to promote block to GPU.
        loop_pin_reuse_threshold: Reuse score threshold for pinning.
        loop_pin_neighbor_threshold: Neighbor hotness for pinning.
        enable_smart_victim: Use CTM+ scoring vs simple LRU.
        shadow_size: Size of ghost cache for tracking evicted blocks.
        neighbor_window: Window size for neighbor tracking.
        adaptive_p_learning_rate: Learning rate for ARC-style p adaptation.
    """

    # Victim selection
    victim_sample_size: int = 48
    promotion_threshold: float = 0.3
    loop_pin_reuse_threshold: float = 0.4
    loop_pin_neighbor_threshold: float = 0.3
    enable_smart_victim: bool = True

    # Shadow tiers (for ARC-style adaptation)
    shadow_size: int = 1024

    # Neighbor tracking
    neighbor_window: int = 16

    # Adaptive p (balances recency vs frequency)
    adaptive_p_learning_rate: float = 0.1
    initial_p: float = 0.5

    # Scoring weights (must sum to 1.0)
    weight_recency: float = 0.35
    weight_frequency: float = 0.30
    weight_reuse: float = 0.15
    weight_coherence: float = 0.10
    weight_neighbor: float = 0.10

    def __post_init__(self):
        total = (self.weight_recency + self.weight_frequency +
                 self.weight_reuse + self.weight_coherence + self.weight_neighbor)
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"Scoring weights must sum to 1.0, got {total:.3f}"
            )

    @classmethod
    def for_llm_inference(cls) -> "CTMvLLMConfig":
        """Optimized for LLM inference (temporal patterns, long sequences)."""
        return cls(
            victim_sample_size=32,
            promotion_threshold=0.2,
            loop_pin_reuse_threshold=0.3,
            weight_recency=0.35,
            weight_frequency=0.25,
            weight_reuse=0.20,
            weight_coherence=0.10,
            weight_neighbor=0.10,
        )

    @classmethod
    def for_batch_inference(cls) -> "CTMvLLMConfig":
        """Optimized for batch inference (many concurrent requests)."""
        return cls(
            victim_sample_size=64,
            promotion_threshold=0.35,
            weight_recency=0.45,
            weight_frequency=0.30,
            weight_reuse=0.10,
            weight_coherence=0.10,
            weight_neighbor=0.05,
        )

    @classmethod
    def for_streaming(cls) -> "CTMvLLMConfig":
        """Optimized for streaming inference (continuous generation)."""
        return cls(
            victim_sample_size=48,
            promotion_threshold=0.25,
            loop_pin_reuse_threshold=0.35,
            loop_pin_neighbor_threshold=0.25,
            weight_recency=0.40,
            weight_frequency=0.25,
            weight_reuse=0.20,
            weight_coherence=0.10,
            weight_neighbor=0.05,
        )
