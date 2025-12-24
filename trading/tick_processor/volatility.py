"""
Tick Volatility Estimators
==========================

Various volatility estimators for tick data.

Methods:
1. Return volatility: std of tick-to-tick returns
2. Range volatility: based on price range
3. Parkinson: high-low range estimator
4. Garman-Klass: OHLC-based (adapted for ticks)
5. Realized volatility: sum of squared returns
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Deque, Optional
from collections import deque
import math


@dataclass
class VolatilityResult:
    """Result of volatility calculation."""
    return_volatility: float     # Std of returns
    range_volatility: float      # Based on price range
    realized_volatility: float   # Sum of squared returns
    volatility_of_volatility: float  # Meta-volatility


class TickVolatility:
    """
    Calculates volatility metrics from tick data.

    All volatility measures are annualized by default.
    Assumes ~250 trading days, ~6.5 hours per day.
    """

    # Annualization factors
    TICKS_PER_DAY: int = 100000  # Approximate
    TRADING_DAYS_PER_YEAR: int = 252

    def __init__(
        self,
        window_size: int = 100,
        vol_of_vol_window: int = 20,
    ):
        """
        Initialize volatility calculator.

        Args:
            window_size: Number of ticks for volatility calculation
            vol_of_vol_window: Window for volatility-of-volatility
        """
        self.window_size = window_size
        self.vol_of_vol_window = vol_of_vol_window

        # Rolling windows
        self.prices: Deque[float] = deque(maxlen=window_size)
        self.returns: Deque[float] = deque(maxlen=window_size)
        self.squared_returns: Deque[float] = deque(maxlen=window_size)
        self.volatilities: Deque[float] = deque(maxlen=vol_of_vol_window)

        # State
        self.last_price: float = 0.0
        self.tick_count: int = 0

    def process_tick(self, price: float) -> VolatilityResult:
        """
        Process a single tick and calculate volatility metrics.

        Args:
            price: Current tick price

        Returns:
            VolatilityResult with all metrics
        """
        self.tick_count += 1
        self.prices.append(price)

        # Calculate return
        if self.last_price > 0:
            tick_return = (price - self.last_price) / self.last_price
        else:
            tick_return = 0.0

        self.returns.append(tick_return)
        self.squared_returns.append(tick_return ** 2)
        self.last_price = price

        # Calculate metrics
        return_vol = self._calculate_return_volatility()
        range_vol = self._calculate_range_volatility()
        realized_vol = self._calculate_realized_volatility()

        # Track volatility history for vol-of-vol
        self.volatilities.append(return_vol)
        vol_of_vol = self._calculate_vol_of_vol()

        return VolatilityResult(
            return_volatility=return_vol,
            range_volatility=range_vol,
            realized_volatility=realized_vol,
            volatility_of_volatility=vol_of_vol,
        )

    def _calculate_return_volatility(self) -> float:
        """Calculate standard deviation of returns."""
        if len(self.returns) < 2:
            return 0.0

        returns = list(self.returns)
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)

        # Per-tick volatility
        tick_vol = math.sqrt(variance) if variance > 0 else 0.0

        # Annualize (assuming independent ticks)
        # annualized_vol = tick_vol * sqrt(ticks_per_year)
        annualization_factor = math.sqrt(self.TICKS_PER_DAY * self.TRADING_DAYS_PER_YEAR)

        return tick_vol * annualization_factor

    def _calculate_range_volatility(self) -> float:
        """Calculate volatility from price range (Parkinson-like)."""
        if len(self.prices) < 2:
            return 0.0

        prices = list(self.prices)
        high = max(prices)
        low = min(prices)

        if low <= 0:
            return 0.0

        # Parkinson estimator
        log_range = math.log(high / low)
        range_vol = log_range / (2 * math.sqrt(math.log(2)))

        # Scale to window size and annualize
        annualization_factor = math.sqrt(
            self.TICKS_PER_DAY * self.TRADING_DAYS_PER_YEAR / len(self.prices)
        )

        return range_vol * annualization_factor

    def _calculate_realized_volatility(self) -> float:
        """Calculate realized volatility (sum of squared returns)."""
        if len(self.squared_returns) < 2:
            return 0.0

        realized_var = sum(self.squared_returns)

        # Scale to annualized
        annualization_factor = self.TICKS_PER_DAY * self.TRADING_DAYS_PER_YEAR / len(self.squared_returns)

        return math.sqrt(realized_var * annualization_factor)

    def _calculate_vol_of_vol(self) -> float:
        """Calculate volatility of volatility."""
        if len(self.volatilities) < 2:
            return 0.0

        vols = list(self.volatilities)
        mean = sum(vols) / len(vols)
        variance = sum((v - mean) ** 2 for v in vols) / (len(vols) - 1)

        return math.sqrt(variance) if variance > 0 else 0.0

    def get_volatility_regime(self, result: VolatilityResult, anchor: float) -> str:
        """
        Classify current volatility regime.

        Args:
            result: Current volatility result
            anchor: Reference volatility

        Returns:
            "low", "normal", "high", or "extreme"
        """
        ratio = result.return_volatility / anchor if anchor > 0 else 1.0

        if ratio < 0.5:
            return "low"
        elif ratio < 1.5:
            return "normal"
        elif ratio < 3.0:
            return "high"
        else:
            return "extreme"

    def is_volatility_expanding(self) -> bool:
        """Check if volatility is expanding (trending up)."""
        if len(self.volatilities) < 5:
            return False

        recent = list(self.volatilities)[-3:]
        older = list(self.volatilities)[-5:-2]

        return sum(recent) / len(recent) > sum(older) / len(older) * 1.2

    def is_volatility_contracting(self) -> bool:
        """Check if volatility is contracting (trending down)."""
        if len(self.volatilities) < 5:
            return False

        recent = list(self.volatilities)[-3:]
        older = list(self.volatilities)[-5:-2]

        return sum(recent) / len(recent) < sum(older) / len(older) * 0.8

    def reset(self) -> None:
        """Reset calculator state."""
        self.prices.clear()
        self.returns.clear()
        self.squared_returns.clear()
        self.volatilities.clear()
        self.last_price = 0.0
        self.tick_count = 0
