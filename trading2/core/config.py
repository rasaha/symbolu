"""
Bayesian Trading Configuration

Configures prior distributions, likelihood models, and trading parameters
for the Bayesian state evolution engine.

Unlike EMA (fixed α), Bayesian updates adapt based on:
- Prior uncertainty (variance)
- Likelihood precision (data quality)
- Posterior convergence
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Literal
from enum import Enum
import math


class TradingTier(Enum):
    """Trading frequency tiers with different prior strengths."""
    SCALPER = "scalper"
    DAYTRADER = "daytrader"
    SWING = "swing"
    POSITION = "position"


class RegimeType(Enum):
    """Market regime classifications."""
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    CRISIS = "crisis"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class PriorConfig:
    """
    Prior distribution configuration.

    Uses Beta distribution for bounded [0,1] parameters
    and Normal distribution for unbounded parameters.

    Beta(α, β):
        - Mean = α / (α + β)
        - Variance = αβ / ((α+β)²(α+β+1))
        - Higher α+β = stronger prior (less adaptive)

    Normal(μ, σ²):
        - Mean = μ
        - Variance = σ²
        - Lower σ² = stronger prior
    """
    # Beta prior for signal thresholds (bounded [0,1])
    tau_entry_alpha: float = 6.0    # Prior: ~0.6 entry threshold
    tau_entry_beta: float = 4.0

    tau_exit_alpha: float = 4.0     # Prior: ~0.4 exit threshold
    tau_exit_beta: float = 6.0

    # Beta prior for signal weights
    w_momentum_alpha: float = 4.0   # Prior: ~0.4 momentum weight
    w_momentum_beta: float = 6.0

    w_reversion_alpha: float = 4.0  # Prior: ~0.4 reversion weight
    w_reversion_beta: float = 6.0

    w_elliott_alpha: float = 3.0    # Prior: ~0.3 Elliott wave weight
    w_elliott_beta: float = 7.0

    # Beta prior for position sizing
    position_scalar_alpha: float = 5.0  # Prior: ~0.5 position size
    position_scalar_beta: float = 5.0

    # Normal prior for volatility anchor
    volatility_anchor_mean: float = 0.02  # 2% daily vol
    volatility_anchor_var: float = 0.0001

    @property
    def tau_entry_mean(self) -> float:
        return self.tau_entry_alpha / (self.tau_entry_alpha + self.tau_entry_beta)

    @property
    def tau_exit_mean(self) -> float:
        return self.tau_exit_alpha / (self.tau_exit_alpha + self.tau_exit_beta)

    @property
    def prior_strength(self) -> float:
        """Total concentration parameter (higher = stronger prior)."""
        return self.tau_entry_alpha + self.tau_entry_beta


@dataclass(frozen=True)
class LikelihoodConfig:
    """
    Likelihood model configuration.

    Controls how much weight new observations get relative to prior.

    observation_weight: Effective sample size of each observation
        - Higher = faster adaptation to new data
        - Lower = more conservative updates

    regime_adjustment: Multiply observation weight by regime factor
        - Crisis: 2x weight (adapt faster)
        - Trending: 1.2x weight
        - Ranging: 0.8x weight (more stable)
    """
    # Base observation weight (pseudo-count per tick)
    observation_weight: float = 0.5

    # Regime-specific adjustments
    crisis_multiplier: float = 2.0
    trending_multiplier: float = 1.2
    ranging_multiplier: float = 0.8
    volatile_multiplier: float = 1.5

    # Minimum/maximum effective weights
    min_weight: float = 0.1
    max_weight: float = 5.0

    def get_adjusted_weight(self, regime: RegimeType) -> float:
        """Get observation weight adjusted for regime."""
        multipliers = {
            RegimeType.CRISIS: self.crisis_multiplier,
            RegimeType.TRENDING: self.trending_multiplier,
            RegimeType.RANGING: self.ranging_multiplier,
            RegimeType.VOLATILE: self.volatile_multiplier,
            RegimeType.UNKNOWN: 1.0,
        }
        weight = self.observation_weight * multipliers.get(regime, 1.0)
        return max(self.min_weight, min(self.max_weight, weight))


@dataclass(frozen=True)
class RiskConfig:
    """Risk management configuration."""
    # Drawdown thresholds
    max_drawdown: float = 0.10          # 10% - halt trading
    warning_drawdown: float = 0.05      # 5% - reduce positions
    crisis_drawdown: float = 0.08       # 8% - crisis mode

    # Position limits
    max_position_scalar: float = 1.0
    crisis_position_scalar: float = 0.25

    # Volatility limits
    max_volatility_ratio: float = 3.0   # 3x anchor vol

    # Circuit breaker
    circuit_break_enabled: bool = True
    circuit_break_cooldown: int = 100   # Ticks


@dataclass(frozen=True)
class ElliottWaveConfig:
    """Elliott Wave analysis configuration."""
    # Minimum wave sizes (as % of price)
    min_wave_size: float = 0.005        # 0.5% minimum wave

    # Fibonacci levels for wave relationships
    wave2_retracement: tuple = (0.382, 0.5, 0.618)
    wave3_extension: tuple = (1.618, 2.0, 2.618)
    wave4_retracement: tuple = (0.236, 0.382, 0.5)
    wave5_extension: tuple = (0.618, 1.0, 1.618)

    # Confidence thresholds
    min_pattern_confidence: float = 0.6

    # Lookback periods
    pivot_lookback: int = 20            # Ticks for pivot detection
    wave_lookback: int = 100            # Ticks for wave analysis


# Tier-specific configurations
TIER_CONFIGS: Dict[TradingTier, Dict] = {
    TradingTier.SCALPER: {
        "prior": PriorConfig(
            tau_entry_alpha=3.0, tau_entry_beta=2.0,  # Weaker prior, more adaptive
            tau_exit_alpha=2.0, tau_exit_beta=3.0,
            w_momentum_alpha=3.0, w_momentum_beta=3.0,
            w_reversion_alpha=2.0, w_reversion_beta=4.0,
            w_elliott_alpha=2.0, w_elliott_beta=8.0,  # Less Elliott weight for scalping
        ),
        "likelihood": LikelihoodConfig(observation_weight=1.0),  # Fast adaptation
        "risk": RiskConfig(max_drawdown=0.05, warning_drawdown=0.02),
    },
    TradingTier.DAYTRADER: {
        "prior": PriorConfig(
            tau_entry_alpha=5.0, tau_entry_beta=3.5,
            tau_exit_alpha=3.5, tau_exit_beta=5.0,
            w_momentum_alpha=4.0, w_momentum_beta=5.0,
            w_reversion_alpha=3.0, w_reversion_beta=5.0,
            w_elliott_alpha=3.0, w_elliott_beta=7.0,
        ),
        "likelihood": LikelihoodConfig(observation_weight=0.5),
        "risk": RiskConfig(max_drawdown=0.08, warning_drawdown=0.04),
    },
    TradingTier.SWING: {
        "prior": PriorConfig(
            tau_entry_alpha=6.0, tau_entry_beta=4.0,
            tau_exit_alpha=4.0, tau_exit_beta=6.0,
            w_momentum_alpha=4.0, w_momentum_beta=6.0,
            w_reversion_alpha=4.0, w_reversion_beta=6.0,
            w_elliott_alpha=4.0, w_elliott_beta=6.0,  # More Elliott weight
        ),
        "likelihood": LikelihoodConfig(observation_weight=0.25),
        "risk": RiskConfig(max_drawdown=0.10, warning_drawdown=0.05),
    },
    TradingTier.POSITION: {
        "prior": PriorConfig(
            tau_entry_alpha=8.0, tau_entry_beta=5.0,  # Stronger prior
            tau_exit_alpha=5.0, tau_exit_beta=8.0,
            w_momentum_alpha=5.0, w_momentum_beta=7.0,
            w_reversion_alpha=5.0, w_reversion_beta=7.0,
            w_elliott_alpha=5.0, w_elliott_beta=5.0,  # Highest Elliott weight
        ),
        "likelihood": LikelihoodConfig(observation_weight=0.1),  # Slow adaptation
        "risk": RiskConfig(max_drawdown=0.15, warning_drawdown=0.07),
    },
}


@dataclass
class BayesianConfig:
    """
    Complete Bayesian trading configuration.

    Combines prior, likelihood, risk, and Elliott Wave configs.
    """
    tier: TradingTier = TradingTier.SWING
    prior: PriorConfig = field(default_factory=PriorConfig)
    likelihood: LikelihoodConfig = field(default_factory=LikelihoodConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    elliott: ElliottWaveConfig = field(default_factory=ElliottWaveConfig)

    # Asymmetric updates (learn faster from losses)
    asymmetric_enabled: bool = True
    loss_multiplier: float = 1.5        # 50% more weight on losses
    gain_multiplier: float = 0.75       # 25% less weight on gains

    # Audit trail
    audit_enabled: bool = True
    audit_interval: int = 100           # Log every N ticks

    @classmethod
    def from_tier(cls, tier: TradingTier) -> "BayesianConfig":
        """Create config from trading tier preset."""
        tier_config = TIER_CONFIGS.get(tier, TIER_CONFIGS[TradingTier.SWING])
        return cls(
            tier=tier,
            prior=tier_config["prior"],
            likelihood=tier_config["likelihood"],
            risk=tier_config["risk"],
        )

    @classmethod
    def scalper(cls) -> "BayesianConfig":
        return cls.from_tier(TradingTier.SCALPER)

    @classmethod
    def daytrader(cls) -> "BayesianConfig":
        return cls.from_tier(TradingTier.DAYTRADER)

    @classmethod
    def swing(cls) -> "BayesianConfig":
        return cls.from_tier(TradingTier.SWING)

    @classmethod
    def position(cls) -> "BayesianConfig":
        return cls.from_tier(TradingTier.POSITION)
