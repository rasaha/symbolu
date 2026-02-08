"""
CTM+ Integration for vLLM.

Provides intelligent KV cache block eviction for PagedAttention,
optimizing memory usage for LLM inference workloads.

Usage:
    from ctm_plus_vllm import CTMBlockSpaceManager, CTMEvictionPolicy

    # Replace vLLM's default block manager
    block_manager = CTMBlockSpaceManager(
        block_size=16,
        num_gpu_blocks=1000,
        num_cpu_blocks=10000,
    )

Benchmarking:
    python -m ctm_plus_vllm.benchmark_cli compare --seq-len 4096 --cache-ratio 0.5
"""

from .evictor import CTMEvictionPolicy
from .block_manager import CTMBlockSpaceManager
from .config import CTMvLLMConfig
from .kv_cache_simulator import (
    KVCacheSimulator,
    CTMKVConfig,
    EvictionPolicy,
    WorkloadGenerator,
    AttentionPatternGenerator,
    run_benchmark,
    quality_preservation_test,
)

__version__ = "0.1.0"
__all__ = [
    "CTMEvictionPolicy",
    "CTMBlockSpaceManager",
    "CTMvLLMConfig",
    "KVCacheSimulator",
    "CTMKVConfig",
    "EvictionPolicy",
    "WorkloadGenerator",
    "AttentionPatternGenerator",
    "run_benchmark",
    "quality_preservation_test",
]
