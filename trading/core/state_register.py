"""
Trading State Register
======================

Immutable state container for trading system, inspired by v2.7 StateRegister.
Uses tick-based concepts instead of time-based.

State Components:
- Entry/Exit thresholds (adaptive based on volatility)
- Signal weights (momentum, mean-reversion, noise)
- Position scalar (0-1 sizing factor)
- Volatility anchor (reference for sizing)
- Regime flag (trending/ranging/crisis)
- Drawdown tracking
"""

from __future__ import annotations
from dataclasses import dataclass, replace
from typing import Tuple, Literal
import math


RegimeType = Literal["trending", "ranging", "crisis", "unknown"]


@dataclass(frozen=True)
class TradingStateRegister:
    """
    Immutable trading state container.

    Tick-based state evolution with bounded parameters.
    All values have hard limits to prevent drift.

    Attributes:
        tau_entry: Entry signal threshold [0.1, 0.9]
        tau_exit: Exit signal threshold [0.1, 0.9]
        w_momentum: Weight for momentum signal [0, 1]
        w_reversion: Weight for mean-reversion signal [0, 1]
        w_noise: Weight for noise/filtering [0, 1]
        position_scalar: Position sizing factor [0, 1]
        volatility_anchor: Reference volatility for sizing
        regime: Current market regime
        drawdown: Current drawdown level [0, 1]
        tick_count: Number of ticks processed
    """

    # Thresholds (from v2.7 tau concept)
    tau_entry: float = 0.6
    tau_exit: float = 0.4

    # Signal weights (from v2.7 w_tone concept, must sum to 1)
    w_momentum: float = 0.4      # Like Rajas - action tendency
    w_reversion: float = 0.4    # Like Sattva - stability tendency
    w_noise: float = 0.2        # Like Tamas - inertia/congestion

    # Trading-specific state
    position_scalar: float = 1.0      # [0, 1] sizing multiplier
    volatility_anchor: float = 0.02   # Reference annualized vol
    regime: RegimeType = "unknown"
    drawdown: float = 0.0             # [0, 1] current drawdown

    # Tracking
    tick_count: int = 0
    last_update_tick: int = 0

    # Bounds (class constants)
    TAU_MIN: float = 0.1
    TAU_MAX: float = 0.9
    WEIGHT_MIN: float = 0.0
    WEIGHT_MAX: float = 1.0
    POSITION_SCALAR_MIN: float = 0.0
    POSITION_SCALAR_MAX: float = 1.0
    VOLATILITY_MIN: float = 0.001
    VOLATILITY_MAX: float = 1.0
    DRAWDOWN_MAX: float = 1.0

    def __post_init__(self) -> None:
        """Validate bounds on creation."""
        self._validate()

    def _validate(self) -> None:
        """Ensure all values are within bounds."""
        if not (self.TAU_MIN <= self.tau_entry <= self.TAU_MAX):
            raise ValueError(f"tau_entry {self.tau_entry} out of bounds [{self.TAU_MIN}, {self.TAU_MAX}]")
        if not (self.TAU_MIN <= self.tau_exit <= self.TAU_MAX):
            raise ValueError(f"tau_exit {self.tau_exit} out of bounds [{self.TAU_MIN}, {self.TAU_MAX}]")

        # Weights must be non-negative and sum to 1
        weights = (self.w_momentum, self.w_reversion, self.w_noise)
        if any(w < self.WEIGHT_MIN or w > self.WEIGHT_MAX for w in weights):
            raise ValueError(f"Weights must be in [{self.WEIGHT_MIN}, {self.WEIGHT_MAX}]")

        weight_sum = sum(weights)
        if abs(weight_sum - 1.0) > 1e-6:
            raise ValueError(f"Weights must sum to 1.0, got {weight_sum}")

        if not (self.POSITION_SCALAR_MIN <= self.position_scalar <= self.POSITION_SCALAR_MAX):
            raise ValueError(f"position_scalar {self.position_scalar} out of bounds")

        if not (self.VOLATILITY_MIN <= self.volatility_anchor <= self.VOLATILITY_MAX):
            raise ValueError(f"volatility_anchor {self.volatility_anchor} out of bounds")

        if not (0.0 <= self.drawdown <= self.DRAWDOWN_MAX):
            raise ValueError(f"drawdown {self.drawdown} out of bounds")

    @property
    def signal_weights(self) -> Tuple[float, float, float]:
        """Return weights as tuple (momentum, reversion, noise)."""
        return (self.w_momentum, self.w_reversion, self.w_noise)

    @property
    def is_crisis_mode(self) -> bool:
        """Check if in crisis regime."""
        return self.regime == "crisis"

    @property
    def is_risk_off(self) -> bool:
        """Check if risk should be reduced (high drawdown or crisis)."""
        return self.drawdown > 0.1 or self.is_crisis_mode

    def with_tau(self, tau_entry: float, tau_exit: float) -> TradingStateRegister:
        """Create new state with updated thresholds (bounded)."""
        return replace(
            self,
            tau_entry=max(self.TAU_MIN, min(self.TAU_MAX, tau_entry)),
            tau_exit=max(self.TAU_MIN, min(self.TAU_MAX, tau_exit)),
        )

    def with_weights(
        self,
        w_momentum: float,
        w_reversion: float,
        w_noise: float
    ) -> TradingStateRegister:
        """Create new state with updated weights (normalized to sum to 1)."""
        total = w_momentum + w_reversion + w_noise
        if total <= 0:
            raise ValueError("Weights must sum to positive value")

        return replace(
            self,
            w_momentum=w_momentum / total,
            w_reversion=w_reversion / total,
            w_noise=w_noise / total,
        )

    def with_position_scalar(self, scalar: float) -> TradingStateRegister:
        """Create new state with updated position scalar (bounded 0-1)."""
        return replace(
            self,
            position_scalar=max(self.POSITION_SCALAR_MIN, min(self.POSITION_SCALAR_MAX, scalar)),
        )

    def with_volatility_anchor(self, vol: float) -> TradingStateRegister:
        """Create new state with updated volatility anchor (bounded)."""
        return replace(
            self,
            volatility_anchor=max(self.VOLATILITY_MIN, min(self.VOLATILITY_MAX, vol)),
        )

    def with_regime(self, regime: RegimeType) -> TradingStateRegister:
        """Create new state with updated regime."""
        return replace(self, regime=regime)

    def with_drawdown(self, drawdown: float) -> TradingStateRegister:
        """Create new state with updated drawdown (bounded 0-1)."""
        return replace(
            self,
            drawdown=max(0.0, min(self.DRAWDOWN_MAX, drawdown)),
        )

    def with_tick_update(self, tick_count: int) -> TradingStateRegister:
        """Create new state with updated tick count."""
        return replace(
            self,
            tick_count=tick_count,
            last_update_tick=tick_count,
        )

    def reset_to_defaults(self) -> TradingStateRegister:
        """Reset state to default values (circuit breaker)."""
        return TradingStateRegister(
            tick_count=self.tick_count,
            last_update_tick=self.tick_count,
        )

    def blend_with(
        self,
        target: TradingStateRegister,
        alpha: float
    ) -> TradingStateRegister:
        """
        EMA blend current state with target state.

        new_state = (1 - alpha) * current + alpha * target

        This is the core v2.7 state evolution formula adapted for trading.
        """
        if not (0.0 < alpha <= 1.0):
            raise ValueError(f"Alpha must be in (0, 1], got {alpha}")

        def ema(current: float, target: float) -> float:
            return (1 - alpha) * current + alpha * target

        # Blend thresholds
        new_tau_entry = ema(self.tau_entry, target.tau_entry)
        new_tau_exit = ema(self.tau_exit, target.tau_exit)

        # Blend weights (will be renormalized)
        new_w_mom = ema(self.w_momentum, target.w_momentum)
        new_w_rev = ema(self.w_reversion, target.w_reversion)
        new_w_noise = ema(self.w_noise, target.w_noise)

        # Blend position scalar
        new_pos_scalar = ema(self.position_scalar, target.position_scalar)

        # Blend volatility anchor
        new_vol = ema(self.volatility_anchor, target.volatility_anchor)

        # Create new state with blended values
        return (
            self
            .with_tau(new_tau_entry, new_tau_exit)
            .with_weights(new_w_mom, new_w_rev, new_w_noise)
            .with_position_scalar(new_pos_scalar)
            .with_volatility_anchor(new_vol)
            .with_regime(target.regime)  # Regime is discrete, take target
            .with_drawdown(target.drawdown)  # Drawdown is current state
            .with_tick_update(target.tick_count)
        )

    def to_dict(self) -> dict:
        """Export state to dictionary for logging/audit."""
        return {
            "tau_entry": self.tau_entry,
            "tau_exit": self.tau_exit,
            "w_momentum": self.w_momentum,
            "w_reversion": self.w_reversion,
            "w_noise": self.w_noise,
            "position_scalar": self.position_scalar,
            "volatility_anchor": self.volatility_anchor,
            "regime": self.regime,
            "drawdown": self.drawdown,
            "tick_count": self.tick_count,
            "last_update_tick": self.last_update_tick,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TradingStateRegister:
        """Create state from dictionary."""
        return cls(**data)

    @classmethod
    def default_for_regime(cls, regime: RegimeType) -> TradingStateRegister:
        """Create regime-appropriate default state."""
        if regime == "trending":
            return cls(
                tau_entry=0.55,
                tau_exit=0.45,
                w_momentum=0.6,
                w_reversion=0.2,
                w_noise=0.2,
                regime=regime,
            )
        elif regime == "ranging":
            return cls(
                tau_entry=0.65,
                tau_exit=0.35,
                w_momentum=0.2,
                w_reversion=0.6,
                w_noise=0.2,
                regime=regime,
            )
        elif regime == "crisis":
            return cls(
                tau_entry=0.8,
                tau_exit=0.2,
                w_momentum=0.1,
                w_reversion=0.1,
                w_noise=0.8,
                position_scalar=0.25,
                regime=regime,
            )
        else:
            return cls(regime=regime)
