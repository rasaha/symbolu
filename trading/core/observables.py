"""
Tick Observables
================

Tick-based input signals for trading state evolution.
Analogous to v2.7 Observables (S, R, T, H, C_contr, F_fail).

Tick-Based Signals:
- Momentum (like Rajas): Directional pressure from order flow
- Mean Reversion (like Sattva): Price deviation from fair value
- Noise (like Tamas): Market microstructure noise level

Additional Trading Signals:
- Volatility: Current tick volatility vs anchor
- Order Imbalance: Buy vs sell pressure
- Spread: Bid-ask spread normalized
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math


@dataclass(frozen=True)
class TickObservables:
    """
    Immutable container for tick-based market observables.

    All signals normalized to [0, 1] or [-1, 1] as appropriate.

    Attributes:
        # Core signals (v2.7 analogs)
        momentum: Directional pressure [-1, 1], positive = bullish
        mean_reversion: Price vs fair value [-1, 1], positive = oversold
        noise_level: Microstructure noise [0, 1], higher = noisier

        # Trading-specific signals
        tick_volatility: Current tick vol / anchor vol ratio
        order_imbalance: (buy_volume - sell_volume) / total_volume [-1, 1]
        spread_normalized: Current spread / average spread ratio
        tick_intensity: Ticks per second / average ticks per second

        # Meta
        tick_number: Current tick sequence number
        timestamp_ns: Nanosecond timestamp (for tick ordering)
    """

    # Core signals (analogs to S, R, T)
    momentum: float = 0.0           # [-1, 1] directional pressure
    mean_reversion: float = 0.0     # [-1, 1] deviation from fair value
    noise_level: float = 0.5        # [0, 1] microstructure noise

    # Trading-specific signals
    tick_volatility: float = 1.0    # ratio: current_vol / anchor_vol
    order_imbalance: float = 0.0    # [-1, 1] buy/sell pressure
    spread_normalized: float = 1.0  # ratio: current_spread / avg_spread
    tick_intensity: float = 1.0     # ratio: current_tps / avg_tps

    # Meta
    tick_number: int = 0
    timestamp_ns: int = 0

    # Bounds
    SIGNAL_MIN: float = -1.0
    SIGNAL_MAX: float = 1.0
    NOISE_MIN: float = 0.0
    NOISE_MAX: float = 1.0
    RATIO_MIN: float = 0.01
    RATIO_MAX: float = 100.0

    def __post_init__(self) -> None:
        """Validate bounds on creation."""
        self._validate()

    def _validate(self) -> None:
        """Ensure all values are within bounds."""
        if not (self.SIGNAL_MIN <= self.momentum <= self.SIGNAL_MAX):
            raise ValueError(f"momentum {self.momentum} out of bounds")
        if not (self.SIGNAL_MIN <= self.mean_reversion <= self.SIGNAL_MAX):
            raise ValueError(f"mean_reversion {self.mean_reversion} out of bounds")
        if not (self.NOISE_MIN <= self.noise_level <= self.NOISE_MAX):
            raise ValueError(f"noise_level {self.noise_level} out of bounds")
        if not (self.SIGNAL_MIN <= self.order_imbalance <= self.SIGNAL_MAX):
            raise ValueError(f"order_imbalance {self.order_imbalance} out of bounds")

    @property
    def is_high_volatility(self) -> bool:
        """Check if volatility is elevated (>2x anchor)."""
        return self.tick_volatility > 2.0

    @property
    def is_wide_spread(self) -> bool:
        """Check if spread is wide (>2x average)."""
        return self.spread_normalized > 2.0

    @property
    def is_bullish(self) -> bool:
        """Check if signals lean bullish."""
        return self.momentum > 0 and self.order_imbalance > 0

    @property
    def is_bearish(self) -> bool:
        """Check if signals lean bearish."""
        return self.momentum < 0 and self.order_imbalance < 0

    @property
    def signal_strength(self) -> float:
        """Combined signal strength [0, 1]."""
        return (abs(self.momentum) + abs(self.mean_reversion) + abs(self.order_imbalance)) / 3

    @property
    def is_noisy(self) -> bool:
        """Check if market is noisy (high noise, wide spread, low intensity)."""
        return self.noise_level > 0.7 or self.spread_normalized > 1.5

    def compute_composite_signal(
        self,
        w_momentum: float = 0.4,
        w_reversion: float = 0.4,
        w_imbalance: float = 0.2,
    ) -> float:
        """
        Compute weighted composite signal [-1, 1].

        Positive = bullish, Negative = bearish
        """
        total_weight = w_momentum + w_reversion + w_imbalance
        if total_weight <= 0:
            return 0.0

        signal = (
            w_momentum * self.momentum +
            w_reversion * self.mean_reversion +
            w_imbalance * self.order_imbalance
        ) / total_weight

        return max(-1.0, min(1.0, signal))

    def volatility_adjusted_signal(self, composite: float) -> float:
        """
        Reduce signal strength in high volatility (risk management).

        In crisis conditions (vol > 3x), signal is heavily dampened.
        """
        if self.tick_volatility <= 1.0:
            return composite
        elif self.tick_volatility <= 2.0:
            # Linear damping between 1x and 2x vol
            damping = 1.0 - 0.3 * (self.tick_volatility - 1.0)
            return composite * damping
        elif self.tick_volatility <= 3.0:
            # Stronger damping between 2x and 3x vol
            damping = 0.7 - 0.4 * (self.tick_volatility - 2.0)
            return composite * damping
        else:
            # Extreme vol: minimal signal
            return composite * 0.1

    def noise_adjusted_signal(self, composite: float) -> float:
        """
        Reduce signal strength in noisy conditions.

        High noise = less confidence in signals.
        """
        confidence = 1.0 - self.noise_level
        return composite * max(0.1, confidence)

    def to_dict(self) -> dict:
        """Export to dictionary for logging."""
        return {
            "momentum": self.momentum,
            "mean_reversion": self.mean_reversion,
            "noise_level": self.noise_level,
            "tick_volatility": self.tick_volatility,
            "order_imbalance": self.order_imbalance,
            "spread_normalized": self.spread_normalized,
            "tick_intensity": self.tick_intensity,
            "tick_number": self.tick_number,
            "timestamp_ns": self.timestamp_ns,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TickObservables:
        """Create from dictionary."""
        return cls(**data)

    @classmethod
    def neutral(cls, tick_number: int = 0) -> TickObservables:
        """Create neutral observables (no signal)."""
        return cls(tick_number=tick_number)

    @classmethod
    def from_tick_data(
        cls,
        price: float,
        fair_value: float,
        tick_size: float,
        volume: float,
        buy_volume: float,
        sell_volume: float,
        current_vol: float,
        anchor_vol: float,
        current_spread: float,
        avg_spread: float,
        ticks_per_second: float,
        avg_tps: float,
        tick_number: int,
        timestamp_ns: int,
        lookback_prices: Optional[list] = None,
    ) -> TickObservables:
        """
        Factory to create observables from raw tick data.

        Args:
            price: Current tick price
            fair_value: Estimated fair value (e.g., VWAP, mid)
            tick_size: Minimum price increment
            volume: Current tick volume
            buy_volume: Identified buy volume
            sell_volume: Identified sell volume
            current_vol: Current volatility estimate
            anchor_vol: Reference volatility
            current_spread: Current bid-ask spread
            avg_spread: Average spread
            ticks_per_second: Current tick rate
            avg_tps: Average tick rate
            tick_number: Sequence number
            timestamp_ns: Nanosecond timestamp
            lookback_prices: Recent prices for momentum calculation
        """
        # Momentum: based on recent price direction
        if lookback_prices and len(lookback_prices) >= 2:
            price_change = price - lookback_prices[0]
            price_range = max(lookback_prices) - min(lookback_prices)
            if price_range > 0:
                momentum = max(-1.0, min(1.0, price_change / price_range))
            else:
                momentum = 0.0
        else:
            momentum = 0.0

        # Mean reversion: deviation from fair value
        deviation = price - fair_value
        deviation_ticks = deviation / tick_size if tick_size > 0 else 0
        # Normalize: 10 ticks = max signal
        mean_reversion = max(-1.0, min(1.0, -deviation_ticks / 10.0))

        # Noise level: based on spread and intensity
        spread_factor = min(1.0, current_spread / (3 * avg_spread)) if avg_spread > 0 else 0.5
        intensity_factor = min(1.0, avg_tps / ticks_per_second) if ticks_per_second > 0 else 0.5
        noise_level = (spread_factor + intensity_factor) / 2

        # Order imbalance
        total_volume = buy_volume + sell_volume
        if total_volume > 0:
            order_imbalance = (buy_volume - sell_volume) / total_volume
        else:
            order_imbalance = 0.0

        # Volatility ratio
        tick_volatility = current_vol / anchor_vol if anchor_vol > 0 else 1.0
        tick_volatility = max(0.01, min(100.0, tick_volatility))

        # Spread ratio
        spread_normalized = current_spread / avg_spread if avg_spread > 0 else 1.0
        spread_normalized = max(0.01, min(100.0, spread_normalized))

        # Intensity ratio
        tick_intensity = ticks_per_second / avg_tps if avg_tps > 0 else 1.0
        tick_intensity = max(0.01, min(100.0, tick_intensity))

        return cls(
            momentum=momentum,
            mean_reversion=mean_reversion,
            noise_level=noise_level,
            tick_volatility=tick_volatility,
            order_imbalance=order_imbalance,
            spread_normalized=spread_normalized,
            tick_intensity=tick_intensity,
            tick_number=tick_number,
            timestamp_ns=timestamp_ns,
        )
