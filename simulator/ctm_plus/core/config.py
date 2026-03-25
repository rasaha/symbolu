"""
Configuration dataclasses for CTM+ simulator.

All configuration is done via immutable dataclasses with sensible defaults
derived from the CTM+ specification.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import IntEnum


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
class AdmissionConfig:
    """
    Admission control configuration (TinyLFU + S3-FIFO inspired).

    Separates admission policy from eviction policy. New pages must "beat"
    the eviction candidate's frequency to be admitted, preventing one-hit-
    wonders from polluting the cache.

    Components:
    - FrequencySketch: Count-Min Sketch for compact frequency tracking
    - S3-FIFO: Small/Main/Ghost three-queue admission structure
    """

    enabled: bool = True
    # FrequencySketch (W-TinyLFU)
    sketch_capacity_multiplier: int = 10  # Track 10x cache size in sketch
    sketch_depth: int = 4  # Number of hash functions
    # S3-FIFO
    small_queue_ratio: float = 0.10  # 10% of tier0 as probation queue
    ghost_queue_ratio: float = 1.0  # Ghost queue = 100% of tier0 size
    # Admission gate: new page must beat victim's frequency to be admitted
    frequency_gate: bool = True  # Require new page freq >= victim freq


class TenantPriority(IntEnum):
    """QoS priority classes for multi-tenant isolation (CacheLib/DAMON-inspired)."""

    BACKGROUND = 0   # Lowest: batch jobs, analytics scans
    LOW = 1           # Below normal: non-critical services
    NORMAL = 2        # Default priority
    HIGH = 3          # Elevated: latency-sensitive services
    CRITICAL = 4      # Highest: cannot be evicted unless pinned-page limit reached


@dataclass(frozen=True)
class TenantConfig:
    """
    Per-tenant QoS configuration.

    Each tenant gets a guaranteed minimum share of tier0 and a hard
    maximum cap. Eviction priority is determined by the priority class:
    lower-priority tenants are evicted first when under memory pressure.
    """

    tenant_id: str = "default"
    priority: TenantPriority = TenantPriority.NORMAL

    # Tier0 share bounds as fractions of total tier0 capacity [0.0, 1.0]
    min_tier0_share: float = 0.0    # Guaranteed minimum (0 = no guarantee)
    max_tier0_share: float = 1.0    # Hard cap (1.0 = no limit)

    # Weight multiplier for victim scoring: higher = harder to evict
    # Applied as: score *= priority_weight. CRITICAL gets 4x protection.
    priority_weight: float = 1.0

    def __post_init__(self) -> None:
        if not (0.0 <= self.min_tier0_share <= self.max_tier0_share <= 1.0):
            raise ValueError(
                f"Invalid share bounds: min={self.min_tier0_share}, max={self.max_tier0_share}"
            )


@dataclass(frozen=True)
class MultiTenancyConfig:
    """
    Multi-tenancy and QoS isolation configuration.

    When enabled, the controller enforces per-tenant tier0 quotas and
    uses priority-weighted victim selection to prevent noisy neighbors.
    """

    enabled: bool = False

    # Default tenant for pages without explicit tenant assignment
    default_tenant_id: str = "default"

    # Eviction pressure: when a tenant exceeds its max_tier0_share,
    # how aggressively to prefer evicting its pages. [0, 1]
    over_quota_penalty: float = 0.3

    # Under-quota protection: when a tenant is below min_tier0_share,
    # how much to protect its pages from eviction. [0, 1]
    under_quota_boost: float = 0.3

    # Priority-based victim selection weight. Higher = priority matters more.
    priority_weight_scale: float = 0.2

    # Per-tenant configs keyed by tenant_id (not frozen-safe as dict, use classmethod)
    # Tenant configs are registered at runtime via TenantManager.register_tenant()


@dataclass(frozen=True)
class NUMAConfig:
    """
    NUMA-aware memory placement configuration (Linux DAMON / CXL-inspired).

    Models a multi-socket system where memory access latency depends on the
    physical distance between the requesting CPU and the memory node.

    Topology:
        num_nodes NUMA nodes, each with a slice of tier0 and tier1 capacity.
        Access latency = base_latency + remote_penalty * distance(src, dst).

    Design:
        - Distance matrix: NxN symmetric matrix of inter-node distances [0.0, 1.0]
          where 0.0 = local and 1.0 = maximum remote distance.
        - Each page tracks its preferred_node (the NUMA node of its most
          frequent accessor). Promotions target the requester's node.
        - Victim selection penalizes pages on the "wrong" node (remote to
          their preferred accessor) → they get evicted first.
        - Migration: When a page is accessed from a different node than its
          current placement, the controller may migrate it closer.
    """

    enabled: bool = False

    # Topology
    num_nodes: int = 2  # Number of NUMA nodes (sockets)

    # Distance matrix as flat list (row-major): distances[i * num_nodes + j]
    # If empty, auto-generated as uniform remote distance.
    # Values in [0.0, 1.0] where 0.0 = local, 1.0 = max remote.
    distances: Tuple[float, ...] = ()

    # Latency model
    remote_penalty_ns: int = 150  # Extra latency per unit of distance (ns)
    # e.g., local DRAM = 100ns, 1-hop remote = 100 + 150*0.5 = 175ns

    # Placement policy
    local_preference_weight: float = 0.15  # Score boost for local pages in victim selection
    remote_eviction_penalty: float = 0.15  # Score penalty for remote pages (easier to evict)
    migration_threshold: float = 0.6  # Affinity score threshold to trigger migration
    migration_cooldown: int = 50  # Min accesses between migrations for same page

    def get_distance(self, src_node: int, dst_node: int) -> float:
        """Get distance between two NUMA nodes."""
        if src_node == dst_node:
            return 0.0
        if self.distances:
            idx = src_node * self.num_nodes + dst_node
            if idx < len(self.distances):
                return self.distances[idx]
        # Default: uniform remote distance of 1.0
        return 1.0

    def get_distance_matrix(self) -> List[List[float]]:
        """Get full NxN distance matrix."""
        n = self.num_nodes
        if self.distances and len(self.distances) == n * n:
            return [[self.distances[i * n + j] for j in range(n)] for i in range(n)]
        # Auto-generate: 0 on diagonal, 1.0 everywhere else
        return [[0.0 if i == j else 1.0 for j in range(n)] for i in range(n)]

    def __post_init__(self) -> None:
        if self.num_nodes < 1:
            raise ValueError("num_nodes must be >= 1")
        if self.distances:
            expected = self.num_nodes * self.num_nodes
            if len(self.distances) != expected:
                raise ValueError(
                    f"distances must have {expected} entries for {self.num_nodes} nodes, "
                    f"got {len(self.distances)}"
                )


@dataclass(frozen=True)
class CostTieringConfig:
    """
    Cost-aware tiering configuration (CacheLib / CXL CMM-H inspired).

    Models the economic cost of placing pages across memory tiers so the
    controller can optimize $/GB-served, not just hit rate or latency.

    Key insight: DRAM is ~10x more expensive per GB than NAND. A page that
    is only accessed once per hour doesn't justify tier0 residency. The
    cost-benefit ratio tells us whether promotion is "worth it":

        benefit = expected_hits_in_window * (tier1_latency - tier0_latency)
        cost    = tier0_cost_per_page_per_window + promotion_cost + demotion_cost

    Promotion only proceeds when benefit / cost > min_cost_benefit_ratio.

    Victim selection also factors cost:
    - Write-heavy pages incur wear on NAND (tier1) → keep in DRAM if cheap
    - Pages with low expected reuse waste expensive DRAM → evict to NAND
    """

    enabled: bool = False

    # Per-tier cost in abstract units per page per epoch.
    # Relative ratio matters more than absolute values.
    # Default: DRAM is 10x costlier than NAND per GB.
    tier0_cost_per_page: float = 10.0   # DRAM: expensive, fast
    tier1_cost_per_page: float = 1.0    # NAND: cheap, slow

    # One-time movement costs (amortized over residency window)
    promotion_cost: float = 2.0   # Cost of moving page tier1 → tier0
    demotion_cost: float = 3.0    # Cost of moving page tier0 → tier1 (write to NAND)

    # Write amplification: extra cost for write-heavy pages in tier1.
    # NAND has limited write endurance, so write-hot pages are cheaper to
    # keep in DRAM than to repeatedly flush to NAND.
    write_amp_weight: float = 0.1  # Per-write penalty in tier1

    # Promotion gating: minimum cost-benefit ratio to justify promotion.
    # < 1.0 means promote even if slightly unprofitable (favor hit rate).
    # > 1.0 means only promote high-value pages (favor cost efficiency).
    min_cost_benefit_ratio: float = 0.5

    # Victim scoring: weight of cost signal in eviction decisions.
    # Positive = prefer evicting low-value pages (low benefit/cost ratio).
    cost_eviction_weight: float = 0.15

    # Expected reuse horizon: how many future accesses to estimate benefit over.
    # Uses access_count / time_in_tier as arrival rate, projected forward.
    benefit_horizon_accesses: int = 100

    def __post_init__(self) -> None:
        if self.tier0_cost_per_page < 0 or self.tier1_cost_per_page < 0:
            raise ValueError("Tier costs must be non-negative")
        if self.min_cost_benefit_ratio < 0:
            raise ValueError("min_cost_benefit_ratio must be non-negative")
        if self.benefit_horizon_accesses < 1:
            raise ValueError("benefit_horizon_accesses must be >= 1")


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

    # === Gap feature configs ===
    admission: AdmissionConfig = field(default_factory=AdmissionConfig)
    irr: IRRConfig = field(default_factory=IRRConfig)
    size_aware: SizeAwareConfig = field(default_factory=SizeAwareConfig)
    refault: RefaultConfig = field(default_factory=RefaultConfig)
    adaptive_weights: AdaptiveWeightConfig = field(default_factory=AdaptiveWeightConfig)
    lazy_promotion: LazyPromotionConfig = field(default_factory=LazyPromotionConfig)
    external_hints: ExternalHintConfig = field(default_factory=ExternalHintConfig)
    multi_tenancy: MultiTenancyConfig = field(default_factory=MultiTenancyConfig)
    numa: NUMAConfig = field(default_factory=NUMAConfig)
    cost_tiering: CostTieringConfig = field(default_factory=CostTieringConfig)

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
