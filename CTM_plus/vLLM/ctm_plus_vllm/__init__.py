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
"""

from .evictor import CTMEvictionPolicy
from .block_manager import CTMBlockSpaceManager
from .config import CTMvLLMConfig

__version__ = "0.1.0"
__all__ = [
    "CTMEvictionPolicy",
    "CTMBlockSpaceManager",
    "CTMvLLMConfig",
]
