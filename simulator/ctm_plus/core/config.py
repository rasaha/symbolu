"""
Configuration dataclasses for CTM+ simulator.

All configuration is done via immutable dataclasses with sensible defaults
derived from the CTM+ specification.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class SimulatorConfig:
    """
    Global simulator configuration.

    Attributes:
        tier0_size: Number of pages in fast tier (e.g., DRAM/HBM)
        tier1_size: Number of pages in slow tier (e.g., NAND/DDR)
        page_size_bytes: Size of each page in bytes (default 4KB)
        tier0_latency_ns: Access latency for tier 0 in nanoseconds
        tier1_latency_ns: Access latency for tier 1 in nanoseconds
        promotion_latency_ns: Latency to promote a page
        demotion_latency_ns: Latency to demote a page
    """

    tier0_size: int = 1000  # Pages in fast tier
    tier1_size: int = 100000  # Pages in slow tier
    page_size_bytes: int = 4096  # 4KB pages
    tier0_latency_ns: int = 100  # ~DRAM latency
    tier1_latency_ns: int = 10000  # ~NAND read latency
    promotion_latency_ns: int = 50000  # Cost to promote
    demotion_latency_ns: int = 100000  # Cost to demote (write to NAND)

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.tier0_size <= 0:
            raise ValueError("tier0_size must be positive")
        if self.tier1_size <= 0:
            raise ValueError("tier1_size must be positive")
        if self.tier0_size >= self.tier1_size:
            raise ValueError("tier0_size should be smaller than tier1_size")


@dataclass(frozen=True)
class PhaseIntegratorConfig:
    """
    Phase Integrator configuration for pattern learning.

    Streaming accumulator:
        M_t = γ·M_{t-1} + (1-γ)·(k_t ⊙ v_t)
    """

    embedding_dim: int = 64  # Dimension D of event embeddings
    decay_gamma: float = 0.95  # EMA decay factor γ
    phase_scale: float = 3.14159  # π for phase bounding


@dataclass(frozen=True)
class CoherenceConfig:
    """
    Coherence computation configuration.

    Fast path (per-access):
        C_fast = α·c_i + β·(1-δ_i) + γ·cos(φ_i - φ̄)

    Slow path (background):
        C_{i,j} = (1/W) Σ cos(φ_i - φ_j)
    """

    # Fast path weights
    fast_alpha: float = 0.4  # Coherence weight
    fast_beta: float = 0.3  # (1-drift) weight
    fast_gamma: float = 0.3  # Phase alignment weight

    # Slow path config
    window_size: int = 16  # W: temporal window for correlation
    neighborhood_size: int = 8  # |N(i)|: neighbors for pairwise coherence
    eta: float = 0.3  # Scaling factor η for sigmoid

    # Update intervals
    slow_update_interval: int = 1000  # Update slow path every N accesses


@dataclass(frozen=True)
class IRRConfig:
    """
    Inter-Reference Recency (IRR) tracking configuration (LIRS-inspired).

    IRR measures the number of unique pages accessed between two consecutive
    accesses to the same page. Pages with high IRR are cold despite recent access.
    """

    enabled: bool = True
    irr_weight: float = 0.15  # Weight in victim scoring
    irr_ema_alpha: float = 0.3  # EMA smoothing for IRR updates
    max_irr: float = 1000.0  # Cap IRR to prevent unbounded values


@dataclass(frozen=True)
class SizeAwareConfig:
    """
    Size-aware eviction configuration (LHD-inspired).

    Uses hit_density = expected_hits / size for variable-size objects.
    """

    enabled: bool = True
    default_page_size: int = 4096  # Default page size in bytes
    size_weight: float = 0.1  # How much size affects victim score


@dataclass(frozen=True)
class RefaultConfig:
    """
    Refault/pressure-based control configuration (TMO/MGLRU-inspired).

    Tracks evicted pages that are immediately re-fetched (refaults)
    and uses a PID-like controller to adjust eviction aggressiveness.
    """

    enabled: bool = True
    refault_window: int = 200  # Sliding window for refault tracking
    target_refault_rate: float = 0.05  # Target refault rate (PID setpoint)
    kp: float = 0.5  # PID proportional gain
    ki: float = 0.1  # PID integral gain
    kd: float = 0.05  # PID derivative gain
    promotion_boost_on_refault: float = 0.2  # Extra promotion score for refaulted pages


@dataclass(frozen=True)
class AdaptiveWeightConfig:
    """
    Online weight learning configuration (CACHEUS/LeCaR-inspired).

    Uses Hedge (multiplicative weights) algorithm to learn victim scoring
    weights from hit/miss outcomes rather than using fixed coefficients.
    """

    enabled: bool = True
    learning_rate: float = 0.1  # Hedge algorithm learning rate (η)
    min_weight: float = 0.02  # Floor to prevent weight collapse
    update_interval: int = 100  # Update weights every N evictions
    num_experts: int = 5  # Number of scoring dimensions


@dataclass(frozen=True)
class LazyPromotionConfig:
    """
    Lazy promotion configuration (SIEVE-inspired).

    Defers metadata updates to eviction time. On access, only set a visited bit.
    At eviction scan, skip visited pages (clear their bit) and evict unvisited ones.
    """

    enabled: bool = True
    sieve_scan_limit: int = 8  # Max pages to scan before falling back to scoring


@dataclass(frozen=True)
class ExternalHintConfig:
    """
    External hint API configuration (CXL CMM-H-inspired).

    Allows applications to signal page hotness/priority to the controller.
    """

    enabled: bool = True
    hot_boost: float = 0.3  # Score boost for HOT-hinted pages
    cold_penalty: float = 0.3  # Score penalty for COLD-hinted pages
    pin_protection: bool = True  # PINNED pages cannot be evicted
    willneed_prefetch: bool = True  # WILLNEED triggers prefetch
    dontneed_evict_priority: float = 0.5  # Priority to evict DONTNEED pages


@dataclass(frozen=True)
class CTMPlusConfig:
    """
    Complete CTM+ configuration combining all sub-configs.

    This is the main configuration object passed to CTMPlusController.
    """

    phase: PhaseIntegratorConfig = field(default_factory=PhaseIntegratorConfig)
    coherence: CoherenceConfig = field(default_factory=CoherenceConfig)

    # Promotion/demotion specific
    promotion_cooldown: int = 10
    demotion_cooldown: int = 10
    max_promotions_per_epoch: int = 10000
    max_demotions_per_epoch: int = 10000
    epoch_size: int = 1000

    # Victim selection thresholds
    victim_sample_size: int = 48
    promotion_threshold: float = 0.3
    loop_pin_reuse_threshold: float = 0.4
    loop_pin_neighbor_threshold: float = 0.3

    # Ablation switches
    enable_smart_victim: bool = True

    # === New gap feature configs ===
    irr: IRRConfig = field(default_factory=IRRConfig)
    size_aware: SizeAwareConfig = field(default_factory=SizeAwareConfig)
    refault: RefaultConfig = field(default_factory=RefaultConfig)
    adaptive_weights: AdaptiveWeightConfig = field(default_factory=AdaptiveWeightConfig)
    lazy_promotion: LazyPromotionConfig = field(default_factory=LazyPromotionConfig)
    external_hints: ExternalHintConfig = field(default_factory=ExternalHintConfig)

    @classmethod
    def default(cls) -> "CTMPlusConfig":
        """Return default configuration."""
        return cls()

    @classmethod
    def aggressive(cls) -> "CTMPlusConfig":
        """More aggressive promotion, for high-locality workloads."""
        return cls(
            phase=PhaseIntegratorConfig(decay_gamma=0.9),
        )

    @classmethod
    def conservative(cls) -> "CTMPlusConfig":
        """Conservative promotion, for random workloads."""
        return cls(
            phase=PhaseIntegratorConfig(decay_gamma=0.99),
        )

    @classmethod
    def minimal_overhead(cls) -> "CTMPlusConfig":
        """Minimal per-access overhead (SIEVE-like behavior)."""
        return cls(
            lazy_promotion=LazyPromotionConfig(enabled=True, sieve_scan_limit=16),
            irr=IRRConfig(enabled=False),
            adaptive_weights=AdaptiveWeightConfig(enabled=False),
        )
