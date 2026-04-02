"""
Configuration for the adaptive eviction policy.

Scoring weights control victim selection. They should sum to 1.0.
Signals: recency, frequency, correlation, page_type.
"""

from dataclasses import dataclass


@dataclass
class EvictionConfig:
    """
    Configuration for AdaptiveEvictionPolicy.

    Weights control how the 4 scoring signals contribute to eviction decisions.
    Higher weight = more influence on which pages are kept.
    """

    # Victim selection
    victim_sample_size: int = 48
    enable_smart_victim: bool = True

    # Shadow tier (ghost cache) size
    shadow_size: int = 2048

    # Access pattern tracking
    neighbor_window: int = 32

    # Page type modifiers (added to page_type signal, not standalone weights)
    dirty_page_penalty: float = 0.3
    index_page_bonus: float = 0.2

    # ARC adaptation
    adaptive_p_learning_rate: float = 0.1
    initial_p: float = 0.5

    # Scoring weights (must sum to 1.0)
    weight_recency: float = 0.40
    weight_frequency: float = 0.35
    weight_correlation: float = 0.15
    weight_page_type: float = 0.10

    # Prefetching
    prefetch_enabled: bool = True
    prefetch_distance: int = 8
    sequential_threshold: int = 4

    # Write-back hint
    lazy_write_threshold: float = 0.8

    @classmethod
    def for_random_access(cls) -> "EvictionConfig":
        """Tuned for random access patterns (e.g. OLTP-like index lookups)."""
        return cls(
            victim_sample_size=64,
            weight_recency=0.45,
            weight_frequency=0.35,
            weight_correlation=0.10,
            weight_page_type=0.10,
            prefetch_enabled=False,
            dirty_page_penalty=0.4,
        )

    @classmethod
    def for_sequential(cls) -> "EvictionConfig":
        """Tuned for sequential scan patterns (e.g. OLAP-like full scans)."""
        return cls(
            victim_sample_size=32,
            weight_recency=0.30,
            weight_frequency=0.30,
            weight_correlation=0.25,
            weight_page_type=0.15,
            prefetch_enabled=True,
            prefetch_distance=16,
            sequential_threshold=2,
        )

    @classmethod
    def for_mixed(cls) -> "EvictionConfig":
        """Balanced for mixed access patterns."""
        return cls(
            victim_sample_size=48,
            prefetch_enabled=True,
            prefetch_distance=4,
        )
