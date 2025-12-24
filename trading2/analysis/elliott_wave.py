"""
Elliott Wave Analysis Module

Implements Elliott Wave pattern recognition for trading signals.

Elliott Wave Theory:
- Markets move in 5-wave impulse patterns (with trend)
- Followed by 3-wave corrective patterns (against trend)
- Waves relate to each other via Fibonacci ratios

Wave Structure:
    Impulse (5 waves): 1-2-3-4-5
        - Wave 1: Initial move
        - Wave 2: Retracement (38.2%-61.8% of Wave 1)
        - Wave 3: Strongest move (often 161.8% of Wave 1)
        - Wave 4: Retracement (23.6%-50% of Wave 3)
        - Wave 5: Final move (often 61.8%-100% of Wave 1)

    Corrective (3 waves): A-B-C
        - Wave A: Initial correction
        - Wave B: Retracement of A
        - Wave C: Final correction (often equals Wave A)

Fibonacci Ratios:
    0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0, 2.618
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Dict
from collections import deque
import math


class WaveType(Enum):
    """Type of Elliott Wave."""
    IMPULSE_UP = "impulse_up"      # Bullish 5-wave
    IMPULSE_DOWN = "impulse_down"  # Bearish 5-wave
    CORRECTIVE_UP = "corrective_up"    # Bullish ABC
    CORRECTIVE_DOWN = "corrective_down"  # Bearish ABC
    UNKNOWN = "unknown"


class WaveNumber(Enum):
    """Wave position in pattern."""
    WAVE_1 = 1
    WAVE_2 = 2
    WAVE_3 = 3
    WAVE_4 = 4
    WAVE_5 = 5
    WAVE_A = 6
    WAVE_B = 7
    WAVE_C = 8


# Fibonacci levels commonly used in Elliott Wave
FIBONACCI_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786, 1.0, 1.272, 1.618, 2.0, 2.618]


@dataclass(frozen=True)
class FibonacciLevel:
    """A Fibonacci retracement or extension level."""
    ratio: float
    price: float
    level_type: str  # "retracement" or "extension"

    @property
    def percentage(self) -> float:
        return self.ratio * 100


@dataclass
class PivotPoint:
    """
    A significant high or low point in price action.

    Used to identify wave endpoints.
    """
    index: int          # Position in price series
    price: float        # Price at pivot
    is_high: bool       # True for high, False for low
    strength: int = 1   # How many bars confirm this pivot

    @property
    def is_low(self) -> bool:
        return not self.is_high


@dataclass
class WaveSegment:
    """
    A single wave segment between two pivots.

    Represents one leg of an Elliott Wave pattern.
    """
    start_pivot: PivotPoint
    end_pivot: PivotPoint
    wave_number: Optional[WaveNumber] = None

    @property
    def price_change(self) -> float:
        """Absolute price change."""
        return self.end_pivot.price - self.start_pivot.price

    @property
    def price_change_pct(self) -> float:
        """Percentage price change."""
        if self.start_pivot.price == 0:
            return 0.0
        return self.price_change / self.start_pivot.price

    @property
    def is_up(self) -> bool:
        """True if wave moved up."""
        return self.price_change > 0

    @property
    def length(self) -> int:
        """Number of bars in wave."""
        return abs(self.end_pivot.index - self.start_pivot.index)

    def retracement_of(self, previous: "WaveSegment") -> float:
        """
        Calculate retracement ratio relative to previous wave.

        Returns ratio of current wave to previous wave.
        """
        if previous.price_change == 0:
            return 0.0
        return abs(self.price_change / previous.price_change)

    def extension_of(self, reference: "WaveSegment") -> float:
        """
        Calculate extension ratio relative to reference wave.
        """
        if reference.price_change == 0:
            return 0.0
        return abs(self.price_change / reference.price_change)


@dataclass
class WavePattern:
    """
    A complete or partial Elliott Wave pattern.

    Contains the wave segments identified so far and
    pattern classification.
    """
    wave_type: WaveType
    waves: List[WaveSegment] = field(default_factory=list)
    confidence: float = 0.0
    is_complete: bool = False

    @property
    def current_wave_number(self) -> Optional[int]:
        """Current wave position (1-5 or 6-8 for ABC)."""
        if not self.waves:
            return None
        return len(self.waves)

    @property
    def start_price(self) -> Optional[float]:
        """Pattern start price."""
        if not self.waves:
            return None
        return self.waves[0].start_pivot.price

    @property
    def current_price(self) -> Optional[float]:
        """Current pattern price."""
        if not self.waves:
            return None
        return self.waves[-1].end_pivot.price

    @property
    def total_move(self) -> float:
        """Total price movement from pattern start."""
        if not self.waves:
            return 0.0
        return sum(w.price_change for w in self.waves)

    def add_wave(self, wave: WaveSegment) -> None:
        """Add a new wave to the pattern."""
        self.waves.append(wave)

        # Check if pattern is complete
        if self.wave_type in (WaveType.IMPULSE_UP, WaveType.IMPULSE_DOWN):
            self.is_complete = len(self.waves) >= 5
        else:
            self.is_complete = len(self.waves) >= 3


@dataclass
class WaveCount:
    """
    Complete wave count analysis result.

    Contains identified patterns and trading signals.
    """
    patterns: List[WavePattern] = field(default_factory=list)
    current_pattern: Optional[WavePattern] = None
    pivots: List[PivotPoint] = field(default_factory=list)

    # Fibonacci targets
    support_levels: List[FibonacciLevel] = field(default_factory=list)
    resistance_levels: List[FibonacciLevel] = field(default_factory=list)

    # Signal
    signal: float = 0.0  # -1 to +1
    signal_confidence: float = 0.0

    @property
    def trend_direction(self) -> int:
        """1 for bullish, -1 for bearish, 0 for neutral."""
        if self.current_pattern is None:
            return 0
        if self.current_pattern.wave_type == WaveType.IMPULSE_UP:
            return 1
        if self.current_pattern.wave_type == WaveType.IMPULSE_DOWN:
            return -1
        return 0


class ElliottWaveAnalyzer:
    """
    Elliott Wave pattern analyzer.

    Identifies wave patterns from price data and generates
    Fibonacci-based support/resistance levels.
    """

    def __init__(
        self,
        min_wave_size: float = 0.005,
        pivot_lookback: int = 5,
        wave_lookback: int = 100,
    ):
        """
        Initialize analyzer.

        Args:
            min_wave_size: Minimum wave size as fraction of price
            pivot_lookback: Bars to look back for pivot confirmation
            wave_lookback: Maximum bars to consider for wave analysis
        """
        self.min_wave_size = min_wave_size
        self.pivot_lookback = pivot_lookback
        self.wave_lookback = wave_lookback

        # Price history
        self._prices: deque = deque(maxlen=wave_lookback * 2)
        self._highs: deque = deque(maxlen=wave_lookback * 2)
        self._lows: deque = deque(maxlen=wave_lookback * 2)

        # Analysis state
        self._pivots: List[PivotPoint] = []
        self._current_count: Optional[WaveCount] = None

    def process_bar(
        self,
        price: float,
        high: float,
        low: float,
    ) -> WaveCount:
        """
        Process a new price bar and update wave analysis.

        Args:
            price: Close price
            high: High price
            low: Low price

        Returns:
            Updated wave count analysis
        """
        self._prices.append(price)
        self._highs.append(high)
        self._lows.append(low)

        if len(self._prices) < self.pivot_lookback * 2:
            return WaveCount()

        # Detect pivots
        self._update_pivots()

        # Analyze wave structure
        self._current_count = self._analyze_waves()

        return self._current_count

    def process_tick(self, price: float) -> WaveCount:
        """
        Process a tick (simplified - uses price as high/low).

        For tick data, high=low=close.
        """
        return self.process_bar(price, price, price)

    def get_current_count(self) -> WaveCount:
        """Get current wave count analysis."""
        return self._current_count or WaveCount()

    def get_fibonacci_levels(
        self,
        start_price: float,
        end_price: float,
        level_type: str = "retracement",
    ) -> List[FibonacciLevel]:
        """
        Calculate Fibonacci levels between two prices.

        Args:
            start_price: Wave start price
            end_price: Wave end price
            level_type: "retracement" or "extension"

        Returns:
            List of Fibonacci levels
        """
        levels = []
        move = end_price - start_price

        for ratio in FIBONACCI_LEVELS:
            if level_type == "retracement":
                # Retracement from end back toward start
                level_price = end_price - (move * ratio)
            else:
                # Extension beyond end
                level_price = end_price + (move * ratio)

            levels.append(FibonacciLevel(
                ratio=ratio,
                price=level_price,
                level_type=level_type,
            ))

        return levels

    def _update_pivots(self) -> None:
        """Detect and update pivot points."""
        if len(self._highs) < self.pivot_lookback * 2 + 1:
            return

        prices = list(self._prices)
        highs = list(self._highs)
        lows = list(self._lows)

        # Current position (most recent bar that can be confirmed)
        current_idx = len(prices) - self.pivot_lookback - 1

        if current_idx < self.pivot_lookback:
            return

        # Check for pivot high
        is_pivot_high = self._is_pivot_high(highs, current_idx)
        if is_pivot_high:
            pivot = PivotPoint(
                index=current_idx,
                price=highs[current_idx],
                is_high=True,
                strength=self._calculate_pivot_strength(highs, current_idx, True),
            )
            self._add_pivot_if_significant(pivot)

        # Check for pivot low
        is_pivot_low = self._is_pivot_low(lows, current_idx)
        if is_pivot_low:
            pivot = PivotPoint(
                index=current_idx,
                price=lows[current_idx],
                is_high=False,
                strength=self._calculate_pivot_strength(lows, current_idx, False),
            )
            self._add_pivot_if_significant(pivot)

    def _is_pivot_high(self, highs: List[float], idx: int) -> bool:
        """Check if index is a pivot high."""
        current_high = highs[idx]

        # Check bars before
        for i in range(1, self.pivot_lookback + 1):
            if idx - i >= 0 and highs[idx - i] >= current_high:
                return False

        # Check bars after
        for i in range(1, self.pivot_lookback + 1):
            if idx + i < len(highs) and highs[idx + i] >= current_high:
                return False

        return True

    def _is_pivot_low(self, lows: List[float], idx: int) -> bool:
        """Check if index is a pivot low."""
        current_low = lows[idx]

        # Check bars before
        for i in range(1, self.pivot_lookback + 1):
            if idx - i >= 0 and lows[idx - i] <= current_low:
                return False

        # Check bars after
        for i in range(1, self.pivot_lookback + 1):
            if idx + i < len(lows) and lows[idx + i] <= current_low:
                return False

        return True

    def _calculate_pivot_strength(
        self,
        prices: List[float],
        idx: int,
        is_high: bool,
    ) -> int:
        """Calculate how many bars confirm this pivot."""
        strength = 1
        current = prices[idx]

        # Count confirming bars before
        for i in range(1, min(idx + 1, 10)):
            if is_high:
                if prices[idx - i] < current:
                    strength += 1
                else:
                    break
            else:
                if prices[idx - i] > current:
                    strength += 1
                else:
                    break

        return strength

    def _add_pivot_if_significant(self, pivot: PivotPoint) -> None:
        """Add pivot if it represents significant price movement."""
        if not self._pivots:
            self._pivots.append(pivot)
            return

        last_pivot = self._pivots[-1]

        # Skip if same type as last pivot (need alternating)
        if last_pivot.is_high == pivot.is_high:
            # Replace if new pivot is more extreme
            if pivot.is_high and pivot.price > last_pivot.price:
                self._pivots[-1] = pivot
            elif not pivot.is_high and pivot.price < last_pivot.price:
                self._pivots[-1] = pivot
            return

        # Check minimum wave size
        move_pct = abs(pivot.price - last_pivot.price) / last_pivot.price
        if move_pct < self.min_wave_size:
            return

        self._pivots.append(pivot)

        # Limit pivot history
        if len(self._pivots) > 20:
            self._pivots = self._pivots[-20:]

    def _analyze_waves(self) -> WaveCount:
        """Analyze pivot points to identify wave patterns."""
        count = WaveCount(pivots=self._pivots.copy())

        if len(self._pivots) < 3:
            return count

        # Create wave segments from pivots
        segments = []
        for i in range(len(self._pivots) - 1):
            segment = WaveSegment(
                start_pivot=self._pivots[i],
                end_pivot=self._pivots[i + 1],
            )
            segments.append(segment)

        if not segments:
            return count

        # Identify pattern type from initial direction
        first_up = segments[0].is_up

        # Try to match impulse pattern
        pattern = self._match_impulse_pattern(segments, first_up)

        if pattern.confidence > 0.5:
            count.current_pattern = pattern
            count.patterns.append(pattern)

            # Calculate signal from pattern
            count.signal, count.signal_confidence = self._calculate_signal(pattern)

            # Calculate Fibonacci levels
            if len(segments) >= 1:
                first_wave = segments[0]
                count.support_levels = self.get_fibonacci_levels(
                    first_wave.start_pivot.price,
                    first_wave.end_pivot.price,
                    "retracement",
                )
                count.resistance_levels = self.get_fibonacci_levels(
                    first_wave.start_pivot.price,
                    first_wave.end_pivot.price,
                    "extension",
                )

        return count

    def _match_impulse_pattern(
        self,
        segments: List[WaveSegment],
        is_bullish: bool,
    ) -> WavePattern:
        """
        Try to match segments to an impulse wave pattern.

        Rules for valid impulse:
        1. Wave 2 cannot retrace more than 100% of Wave 1
        2. Wave 3 cannot be the shortest impulse wave
        3. Wave 4 cannot overlap Wave 1 territory
        """
        wave_type = WaveType.IMPULSE_UP if is_bullish else WaveType.IMPULSE_DOWN
        pattern = WavePattern(wave_type=wave_type)

        if len(segments) < 2:
            return pattern

        confidence = 0.0
        wave_count = 0

        # Analyze each segment as potential wave
        for i, seg in enumerate(segments[:5]):  # Max 5 waves
            expected_up = is_bullish if (i % 2 == 0) else not is_bullish

            # Check direction matches expected
            if seg.is_up != expected_up:
                break

            # Assign wave number
            seg.wave_number = WaveNumber(i + 1)
            pattern.add_wave(seg)
            wave_count += 1

            # Validate wave relationships
            if i == 1:  # Wave 2
                # Wave 2 should retrace 38.2%-61.8% of Wave 1
                retracement = seg.retracement_of(segments[0])
                if 0.236 <= retracement <= 0.786:
                    confidence += 0.2
                elif retracement > 1.0:
                    # Invalid - Wave 2 exceeds Wave 1
                    break

            if i == 2:  # Wave 3
                # Wave 3 often extends to 161.8% of Wave 1
                extension = seg.extension_of(segments[0])
                if extension >= 1.0:
                    confidence += 0.3
                if extension >= 1.618:
                    confidence += 0.1

            if i == 3:  # Wave 4
                # Wave 4 should retrace 23.6%-50% of Wave 3
                retracement = seg.retracement_of(segments[2])
                if 0.236 <= retracement <= 0.5:
                    confidence += 0.2

                # Wave 4 should not overlap Wave 1
                if is_bullish:
                    if seg.end_pivot.price < segments[0].end_pivot.price:
                        confidence -= 0.3  # Overlap violation
                else:
                    if seg.end_pivot.price > segments[0].end_pivot.price:
                        confidence -= 0.3

            if i == 4:  # Wave 5
                # Wave 5 often equals Wave 1 or extends to 61.8%
                extension = seg.extension_of(segments[0])
                if 0.618 <= extension <= 1.618:
                    confidence += 0.2

        # Bonus for more waves identified
        confidence += wave_count * 0.1

        # Normalize confidence to [0, 1]
        pattern.confidence = max(0.0, min(1.0, confidence))

        return pattern

    def _calculate_signal(self, pattern: WavePattern) -> Tuple[float, float]:
        """
        Calculate trading signal from wave pattern.

        Returns:
            (signal, confidence) where signal is -1 to +1
        """
        if not pattern.waves:
            return 0.0, 0.0

        current_wave = len(pattern.waves)
        is_bullish = pattern.wave_type == WaveType.IMPULSE_UP

        signal = 0.0

        if pattern.wave_type in (WaveType.IMPULSE_UP, WaveType.IMPULSE_DOWN):
            if current_wave == 1:
                # Wave 1 complete - wait for Wave 2 pullback
                signal = 0.3 if is_bullish else -0.3

            elif current_wave == 2:
                # Wave 2 complete - strong entry for Wave 3
                signal = 0.8 if is_bullish else -0.8

            elif current_wave == 3:
                # Wave 3 in progress - trend is strong
                signal = 0.6 if is_bullish else -0.6

            elif current_wave == 4:
                # Wave 4 complete - entry for Wave 5
                signal = 0.5 if is_bullish else -0.5

            elif current_wave >= 5:
                # Wave 5 - trend exhausting, reduce position
                signal = 0.2 if is_bullish else -0.2

        return signal, pattern.confidence

    def reset(self) -> None:
        """Reset analyzer state."""
        self._prices.clear()
        self._highs.clear()
        self._lows.clear()
        self._pivots.clear()
        self._current_count = None
