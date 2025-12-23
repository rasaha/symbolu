"""
Bayesian Observables

Market observables for the Bayesian trading system.
Similar to trading/core/observables.py but includes Elliott Wave signals.
"""

from dataclasses import dataclass
from typing import Optional
import math


@dataclass(frozen=True)
class BayesianObservables:
    """
    Observable market signals for Bayesian state updates.

    Extends the EMA model observables with Elliott Wave signals.
    All values normalized to [-1, 1] or [0, 1] range.
    """
    # Core momentum indicators (same as EMA model)
    momentum: float = 0.0           # [-1, 1] directional pressure
    mean_reversion: float = 0.0     # [-1, 1] price vs fair value
    noise_level: float = 0.5        # [0, 1] market microstructure noise

    # Volatility indicators
    tick_volatility: float = 1.0    # Ratio: current/anchor volatility
    volatility_percentile: float = 0.5  # [0, 1] where current vol ranks

    # Order flow indicators
    order_imbalance: float = 0.0    # [-1, 1] buy/sell pressure
    spread_normalized: float = 1.0  # Ratio: current/avg spread
    tick_intensity: float = 1.0     # Ratio: current/avg ticks per second

    # Elliott Wave signals (NEW)
    elliott_signal: float = 0.0     # [-1, 1] wave-based direction
    elliott_confidence: float = 0.0  # [0, 1] pattern confidence
    current_wave: Optional[int] = None  # 1-5 or 6-8 (A-C)
    wave_position: float = 0.0      # [0, 1] position within current wave

    # Fibonacci levels (NEW)
    fib_support_distance: float = 0.0   # Distance to nearest support (% of price)
    fib_resistance_distance: float = 0.0  # Distance to nearest resistance

    # Price context
    price: float = 0.0
    vwap: float = 0.0

    def __post_init__(self):
        """Validate ranges."""
        # Clamp values to valid ranges
        object.__setattr__(self, 'momentum', max(-1.0, min(1.0, self.momentum)))
        object.__setattr__(self, 'mean_reversion', max(-1.0, min(1.0, self.mean_reversion)))
        object.__setattr__(self, 'noise_level', max(0.0, min(1.0, self.noise_level)))
        object.__setattr__(self, 'order_imbalance', max(-1.0, min(1.0, self.order_imbalance)))
        object.__setattr__(self, 'elliott_signal', max(-1.0, min(1.0, self.elliott_signal)))
        object.__setattr__(self, 'elliott_confidence', max(0.0, min(1.0, self.elliott_confidence)))

    @property
    def price_vs_vwap(self) -> float:
        """Price position relative to VWAP."""
        if self.vwap == 0:
            return 0.0
        return (self.price - self.vwap) / self.vwap

    def compute_composite_signal(
        self,
        w_momentum: float = 0.3,
        w_reversion: float = 0.3,
        w_elliott: float = 0.3,
        w_imbalance: float = 0.1,
    ) -> float:
        """
        Compute weighted composite signal.

        Args:
            w_momentum: Weight for momentum signal
            w_reversion: Weight for mean reversion signal
            w_elliott: Weight for Elliott wave signal
            w_imbalance: Weight for order imbalance

        Returns:
            Composite signal in [-1, 1]
        """
        total_weight = w_momentum + w_reversion + w_elliott + w_imbalance

        if total_weight == 0:
            return 0.0

        # Weight Elliott signal by its confidence
        adjusted_elliott = self.elliott_signal * self.elliott_confidence

        signal = (
            w_momentum * self.momentum +
            w_reversion * self.mean_reversion +
            w_elliott * adjusted_elliott +
            w_imbalance * self.order_imbalance
        ) / total_weight

        # Apply volatility damping
        signal = self._apply_volatility_damping(signal)

        # Apply noise filtering
        signal = self._apply_noise_filter(signal)

        return max(-1.0, min(1.0, signal))

    def _apply_volatility_damping(self, signal: float) -> float:
        """Reduce signal strength in high volatility."""
        if self.tick_volatility <= 1.0:
            return signal
        elif self.tick_volatility <= 2.0:
            # Linear damping: 100% to 70%
            damping = 1.0 - 0.3 * (self.tick_volatility - 1.0)
            return signal * damping
        elif self.tick_volatility <= 3.0:
            # Stronger damping: 70% to 30%
            damping = 0.7 - 0.4 * (self.tick_volatility - 2.0)
            return signal * damping
        else:
            # Extreme volatility: minimal signal
            return signal * 0.1

    def _apply_noise_filter(self, signal: float) -> float:
        """Reduce signal in high noise environments."""
        if self.noise_level <= 0.3:
            return signal  # Low noise - full signal
        elif self.noise_level <= 0.7:
            # Moderate noise - gradual reduction
            reduction = (self.noise_level - 0.3) / 0.4  # 0 to 1
            return signal * (1.0 - 0.3 * reduction)
        else:
            # High noise - significant reduction
            return signal * 0.5

    def to_likelihood_observation(self) -> dict:
        """
        Convert observables to likelihood observations for Bayesian update.

        Returns dict mapping parameter names to (observation, weight) tuples.
        """
        observations = {}

        # Signal strength indicates optimal threshold
        signal_strength = abs(self.compute_composite_signal())

        # If signal is strong, entry threshold should be lower (easier entry)
        # Map signal strength to tau_entry observation
        observations["tau_entry"] = (
            0.7 - 0.2 * signal_strength,  # Lower threshold when signal strong
            self.elliott_confidence * 0.5 + 0.5,  # Weight by Elliott confidence
        )

        observations["tau_exit"] = (
            0.3 + 0.2 * signal_strength,  # Higher exit threshold when signal strong
            self.elliott_confidence * 0.5 + 0.5,
        )

        # Momentum weight should increase when momentum is clear
        momentum_clarity = abs(self.momentum)
        observations["w_momentum"] = (
            0.3 + 0.3 * momentum_clarity,
            momentum_clarity,
        )

        # Reversion weight should increase when price deviates from VWAP
        reversion_strength = abs(self.mean_reversion)
        observations["w_reversion"] = (
            0.3 + 0.3 * reversion_strength,
            reversion_strength,
        )

        # Elliott weight from confidence
        observations["w_elliott"] = (
            0.2 + 0.4 * self.elliott_confidence,
            self.elliott_confidence,
        )

        # Position sizing from volatility
        # Lower position in high volatility
        vol_factor = 1.0 / max(0.5, self.tick_volatility)
        observations["position_scalar"] = (
            min(1.0, vol_factor),
            0.5,  # Moderate weight
        )

        return observations

    @classmethod
    def empty(cls) -> "BayesianObservables":
        """Create empty observables (neutral state)."""
        return cls()

    @classmethod
    def from_tick_data(
        cls,
        price: float,
        vwap: float,
        momentum: float,
        order_imbalance: float,
        volatility_ratio: float,
        spread_ratio: float,
        noise: float,
        elliott_signal: float = 0.0,
        elliott_confidence: float = 0.0,
        current_wave: Optional[int] = None,
    ) -> "BayesianObservables":
        """
        Create observables from tick processor output.

        Args:
            price: Current price
            vwap: Volume-weighted average price
            momentum: Directional momentum [-1, 1]
            order_imbalance: Buy/sell imbalance [-1, 1]
            volatility_ratio: Current vol / anchor vol
            spread_ratio: Current spread / avg spread
            noise: Noise level [0, 1]
            elliott_signal: Elliott wave signal [-1, 1]
            elliott_confidence: Wave pattern confidence [0, 1]
            current_wave: Current wave number (1-5 or 6-8)

        Returns:
            BayesianObservables instance
        """
        # Calculate mean reversion from price vs VWAP
        mean_reversion = 0.0
        if vwap > 0:
            deviation = (price - vwap) / vwap
            # Convert to [-1, 1] with saturation at ±2%
            mean_reversion = max(-1.0, min(1.0, -deviation / 0.02))

        return cls(
            momentum=momentum,
            mean_reversion=mean_reversion,
            noise_level=noise,
            tick_volatility=volatility_ratio,
            order_imbalance=order_imbalance,
            spread_normalized=spread_ratio,
            elliott_signal=elliott_signal,
            elliott_confidence=elliott_confidence,
            current_wave=current_wave,
            price=price,
            vwap=vwap,
        )
