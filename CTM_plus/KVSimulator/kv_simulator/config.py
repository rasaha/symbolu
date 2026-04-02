"""
Configuration for KV cache eviction simulation.

Parameters control the simulated LLM inference workload and
attention-aware eviction policy behavior.
"""

from dataclasses import dataclass


@dataclass
class SimulationConfig:
    """
    Parameters for KVCacheSimulator.

    Structural:
        block_size: Tokens per KV block.
        sink_tokens: Number of initial positions treated as attention sinks.
        recent_window: Number of recent positions protected from eviction.

    Policy (CTM+ only):
        victim_sample_size: Blocks sampled for victim selection.
        entity_attention_threshold: Cumulative attention above which
            a block is classified as ENTITY (protected).
    """

    block_size: int = 16
    sink_tokens: int = 4
    recent_window: int = 128
    victim_sample_size: int = 48
    entity_attention_threshold: float = 0.02

    @classmethod
    def for_short_context(cls) -> "SimulationConfig":
        """Short sequences (≤2K tokens), e.g. chatbot turns."""
        return cls(recent_window=64, victim_sample_size=32)

    @classmethod
    def for_long_context(cls) -> "SimulationConfig":
        """Long sequences (8K–32K+), entity-heavy documents."""
        return cls(
            sink_tokens=8,
            recent_window=512,
            victim_sample_size=64,
            entity_attention_threshold=0.01,
        )

    @classmethod
    def for_batch(cls) -> "SimulationConfig":
        """High-throughput batch inference with many concurrent sequences."""
        return cls(recent_window=256, victim_sample_size=64)
