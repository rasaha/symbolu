"""
Trading Configuration
=====================

Configuration classes for trading system, inspired by v2.7 V27Config.

Key Configurations:
- AlphaConfig: Learning rate with tick-based half-life
- RiskConfig: Drawdown limits and position constraints
- TradingConfig: Master configuration
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Literal
import math


TierType = Literal["scalper", "daytrader", "swing", "position", "custom"]


@dataclass(frozen=True)
class AlphaConfig:
    """
    Learning rate configuration with tick-based half-life.

    Half-life: number of ticks for influence to decay by 50%
    Formula: half_life = ln(0.5) / ln(1 - alpha) ≈ 0.693 / alpha

    Tier Presets (tick-based):
    - scalper:    α=0.20, half-life ≈  3 ticks (very fast adaptation)
    - daytrader:  α=0.10, half-life ≈  7 ticks (fast adaptation)
    - swing:      α=0.05, half-life ≈ 14 ticks (moderate adaptation)
    - position:   α=0.02, half-life ≈ 35 ticks (slow adaptation)
    """

    alpha: float
    tier: TierType = "custom"

    ALPHA_MIN: float = 0.001
    ALPHA_MAX: float = 0.50

    def __post_init__(self) -> None:
        if not (self.ALPHA_MIN <= self.alpha <= self.ALPHA_MAX):
            raise ValueError(
                f"alpha {self.alpha} out of bounds [{self.ALPHA_MIN}, {self.ALPHA_MAX}]"
            )

    @property
    def half_life_ticks(self) -> float:
        """Number of ticks for 50% decay."""
        return math.log(0.5) / math.log(1 - self.alpha)

    @property
    def decay_90_ticks(self) -> float:
        """Number of ticks for 90% decay (old info mostly forgotten)."""
        return math.log(0.1) / math.log(1 - self.alpha)

    @classmethod
    def scalper(cls) -> AlphaConfig:
        """Fast adaptation for scalping (3 tick half-life)."""
        return cls(alpha=0.20, tier="scalper")

    @classmethod
    def daytrader(cls) -> AlphaConfig:
        """Medium-fast adaptation for day trading (7 tick half-life)."""
        return cls(alpha=0.10, tier="daytrader")

    @classmethod
    def swing(cls) -> AlphaConfig:
        """Moderate adaptation for swing trading (14 tick half-life)."""
        return cls(alpha=0.05, tier="swing")

    @classmethod
    def position(cls) -> AlphaConfig:
        """Slow adaptation for position trading (35 tick half-life)."""
        return cls(alpha=0.02, tier="position")

    @classmethod
    def for_tier(cls, tier: TierType) -> AlphaConfig:
        """Get config for specified tier."""
        configs = {
            "scalper": cls.scalper,
            "daytrader": cls.daytrader,
            "swing": cls.swing,
            "position": cls.position,
        }
        if tier in configs:
            return configs[tier]()
        raise ValueError(f"Unknown tier: {tier}")


@dataclass(frozen=True)
class RiskConfig:
    """
    Risk management configuration.

    Defines drawdown limits and position constraints.
    """

    # Drawdown circuit breakers
    max_drawdown: float = 0.10           # 10% max drawdown
    warning_drawdown: float = 0.05       # 5% warning level
    crisis_drawdown: float = 0.08        # 8% triggers crisis mode

    # Position constraints
    max_position_scalar: float = 1.0     # Max position size multiplier
    crisis_position_scalar: float = 0.25 # Position scalar in crisis
    min_position_scalar: float = 0.0     # Can go to zero

    # Volatility constraints
    max_volatility_ratio: float = 3.0    # Max vol / anchor vol ratio
    crisis_volatility_ratio: float = 2.5 # Vol ratio triggering crisis

    # Recovery
    recovery_alpha: float = 0.01         # Slow recovery after crisis
    restart_decay_factor: float = 0.5    # How much state to keep on restart

    def __post_init__(self) -> None:
        if not (0.0 < self.warning_drawdown <= self.crisis_drawdown <= self.max_drawdown <= 1.0):
            raise ValueError("Drawdown levels must be: 0 < warning <= crisis <= max <= 1")
        if not (0.0 <= self.min_position_scalar <= self.crisis_position_scalar <= self.max_position_scalar <= 1.0):
            raise ValueError("Position scalars must be properly ordered")

    def should_reduce_risk(self, drawdown: float, volatility_ratio: float) -> bool:
        """Check if risk should be reduced."""
        return drawdown >= self.warning_drawdown or volatility_ratio >= self.max_volatility_ratio

    def should_enter_crisis(self, drawdown: float, volatility_ratio: float) -> bool:
        """Check if crisis mode should be triggered."""
        return drawdown >= self.crisis_drawdown or volatility_ratio >= self.crisis_volatility_ratio

    def should_halt(self, drawdown: float) -> bool:
        """Check if trading should halt (max drawdown hit)."""
        return drawdown >= self.max_drawdown

    def compute_position_scalar(self, drawdown: float, volatility_ratio: float) -> float:
        """
        Compute position scalar based on current risk state.

        Smoothly reduces position as risk increases.
        """
        if self.should_halt(drawdown):
            return self.min_position_scalar

        if self.should_enter_crisis(drawdown, volatility_ratio):
            return self.crisis_position_scalar

        # Linear interpolation between max and crisis based on drawdown
        if drawdown >= self.warning_drawdown:
            progress = (drawdown - self.warning_drawdown) / (self.crisis_drawdown - self.warning_drawdown)
            return self.max_position_scalar - progress * (self.max_position_scalar - self.crisis_position_scalar)

        # Linear interpolation based on volatility
        if volatility_ratio >= 1.5:
            vol_progress = (volatility_ratio - 1.5) / (self.crisis_volatility_ratio - 1.5)
            vol_scalar = self.max_position_scalar - vol_progress * (self.max_position_scalar - self.crisis_position_scalar)
            return min(self.max_position_scalar, vol_scalar)

        return self.max_position_scalar

    @classmethod
    def conservative(cls) -> RiskConfig:
        """Conservative risk settings."""
        return cls(
            max_drawdown=0.05,
            warning_drawdown=0.02,
            crisis_drawdown=0.04,
            crisis_position_scalar=0.1,
        )

    @classmethod
    def moderate(cls) -> RiskConfig:
        """Moderate risk settings (default)."""
        return cls()

    @classmethod
    def aggressive(cls) -> RiskConfig:
        """Aggressive risk settings."""
        return cls(
            max_drawdown=0.20,
            warning_drawdown=0.10,
            crisis_drawdown=0.15,
            crisis_position_scalar=0.5,
        )


@dataclass(frozen=True)
class AsymmetricConfig:
    """
    Asymmetric response configuration.

    Trading needs different behavior for gains vs losses.
    Losses should be learned from faster than gains.
    """

    # Alpha multipliers
    loss_alpha_multiplier: float = 2.0    # Learn 2x faster from losses
    gain_alpha_multiplier: float = 0.5    # Learn 0.5x from gains
    neutral_band: float = 0.001           # [-0.1%, +0.1%] = neutral

    def adjust_alpha(self, base_alpha: float, pnl_change: float) -> float:
        """
        Adjust alpha based on recent P&L change.

        Args:
            base_alpha: Base learning rate
            pnl_change: Recent P&L change (as fraction, e.g., -0.01 = -1%)
        """
        if abs(pnl_change) <= self.neutral_band:
            return base_alpha
        elif pnl_change < 0:
            # Loss: learn faster
            return min(0.5, base_alpha * self.loss_alpha_multiplier)
        else:
            # Gain: learn slower
            return max(0.001, base_alpha * self.gain_alpha_multiplier)


@dataclass(frozen=True)
class TradingConfig:
    """
    Master trading configuration.

    Combines alpha, risk, and asymmetric settings.
    """

    alpha_config: AlphaConfig
    risk_config: RiskConfig
    asymmetric_config: AsymmetricConfig

    # Feature flags
    enable_asymmetric: bool = True
    enable_regime_detection: bool = True
    enable_crisis_mode: bool = True

    # Update frequency
    min_ticks_between_updates: int = 1   # Update every tick
    state_snapshot_interval: int = 100   # Snapshot state every N ticks

    @property
    def alpha(self) -> float:
        """Base learning rate."""
        return self.alpha_config.alpha

    @property
    def half_life_ticks(self) -> float:
        """Tick-based half-life."""
        return self.alpha_config.half_life_ticks

    @classmethod
    def for_tier(
        cls,
        tier: TierType,
        risk_profile: Literal["conservative", "moderate", "aggressive"] = "moderate",
    ) -> TradingConfig:
        """Create configuration for specified tier and risk profile."""
        alpha = AlphaConfig.for_tier(tier)

        risk_configs = {
            "conservative": RiskConfig.conservative,
            "moderate": RiskConfig.moderate,
            "aggressive": RiskConfig.aggressive,
        }
        risk = risk_configs[risk_profile]()

        return cls(
            alpha_config=alpha,
            risk_config=risk,
            asymmetric_config=AsymmetricConfig(),
        )

    @classmethod
    def scalper(cls) -> TradingConfig:
        """Scalper preset."""
        return cls.for_tier("scalper", "aggressive")

    @classmethod
    def daytrader(cls) -> TradingConfig:
        """Day trader preset."""
        return cls.for_tier("daytrader", "moderate")

    @classmethod
    def swing(cls) -> TradingConfig:
        """Swing trader preset."""
        return cls.for_tier("swing", "moderate")

    @classmethod
    def position(cls) -> TradingConfig:
        """Position trader preset."""
        return cls.for_tier("position", "conservative")
