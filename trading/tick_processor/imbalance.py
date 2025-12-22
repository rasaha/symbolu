"""
Order Flow Imbalance
====================

Calculates order flow imbalance from tick data.
Key indicator for detecting buying/selling pressure.

Methods:
1. Volume Imbalance: (buy_vol - sell_vol) / total_vol
2. Trade Imbalance: (buy_trades - sell_trades) / total_trades
3. Dollar Imbalance: weighted by trade value
4. Cumulative Delta: running sum of signed volume
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Deque
from collections import deque


@dataclass
class ImbalanceResult:
    """Result of imbalance calculation."""
    volume_imbalance: float      # [-1, 1]
    trade_imbalance: float       # [-1, 1]
    dollar_imbalance: float      # [-1, 1]
    cumulative_delta: float      # Running sum (can be any value)
    delta_rate: float            # Delta per tick


class OrderFlowImbalance:
    """
    Calculates various order flow imbalance metrics.

    Tick-based analysis of buying vs selling pressure.
    """

    def __init__(self, window_size: int = 100):
        """
        Initialize imbalance calculator.

        Args:
            window_size: Number of ticks for rolling calculations
        """
        self.window_size = window_size

        # Rolling windows
        self.buy_volumes: Deque[float] = deque(maxlen=window_size)
        self.sell_volumes: Deque[float] = deque(maxlen=window_size)
        self.buy_dollars: Deque[float] = deque(maxlen=window_size)
        self.sell_dollars: Deque[float] = deque(maxlen=window_size)

        # Cumulative tracking
        self.cumulative_delta: float = 0.0
        self.tick_count: int = 0

    def process_tick(
        self,
        volume: float,
        price: float,
        is_buy: bool,
    ) -> ImbalanceResult:
        """
        Process a single tick and calculate imbalances.

        Args:
            volume: Tick volume
            price: Tick price
            is_buy: True if classified as buy

        Returns:
            ImbalanceResult with all metrics
        """
        self.tick_count += 1
        dollar_value = volume * price

        # Update cumulative delta
        if is_buy:
            self.cumulative_delta += volume
            self.buy_volumes.append(volume)
            self.sell_volumes.append(0)
            self.buy_dollars.append(dollar_value)
            self.sell_dollars.append(0)
        else:
            self.cumulative_delta -= volume
            self.buy_volumes.append(0)
            self.sell_volumes.append(volume)
            self.buy_dollars.append(0)
            self.sell_dollars.append(dollar_value)

        # Calculate window metrics
        buy_vol = sum(self.buy_volumes)
        sell_vol = sum(self.sell_volumes)
        total_vol = buy_vol + sell_vol

        buy_trades = sum(1 for v in self.buy_volumes if v > 0)
        sell_trades = sum(1 for v in self.sell_volumes if v > 0)
        total_trades = buy_trades + sell_trades

        buy_dollars = sum(self.buy_dollars)
        sell_dollars = sum(self.sell_dollars)
        total_dollars = buy_dollars + sell_dollars

        # Calculate imbalances
        volume_imbalance = (buy_vol - sell_vol) / total_vol if total_vol > 0 else 0
        trade_imbalance = (buy_trades - sell_trades) / total_trades if total_trades > 0 else 0
        dollar_imbalance = (buy_dollars - sell_dollars) / total_dollars if total_dollars > 0 else 0

        # Delta rate (delta per tick in window)
        window_delta = buy_vol - sell_vol
        delta_rate = window_delta / len(self.buy_volumes) if self.buy_volumes else 0

        return ImbalanceResult(
            volume_imbalance=volume_imbalance,
            trade_imbalance=trade_imbalance,
            dollar_imbalance=dollar_imbalance,
            cumulative_delta=self.cumulative_delta,
            delta_rate=delta_rate,
        )

    def get_imbalance_signal(self, result: ImbalanceResult) -> float:
        """
        Convert imbalance metrics to composite signal [-1, 1].

        Weights different imbalance types.
        """
        # Weight volume imbalance most heavily
        signal = (
            0.5 * result.volume_imbalance +
            0.2 * result.trade_imbalance +
            0.3 * result.dollar_imbalance
        )
        return max(-1.0, min(1.0, signal))

    def is_strong_buying_pressure(self, result: ImbalanceResult) -> bool:
        """Check for strong buying pressure (imbalance > 0.5)."""
        return result.volume_imbalance > 0.5 and result.dollar_imbalance > 0.3

    def is_strong_selling_pressure(self, result: ImbalanceResult) -> bool:
        """Check for strong selling pressure (imbalance < -0.5)."""
        return result.volume_imbalance < -0.5 and result.dollar_imbalance < -0.3

    def reset(self) -> None:
        """Reset calculator state."""
        self.buy_volumes.clear()
        self.sell_volumes.clear()
        self.buy_dollars.clear()
        self.sell_dollars.clear()
        self.cumulative_delta = 0.0
        self.tick_count = 0
