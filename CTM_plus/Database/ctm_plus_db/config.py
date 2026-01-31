"""
Configuration for CTM+ Database integration.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CTMDBConfig:
    """
    Configuration for CTM+ buffer pool management.

    Attributes:
        victim_sample_size: Number of pages to sample for eviction decisions.
        promotion_threshold: Minimum score for page to stay in buffer.
        enable_smart_victim: Use CTM+ scoring vs simple LRU.
        shadow_size: Size of ghost cache for tracking evicted pages.
        neighbor_window: Window size for access pattern tracking.
        dirty_page_penalty: Extra weight for dirty pages (avoid eviction).
        index_page_bonus: Extra weight for index pages (keep in buffer).
        adaptive_p_learning_rate: Learning rate for ARC-style adaptation.
        prefetch_enabled: Enable sequential prefetching.
        prefetch_distance: Number of pages to prefetch ahead.
    """

    # Victim selection
    victim_sample_size: int = 48
    promotion_threshold: float = 0.3
    enable_smart_victim: bool = True

    # Shadow tiers
    shadow_size: int = 2048

    # Access tracking
    neighbor_window: int = 32

    # Page type weights
    dirty_page_penalty: float = 0.3  # Dirty pages harder to evict
    index_page_bonus: float = 0.2  # Index pages protected
    heap_page_weight: float = 0.0  # Normal data pages

    # Adaptive p
    adaptive_p_learning_rate: float = 0.1
    initial_p: float = 0.5

    # Scoring weights
    weight_recency: float = 0.35
    weight_frequency: float = 0.30
    weight_reuse: float = 0.15
    weight_correlation: float = 0.10
    weight_page_type: float = 0.10

    # Prefetching
    prefetch_enabled: bool = True
    prefetch_distance: int = 8
    sequential_threshold: int = 4  # Min sequential accesses to trigger prefetch

    # Write-back
    lazy_write_threshold: float = 0.8  # Start flushing when buffer > 80% dirty

    @classmethod
    def for_oltp(cls) -> "CTMDBConfig":
        """Optimized for OLTP workloads (random access, many small txns)."""
        return cls(
            victim_sample_size=64,
            promotion_threshold=0.25,
            weight_recency=0.40,
            weight_frequency=0.30,
            weight_reuse=0.15,
            weight_correlation=0.10,
            weight_page_type=0.05,
            prefetch_enabled=False,  # Random access, prefetch not helpful
            dirty_page_penalty=0.4,  # Protect dirty pages more
        )

    @classmethod
    def for_olap(cls) -> "CTMDBConfig":
        """Optimized for OLAP workloads (sequential scans, large queries)."""
        return cls(
            victim_sample_size=32,
            promotion_threshold=0.35,
            weight_recency=0.30,
            weight_frequency=0.25,
            weight_reuse=0.20,
            weight_correlation=0.15,
            weight_page_type=0.10,
            prefetch_enabled=True,
            prefetch_distance=16,
            sequential_threshold=2,
        )

    @classmethod
    def for_mixed(cls) -> "CTMDBConfig":
        """Balanced for mixed OLTP/OLAP workloads."""
        return cls(
            victim_sample_size=48,
            promotion_threshold=0.30,
            prefetch_enabled=True,
            prefetch_distance=4,
        )

    @classmethod
    def for_redis(cls) -> "CTMDBConfig":
        """Optimized for Redis-style key-value caching."""
        return cls(
            victim_sample_size=64,
            promotion_threshold=0.20,
            weight_recency=0.45,
            weight_frequency=0.35,
            weight_reuse=0.10,
            weight_correlation=0.05,
            weight_page_type=0.05,
            prefetch_enabled=False,
            dirty_page_penalty=0.0,  # Redis is often read-heavy
            shadow_size=4096,  # Larger ghost cache for better adaptation
        )

    @classmethod
    def for_postgres(cls) -> "CTMDBConfig":
        """Optimized for PostgreSQL buffer pool."""
        return cls(
            victim_sample_size=48,
            promotion_threshold=0.30,
            index_page_bonus=0.25,
            dirty_page_penalty=0.35,
            prefetch_enabled=True,
            prefetch_distance=8,
            lazy_write_threshold=0.75,
        )

    @classmethod
    def for_mysql(cls) -> "CTMDBConfig":
        """Optimized for MySQL/InnoDB buffer pool."""
        return cls(
            victim_sample_size=48,
            promotion_threshold=0.30,
            index_page_bonus=0.20,
            dirty_page_penalty=0.30,
            prefetch_enabled=True,
            prefetch_distance=8,
            # MySQL uses young/old list, so we adjust weights
            weight_recency=0.40,
            weight_frequency=0.25,
        )
