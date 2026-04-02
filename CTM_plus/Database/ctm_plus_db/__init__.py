"""
CTM+ Adaptive Eviction Policy.

A sampled multi-signal eviction policy for research and benchmarking.
This is NOT a database buffer pool or storage system — it only makes
eviction decisions based on page access metadata.

Usage:
    from ctm_plus_db import AdaptiveEvictionPolicy, EvictionConfig

    policy = AdaptiveEvictionPolicy(capacity=10000)
    is_hit, prefetch = policy.access(page_id=42)
    victim = policy.select_victim()
"""

from .buffer_pool import AdaptiveEvictionPolicy, PageType
from .config import EvictionConfig

__version__ = "0.2.0"
__all__ = [
    "AdaptiveEvictionPolicy",
    "EvictionConfig",
    "PageType",
]
