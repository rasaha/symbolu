"""
Fibonacci Levels Calculator
===========================

Calculates Fibonacci retracement and extension levels.
Used for price targets and stop-loss placement.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class FibonacciLevels:
    """
    Fibonacci retracement and extension levels.

    Retracements: How far price has pulled back
    Extensions: Potential target levels
    """

    # Reference points
    swing_high: float
    swing_low: float

    # Direction
    is_uptrend: bool

    # Retracement levels (pullback from move)
    ret_236: float  # 23.6% - shallow pullback
    ret_382: float  # 38.2% - moderate pullback
    ret_500: float  # 50.0% - halfway
    ret_618: float  # 61.8% - golden ratio (key level)
    ret_786: float  # 78.6% - deep pullback

    # Extension levels (beyond the move)
    ext_1000: float  # 100% - equal move
    ext_1272: float  # 127.2%
    ext_1618: float  # 161.8% - golden extension
    ext_2000: float  # 200% - double move
    ext_2618: float  # 261.8%

    @property
    def range_size(self) -> float:
        """Size of the swing."""
        return abs(self.swing_high - self.swing_low)

    @property
    def retracement_levels(self) -> List[Tuple[str, float]]:
        """List of retracement levels."""
        return [
            ("23.6%", self.ret_236),
            ("38.2%", self.ret_382),
            ("50.0%", self.ret_500),
            ("61.8%", self.ret_618),
            ("78.6%", self.ret_786),
        ]

    @property
    def extension_levels(self) -> List[Tuple[str, float]]:
        """List of extension levels."""
        return [
            ("100%", self.ext_1000),
            ("127.2%", self.ext_1272),
            ("161.8%", self.ext_1618),
            ("200%", self.ext_2000),
            ("261.8%", self.ext_2618),
        ]

    def get_nearest_level(self, price: float) -> Tuple[str, float, float]:
        """
        Find nearest Fibonacci level to current price.

        Returns: (level_name, level_price, distance)
        """
        all_levels = self.retracement_levels + self.extension_levels
        nearest = min(all_levels, key=lambda x: abs(x[1] - price))
        distance = abs(nearest[1] - price)
        return nearest[0], nearest[1], distance

    def is_at_support(self, price: float, tolerance: float = 0.002) -> bool:
        """Check if price is at a Fibonacci support level."""
        for _, level in self.retracement_levels:
            if abs(price - level) / price < tolerance:
                return True
        return False

    def get_target(self, entry_price: float) -> float:
        """Get suggested target based on entry price."""
        if self.is_uptrend:
            # Long: target is extension
            return self.ext_1618
        else:
            # Short: target is extension (below)
            return self.ext_1618

    def get_stop(self, entry_price: float) -> float:
        """Get suggested stop based on entry price."""
        if self.is_uptrend:
            # Long: stop below 78.6% retracement
            return self.ret_786 * 0.99
        else:
            # Short: stop above 78.6% retracement
            return self.ret_786 * 1.01

    @classmethod
    def calculate(cls, swing_high: float, swing_low: float) -> FibonacciLevels:
        """
        Calculate Fibonacci levels from swing points.

        Args:
            swing_high: Highest point of the swing
            swing_low: Lowest point of the swing

        Returns:
            FibonacciLevels with all calculated levels
        """
        range_size = swing_high - swing_low
        is_uptrend = True  # Assuming we measure from low to high

        # Retracements (from high back toward low)
        ret_236 = swing_high - range_size * 0.236
        ret_382 = swing_high - range_size * 0.382
        ret_500 = swing_high - range_size * 0.500
        ret_618 = swing_high - range_size * 0.618
        ret_786 = swing_high - range_size * 0.786

        # Extensions (beyond the high)
        ext_1000 = swing_low + range_size * 1.000  # = swing_high
        ext_1272 = swing_low + range_size * 1.272
        ext_1618 = swing_low + range_size * 1.618
        ext_2000 = swing_low + range_size * 2.000
        ext_2618 = swing_low + range_size * 2.618

        return cls(
            swing_high=swing_high,
            swing_low=swing_low,
            is_uptrend=is_uptrend,
            ret_236=ret_236,
            ret_382=ret_382,
            ret_500=ret_500,
            ret_618=ret_618,
            ret_786=ret_786,
            ext_1000=ext_1000,
            ext_1272=ext_1272,
            ext_1618=ext_1618,
            ext_2000=ext_2000,
            ext_2618=ext_2618,
        )

    @classmethod
    def calculate_downtrend(cls, swing_high: float, swing_low: float) -> FibonacciLevels:
        """
        Calculate Fibonacci levels for a downtrend.

        Retracements go from low back up toward high.
        Extensions go below the low.
        """
        range_size = swing_high - swing_low

        # Retracements (from low back toward high)
        ret_236 = swing_low + range_size * 0.236
        ret_382 = swing_low + range_size * 0.382
        ret_500 = swing_low + range_size * 0.500
        ret_618 = swing_low + range_size * 0.618
        ret_786 = swing_low + range_size * 0.786

        # Extensions (below the low)
        ext_1000 = swing_high - range_size * 1.000  # = swing_low
        ext_1272 = swing_high - range_size * 1.272
        ext_1618 = swing_high - range_size * 1.618
        ext_2000 = swing_high - range_size * 2.000
        ext_2618 = swing_high - range_size * 2.618

        return cls(
            swing_high=swing_high,
            swing_low=swing_low,
            is_uptrend=False,
            ret_236=ret_236,
            ret_382=ret_382,
            ret_500=ret_500,
            ret_618=ret_618,
            ret_786=ret_786,
            ext_1000=ext_1000,
            ext_1272=ext_1272,
            ext_1618=ext_1618,
            ext_2000=ext_2000,
            ext_2618=ext_2618,
        )
