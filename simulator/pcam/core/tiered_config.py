"""
Configuration for Tiered PCAM with TurboQuant compression and CXL shared pool.

Extends the base PCAMConfig with:
  - CXL 3.0 overflow tier: TQ-compressed edges in CXL-attached DRAM
  - Multi-GPU shared edge pool: cross-host edge sharing via CXL coherence
  - Tier promotion/demotion policies based on access patterns
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .config import PCAMConfig, InterconnectType


class TierType(Enum):
    """PCAM storage tiers."""
    BRAM = "bram"          # On-chip BRAM: fast, limited (1M entries)
    CXL_POOL = "cxl_pool"  # CXL-attached DRAM: TQ-compressed, larger
    EVICTED = "evicted"     # No longer stored


@dataclass
class TurboQuantEdgeConfig:
    """TurboQuant configuration adapted for PCAM edge compression.

    PCAM edges are scalar scores (not full KV vectors), so we compress
    the per-block metadata (score, access_count, timestamps, query sources)
    into a compact representation.  TQ's compression ratio applies to the
    aggregate edge state per block.
    """
    # Compression ratio for edge metadata in CXL tier
    # Based on TQ-3bit: ~5.3x for KV vectors; for edge metadata we achieve
    # ~4x by quantizing scores to Q4.4 and packing access counts.
    compression_ratio: float = 4.0

    # Minimum score to admit to CXL tier (below this, evict entirely)
    min_score_for_cxl: float = 0.001

    # Score precision in CXL tier (bits for Q-format fixed point)
    score_bits: int = 8  # Q4.4: 4 integer + 4 fractional bits

    # Whether to store attention edges in CXL (expensive but improves recall)
    store_edges_in_cxl: bool = False

    # Max edges per block in CXL tier (limit to save space)
    max_edges_per_block_cxl: int = 16


@dataclass
class CXLPoolConfig:
    """CXL 3.0 shared memory pool configuration for PCAM edges."""
    enabled: bool = True

    # Pool capacity as multiple of BRAM capacity
    # With TQ compression, effective capacity = pool_capacity_multiplier * compression_ratio
    pool_capacity_multiplier: float = 1.5  # 1.5M raw slots → ~6M effective with TQ

    # Latency model (nanoseconds)
    access_latency_ns: float = 250.0   # CXL pool read/write
    promotion_latency_ns: float = 150.0  # CXL → BRAM promotion (decompress + write)
    demotion_latency_ns: float = 200.0   # BRAM → CXL demotion (compress + write)

    # Multi-GPU sharing
    num_hosts: int = 1          # Number of GPUs sharing the pool
    max_sharers_per_entry: int = 4  # CXL.cache sharer limit

    # Per-host quota management
    per_host_min_share: float = 0.1   # Minimum guaranteed pool share per host [0, 1]
    per_host_max_share: float = 0.8   # Maximum pool share any single host can use

    # Coherence costs
    invalidation_latency_ns: float = 500.0
    invalidation_batch_size: int = 8

    # Eviction scoring for shared entries
    shared_entry_penalty: float = 0.2   # Penalty multiplier for evicting shared entries
    remote_entry_boost: float = 0.1     # Boost for keeping frequently-shared entries

    # Dynamic capacity
    expansion_threshold: float = 0.85   # Utilization to trigger expansion
    contraction_threshold: float = 0.30  # Utilization to trigger contraction
    rebalance_interval: int = 500       # Accesses between rebalance checks
    capacity_step: int = 100            # Entries added/removed per expansion/contraction

    # Cross-host edge discovery
    discovery_enabled: bool = True       # Allow GPUs to discover edges from other GPUs
    discovery_min_score: float = 0.05    # Minimum score for cross-host edge discovery
    discovery_boost: float = 0.15        # Score boost for cross-host validated edges


@dataclass
class TierPolicy:
    """Policy for promotion and demotion between BRAM and CXL tiers."""
    # Demotion: BRAM → CXL (triggered when BRAM is full)
    # Demote blocks with lowest score that haven't been accessed recently
    demotion_score_percentile: float = 0.25  # Bottom 25% by score
    demotion_min_idle_steps: int = 50        # Must be idle for N steps

    # Promotion: CXL → BRAM (triggered on CXL hit)
    # Promote if block is accessed and has sufficient score
    promotion_min_access_count: int = 2  # Must be accessed N times in CXL
    promotion_min_score: float = 0.01    # Minimum score to promote

    # Eviction: CXL → gone (when CXL pool is full)
    eviction_min_idle_steps: int = 200   # Must be idle for N steps in CXL
    eviction_max_score: float = 0.0005   # Below this score, evict from CXL


@dataclass
class TieredPCAMConfig:
    """Complete configuration for Tiered PCAM with TQ + CXL."""
    # Base PCAM configuration (BRAM tier)
    base: PCAMConfig = field(default_factory=PCAMConfig)

    # TurboQuant edge compression
    tq: TurboQuantEdgeConfig = field(default_factory=TurboQuantEdgeConfig)

    # CXL shared pool
    cxl: CXLPoolConfig = field(default_factory=CXLPoolConfig)

    # Tier management policy
    policy: TierPolicy = field(default_factory=TierPolicy)

    @property
    def bram_capacity(self) -> int:
        """Maximum entries in BRAM tier."""
        return self.base.max_entries

    @property
    def cxl_raw_capacity(self) -> int:
        """Raw CXL pool capacity (before compression)."""
        return int(self.base.max_entries * self.cxl.pool_capacity_multiplier)

    @property
    def cxl_effective_capacity(self) -> int:
        """Effective CXL capacity with TQ compression."""
        return int(self.cxl_raw_capacity * self.tq.compression_ratio)

    @property
    def total_effective_capacity(self) -> int:
        """Total capacity across all tiers."""
        return self.bram_capacity + self.cxl_effective_capacity

    def summary(self) -> str:
        """Human-readable configuration summary."""
        return (
            f"Tiered PCAM Configuration:\n"
            f"  BRAM tier:  {self.bram_capacity:,} entries (on-chip, <100ns)\n"
            f"  CXL tier:   {self.cxl_effective_capacity:,} effective entries "
            f"({self.tq.compression_ratio:.1f}x TQ compression, ~{self.cxl.access_latency_ns:.0f}ns)\n"
            f"  Total:      {self.total_effective_capacity:,} entries "
            f"({self.total_effective_capacity / self.bram_capacity:.1f}x base capacity)\n"
            f"  Hosts:      {self.cxl.num_hosts} GPU(s)\n"
            f"  CXL pool:   {'enabled' if self.cxl.enabled else 'disabled'}\n"
        )

    @classmethod
    def single_gpu(cls) -> "TieredPCAMConfig":
        """Default config for single-GPU inference."""
        return cls(
            cxl=CXLPoolConfig(num_hosts=1),
        )

    @classmethod
    def multi_gpu(cls, num_gpus: int = 4) -> "TieredPCAMConfig":
        """Config for multi-GPU inference with shared edge pool."""
        return cls(
            cxl=CXLPoolConfig(
                num_hosts=num_gpus,
                pool_capacity_multiplier=2.0,  # Larger pool for sharing
            ),
        )

    @classmethod
    def long_context(cls) -> "TieredPCAMConfig":
        """Config optimized for long-context workloads (128K+ tokens)."""
        return cls(
            tq=TurboQuantEdgeConfig(
                compression_ratio=5.3,  # Full TQ-3bit ratio
                store_edges_in_cxl=True,  # Store edges for better recall
                max_edges_per_block_cxl=32,
            ),
            cxl=CXLPoolConfig(
                pool_capacity_multiplier=3.0,  # 3x BRAM → ~16M effective
            ),
            policy=TierPolicy(
                demotion_score_percentile=0.15,  # More aggressive demotion
                promotion_min_access_count=1,    # Faster promotion
            ),
        )
