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
class BCVFConfig:
    """
    BCVF (Bidirectional Coherence Verification Framework) parameters.

    The BCVF Lagrangian:
        L(i,A) = λ_f(1-s_f)² + λ_b(1-s_b)² + λ_c(s_f-s_b)²

    Action weight:
        w(i,A) = e^{-β·L(i,A)}
    """

    lambda_f: float = 0.40  # Forward penalty weight
    lambda_b: float = 0.35  # Backward penalty weight
    lambda_c: float = 0.25  # Consistency penalty weight
    beta: float = 2.0  # Temperature parameter
    threshold: float = 0.4  # Decision threshold τ (was 0.6, too conservative)

    # Forward score weights (α)
    alpha_latency: float = 0.6  # Weight for latency improvement
    alpha_miss: float = 0.4  # Weight for miss reduction

    # Backward score weights (β)
    beta_heat: float = 0.25  # Weight for (1 - heat)
    beta_coherence: float = 0.30  # Weight for coherence
    beta_uncertainty: float = 0.20  # Weight for (1 - uncertainty)
    beta_drift: float = 0.25  # Weight for (1 - drift)


@dataclass(frozen=True)
class SCCConfig:
    """
    SCC (Semantic Coherence Controller) parameters.

    Per-tier coherence:
        C_tier = α·c̄ + β·R̄ + γ·(1-ū) + δ·P̄
    """

    alpha: float = 0.30  # Coherence weight
    beta: float = 0.25  # Reuse/hit-rate weight
    gamma: float = 0.25  # Certainty weight (1 - entropy)
    delta: float = 0.20  # Predictability weight
    learning_rate: float = 0.01  # Parameter update rate ρ
    update_interval: int = 10000  # Update every N accesses


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
class CTMPlusConfig:
    """
    Complete CTM+ configuration combining all sub-configs.

    This is the main configuration object passed to CTMPlusController.
    """

    bcvf: BCVFConfig = field(default_factory=BCVFConfig)
    scc: SCCConfig = field(default_factory=SCCConfig)
    phase: PhaseIntegratorConfig = field(default_factory=PhaseIntegratorConfig)
    coherence: CoherenceConfig = field(default_factory=CoherenceConfig)

    # Promotion/demotion specific
    # NOTE: Previous values (100, 50, 100, 100) were too restrictive
    # and handicapped CTM+ vs LRU/ARC which have no such limits
    promotion_cooldown: int = 10  # Min accesses before re-promoting demoted page
    demotion_cooldown: int = 10  # Min accesses before re-demoting promoted page
    max_promotions_per_epoch: int = 10000  # Effectively unlimited
    max_demotions_per_epoch: int = 10000  # Effectively unlimited
    epoch_size: int = 1000  # Accesses per epoch

    # Ablation switches for experimental validation
    enable_smart_victim: bool = True  # Use CTM+ victim selection vs LRU fallback
    enable_bcvf_gate: bool = True  # Use BCVF promotion gate vs always promote
    # NOTE: Admission controller was removed - it hurt temporal workloads

    @classmethod
    def default(cls) -> "CTMPlusConfig":
        """Return default configuration."""
        return cls()

    @classmethod
    def aggressive(cls) -> "CTMPlusConfig":
        """More aggressive promotion, for high-locality workloads."""
        return cls(
            bcvf=BCVFConfig(threshold=0.5, beta=3.0),
            phase=PhaseIntegratorConfig(decay_gamma=0.9),
        )

    @classmethod
    def conservative(cls) -> "CTMPlusConfig":
        """Conservative promotion, for random workloads."""
        return cls(
            bcvf=BCVFConfig(threshold=0.7, beta=1.5),
            phase=PhaseIntegratorConfig(decay_gamma=0.99),
        )
