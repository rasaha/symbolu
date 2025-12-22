"""
Tick Aggregator
===============

Aggregates raw tick data into meaningful signals.
Designed for QuantConnect Tick objects.

Key Features:
- Rolling window for price history
- VWAP calculation (fair value proxy)
- Buy/Sell classification using tick rule
- Signal generation from tick stream
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Deque
from collections import deque
import math

from trading.core.observables import TickObservables


@dataclass
class TickData:
    """Raw tick data container."""
    price: float
    volume: float
    bid: float
    ask: float
    timestamp_ns: int
    exchange: str = ""


@dataclass
class TickSignals:
    """
    Aggregated signals from tick stream.

    Intermediate representation between raw ticks and TickObservables.
    """
    # Price signals
    last_price: float = 0.0
    vwap: float = 0.0
    mid_price: float = 0.0
    tick_direction: int = 0  # 1=up, -1=down, 0=unchanged

    # Volume signals
    total_volume: float = 0.0
    buy_volume: float = 0.0
    sell_volume: float = 0.0

    # Spread signals
    current_spread: float = 0.0
    avg_spread: float = 0.0

    # Rate signals
    ticks_in_window: int = 0
    window_duration_ns: int = 0

    # Volatility proxy
    price_range: float = 0.0
    price_std: float = 0.0

    @property
    def imbalance(self) -> float:
        """Order flow imbalance [-1, 1]."""
        total = self.buy_volume + self.sell_volume
        if total <= 0:
            return 0.0
        return (self.buy_volume - self.sell_volume) / total

    @property
    def ticks_per_second(self) -> float:
        """Tick rate."""
        if self.window_duration_ns <= 0:
            return 0.0
        return self.ticks_in_window / (self.window_duration_ns / 1e9)

    @property
    def spread_ratio(self) -> float:
        """Current spread / average spread."""
        if self.avg_spread <= 0:
            return 1.0
        return self.current_spread / self.avg_spread


class TickAggregator:
    """
    Aggregates tick stream into signals.

    Maintains rolling windows for various calculations.
    """

    def __init__(
        self,
        price_window_size: int = 100,
        volume_window_size: int = 50,
        spread_window_size: int = 20,
    ):
        """
        Initialize aggregator with window sizes.

        Args:
            price_window_size: Number of ticks for price calculations
            volume_window_size: Number of ticks for volume calculations
            spread_window_size: Number of ticks for spread calculations
        """
        self.price_window_size = price_window_size
        self.volume_window_size = volume_window_size
        self.spread_window_size = spread_window_size

        # Rolling windows
        self.price_window: Deque[float] = deque(maxlen=price_window_size)
        self.volume_window: Deque[float] = deque(maxlen=volume_window_size)
        self.spread_window: Deque[float] = deque(maxlen=spread_window_size)
        self.timestamp_window: Deque[int] = deque(maxlen=price_window_size)

        # Volume weighted tracking
        self.vwap_sum: float = 0.0
        self.volume_sum: float = 0.0

        # Buy/Sell classification
        self.buy_volume_sum: float = 0.0
        self.sell_volume_sum: float = 0.0

        # State tracking
        self.last_price: float = 0.0
        self.last_mid: float = 0.0
        self.tick_count: int = 0

    def process_tick(self, tick: TickData) -> TickSignals:
        """
        Process a single tick and return aggregated signals.

        Args:
            tick: Raw tick data

        Returns:
            Aggregated signals
        """
        self.tick_count += 1

        # Calculate mid price
        mid_price = (tick.bid + tick.ask) / 2 if tick.bid > 0 and tick.ask > 0 else tick.price
        spread = tick.ask - tick.bid if tick.bid > 0 and tick.ask > 0 else 0.0

        # Determine tick direction
        if self.last_price > 0:
            if tick.price > self.last_price:
                tick_direction = 1
            elif tick.price < self.last_price:
                tick_direction = -1
            else:
                tick_direction = 0
        else:
            tick_direction = 0

        # Classify volume as buy or sell using tick rule
        # If price went up or price at ask -> buy
        # If price went down or price at bid -> sell
        is_buy = self._classify_tick(tick, tick_direction)

        if is_buy:
            self.buy_volume_sum += tick.volume
        else:
            self.sell_volume_sum += tick.volume

        # Update VWAP
        self.vwap_sum += tick.price * tick.volume
        self.volume_sum += tick.volume
        vwap = self.vwap_sum / self.volume_sum if self.volume_sum > 0 else tick.price

        # Update rolling windows
        self.price_window.append(tick.price)
        self.volume_window.append(tick.volume)
        self.spread_window.append(spread)
        self.timestamp_window.append(tick.timestamp_ns)

        # Calculate statistics
        prices = list(self.price_window)
        price_range = max(prices) - min(prices) if len(prices) >= 2 else 0.0
        price_mean = sum(prices) / len(prices)
        price_std = math.sqrt(sum((p - price_mean) ** 2 for p in prices) / len(prices)) if len(prices) >= 2 else 0.0

        # Spread average
        spreads = list(self.spread_window)
        avg_spread = sum(spreads) / len(spreads) if spreads else spread

        # Time window
        if len(self.timestamp_window) >= 2:
            window_duration_ns = self.timestamp_window[-1] - self.timestamp_window[0]
        else:
            window_duration_ns = 0

        # Update state
        self.last_price = tick.price
        self.last_mid = mid_price

        return TickSignals(
            last_price=tick.price,
            vwap=vwap,
            mid_price=mid_price,
            tick_direction=tick_direction,
            total_volume=self.volume_sum,
            buy_volume=self.buy_volume_sum,
            sell_volume=self.sell_volume_sum,
            current_spread=spread,
            avg_spread=avg_spread,
            ticks_in_window=len(self.price_window),
            window_duration_ns=window_duration_ns,
            price_range=price_range,
            price_std=price_std,
        )

    def _classify_tick(self, tick: TickData, tick_direction: int) -> bool:
        """
        Classify tick as buy or sell using Lee-Ready algorithm variant.

        Returns True if classified as buy, False for sell.
        """
        # Primary: quote test
        if tick.bid > 0 and tick.ask > 0:
            mid = (tick.bid + tick.ask) / 2
            if tick.price > mid:
                return True  # Buy
            elif tick.price < mid:
                return False  # Sell

        # Secondary: tick test
        if tick_direction > 0:
            return True
        elif tick_direction < 0:
            return False

        # Tie-breaker: previous classification or default to buy
        return True

    def to_observables(
        self,
        signals: TickSignals,
        volatility_anchor: float = 0.02,
        avg_tps: float = 10.0,
    ) -> TickObservables:
        """
        Convert aggregated signals to TickObservables.

        Args:
            signals: Aggregated signals from process_tick
            volatility_anchor: Reference volatility for ratio
            avg_tps: Average ticks per second for ratio

        Returns:
            TickObservables for state evolution
        """
        prices = list(self.price_window)

        # Momentum: based on price trend
        if len(prices) >= 10:
            recent = prices[-5:]
            older = prices[-10:-5]
            recent_avg = sum(recent) / len(recent)
            older_avg = sum(older) / len(older)
            if older_avg > 0:
                momentum = (recent_avg - older_avg) / older_avg
                momentum = max(-1.0, min(1.0, momentum * 100))  # Scale
            else:
                momentum = 0.0
        else:
            momentum = 0.0

        # Mean reversion: price vs VWAP
        if signals.vwap > 0:
            deviation = (signals.last_price - signals.vwap) / signals.vwap
            mean_reversion = max(-1.0, min(1.0, -deviation * 50))  # Negative: oversold = positive
        else:
            mean_reversion = 0.0

        # Noise level: based on spread and volatility
        if signals.avg_spread > 0 and signals.last_price > 0:
            spread_pct = signals.current_spread / signals.last_price
            noise_level = min(1.0, spread_pct * 100 + 0.3)  # Base noise + spread contribution
        else:
            noise_level = 0.5

        # Tick volatility ratio
        if volatility_anchor > 0 and signals.last_price > 0:
            current_vol = signals.price_std / signals.last_price if signals.price_std > 0 else 0.01
            tick_volatility = current_vol / volatility_anchor
            tick_volatility = max(0.01, min(100.0, tick_volatility))
        else:
            tick_volatility = 1.0

        # Tick intensity
        if avg_tps > 0:
            tick_intensity = signals.ticks_per_second / avg_tps
            tick_intensity = max(0.01, min(100.0, tick_intensity))
        else:
            tick_intensity = 1.0

        return TickObservables(
            momentum=momentum,
            mean_reversion=mean_reversion,
            noise_level=noise_level,
            tick_volatility=tick_volatility,
            order_imbalance=signals.imbalance,
            spread_normalized=signals.spread_ratio,
            tick_intensity=tick_intensity,
            tick_number=self.tick_count,
            timestamp_ns=self.timestamp_window[-1] if self.timestamp_window else 0,
        )

    def reset(self) -> None:
        """Reset aggregator state."""
        self.price_window.clear()
        self.volume_window.clear()
        self.spread_window.clear()
        self.timestamp_window.clear()
        self.vwap_sum = 0.0
        self.volume_sum = 0.0
        self.buy_volume_sum = 0.0
        self.sell_volume_sum = 0.0
        self.last_price = 0.0
        self.last_mid = 0.0
        self.tick_count = 0
