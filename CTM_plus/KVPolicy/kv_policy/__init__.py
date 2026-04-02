"""
CTM+ KV Cache Eviction Policy.

A scoring-only eviction policy for LLM KV cache blocks.
This module does NOT manage memory, I/O, or block allocation — it only
decides which blocks to evict based on attention, position, frequency,
recency, and sequence priority signals.

Integration point: vLLM's Evictor abstract base class.

Usage:
    from kv_policy import KVCachePolicy

    policy = KVCachePolicy(max_blocks=2048)
    policy.register_sequence(seq_id=1)
    policy.on_token_access(token_id=0, position=0, sequence_id=1, block_id=0, attention_weight=0.1)
    victims = policy.select_victims(count=4)
"""

from .attention_evictor import (
    KVCachePolicy,
    InferencePhase,
    PositionClass,
    compute_adaptive_threshold,
    classify_block_importance,
)
from .config import KVCachePolicyConfig
from .vllm_adapter import CTMBlockSpaceManager, CTMvLLMConfig

__version__ = "0.3.0"
__all__ = [
    "KVCachePolicy",
    "KVCachePolicyConfig",
    "InferencePhase",
    "PositionClass",
    "compute_adaptive_threshold",
    "classify_block_importance",
    "CTMBlockSpaceManager",
    "CTMvLLMConfig",
]
