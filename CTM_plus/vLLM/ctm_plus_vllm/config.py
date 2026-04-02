"""
Configuration for KV cache eviction policy.

These weights control how KVCachePolicy scores blocks for eviction.
They correspond to the 5 signals actually computed in attention_evictor.py:
  recency, frequency, attention, position, seq_priority.
"""

from dataclasses import dataclass


@dataclass
class KVCachePolicyConfig:
    """
    Scoring weights for KVCachePolicy.

    All phase-aware weights are defined in attention_evictor.PHASE_WEIGHTS.
    This config controls structural parameters only.

    Attributes:
        block_size: Tokens per KV block (must match vLLM's block_size).
        sink_tokens: Number of initial positions to treat as attention sinks.
        recent_window: Number of recent positions to protect from eviction.
        entity_attention_threshold: Cumulative attention above which a token
            is classified as ENTITY (protected).
        attention_ema_alpha: EMA smoothing for per-token attention tracking.
        victim_sample_size: Number of blocks to sample for victim selection.
    """

    block_size: int = 16
    sink_tokens: int = 4
    recent_window: int = 256
    entity_attention_threshold: float = 0.02
    attention_ema_alpha: float = 0.1
    victim_sample_size: int = 48

    @classmethod
    def for_chatbot(cls) -> "KVCachePolicyConfig":
        """Short sequences, low latency."""
        return cls(recent_window=256, victim_sample_size=32)

    @classmethod
    def for_long_context(cls) -> "KVCachePolicyConfig":
        """Long sequences (32K+), protect entities aggressively."""
        return cls(
            sink_tokens=8,
            recent_window=1024,
            entity_attention_threshold=0.01,
            victim_sample_size=64,
        )

    @classmethod
    def for_batch(cls) -> "KVCachePolicyConfig":
        """High-throughput batch inference."""
        return cls(recent_window=512, victim_sample_size=64)
