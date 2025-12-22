"""
Elliott Wave Analysis Integration
=================================

Integrates Elliott Wave Theory with the state evolution system.

Elliott Wave Principles:
1. Impulse waves: 5 waves in trend direction (1-2-3-4-5)
2. Corrective waves: 3 waves against trend (A-B-C)
3. Wave 3 is never the shortest
4. Wave 4 doesn't overlap Wave 1 (in impulse)
5. Fibonacci relationships between waves

Integration with State Evolution:
- Wave position affects momentum/reversion weights
- Wave 3 = highest momentum signal boost
- Wave 5 = potential exhaustion (reduce confidence)
- Corrective waves = favor mean reversion
- Fibonacci levels provide targets/stops
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple, Deque
from collections import deque
import math


class WaveType(Enum):
    """Type of Elliott Wave."""
    IMPULSE_1 = "1"      # First impulse wave
    CORRECTIVE_2 = "2"   # First correction
    IMPULSE_3 = "3"      # Strongest wave (usually)
    CORRECTIVE_4 = "4"   # Second correction
    IMPULSE_5 = "5"      # Final impulse (often exhaustion)
    CORRECTIVE_A = "A"   # First leg of correction
    CORRECTIVE_B = "B"   # Counter-trend bounce
    CORRECTIVE_C = "C"   # Final corrective wave
    UNKNOWN = "?"


class WaveDegree(Enum):
    """Degree/timeframe of wave."""
    SUBMINUETTE = "subminuette"  # Minutes
    MINUETTE = "minuette"        # Hours
    MINUTE = "minute"            # Days
    MINOR = "minor"              # Weeks
    INTERMEDIATE = "intermediate"  # Months
    PRIMARY = "primary"          # Years


@dataclass
class WaveCount:
    """
    Current Elliott Wave count.

    Represents where we are in the wave structure.
    """
    wave_type: WaveType
    degree: WaveDegree
    direction: int  # 1 = bullish trend, -1 = bearish trend

    # Wave boundaries
    wave_start_price: float = 0.0
    wave_start_tick: int = 0
    wave_high: float = 0.0
    wave_low: float = 0.0

    # Context
    in_impulse: bool = True  # vs corrective
    completed_waves: int = 0  # How many waves completed in current sequence

    # Fibonacci projections
    target_0618: float = 0.0  # 61.8% extension
    target_1000: float = 0.0  # 100% extension
    target_1618: float = 0.0  # 161.8% extension

    @property
    def is_impulse(self) -> bool:
        """Check if currently in impulse wave."""
        return self.wave_type in (
            WaveType.IMPULSE_1,
            WaveType.IMPULSE_3,
            WaveType.IMPULSE_5,
        )

    @property
    def is_corrective(self) -> bool:
        """Check if currently in corrective wave."""
        return self.wave_type in (
            WaveType.CORRECTIVE_2,
            WaveType.CORRECTIVE_4,
            WaveType.CORRECTIVE_A,
            WaveType.CORRECTIVE_B,
            WaveType.CORRECTIVE_C,
        )

    @property
    def wave_strength(self) -> float:
        """
        Expected strength of current wave (0-1).

        Wave 3 is strongest, Wave 5/B often weakest.
        """
        strengths = {
            WaveType.IMPULSE_1: 0.6,
            WaveType.CORRECTIVE_2: 0.4,
            WaveType.IMPULSE_3: 1.0,   # Strongest
            WaveType.CORRECTIVE_4: 0.3,
            WaveType.IMPULSE_5: 0.5,   # Often exhaustion
            WaveType.CORRECTIVE_A: 0.6,
            WaveType.CORRECTIVE_B: 0.3,  # Weakest
            WaveType.CORRECTIVE_C: 0.7,
            WaveType.UNKNOWN: 0.5,
        }
        return strengths.get(self.wave_type, 0.5)

    @property
    def momentum_bias(self) -> float:
        """
        Momentum bias based on wave position (-1 to 1).

        Impulse waves = positive momentum bias
        Corrective waves = negative (mean reversion) bias
        """
        if self.wave_type in (WaveType.IMPULSE_1, WaveType.IMPULSE_3, WaveType.IMPULSE_5):
            return self.direction * self.wave_strength
        elif self.wave_type in (WaveType.CORRECTIVE_A, WaveType.CORRECTIVE_C):
            return -self.direction * 0.5  # Counter-trend
        elif self.wave_type in (WaveType.CORRECTIVE_2, WaveType.CORRECTIVE_4, WaveType.CORRECTIVE_B):
            return 0  # Sideways/uncertain
        return 0


@dataclass
class ElliottSignal:
    """
    Signal derived from Elliott Wave analysis.

    Combines wave position with state evolution signals.
    """
    wave_count: WaveCount

    # Signal adjustments
    momentum_adjustment: float  # [-0.3, 0.3] adjustment to momentum weight
    reversion_adjustment: float  # [-0.3, 0.3] adjustment to reversion weight
    confidence_adjustment: float  # [-20, 20] adjustment to confidence %

    # Targets
    target_price: float  # Fibonacci target
    stop_price: float    # Fibonacci stop

    # Recommendation
    wave_aligned: bool   # True if signal aligns with wave direction
    exhaustion_warning: bool  # True if in wave 5 or C (potential reversal)

    def adjust_signal_score(
        self,
        bullish_prob: float,
        bearish_prob: float,
        confidence: float,
    ) -> Tuple[float, float, float]:
        """
        Adjust signal scores based on Elliott Wave context.

        Returns adjusted (bullish_prob, bearish_prob, confidence).
        """
        # Momentum adjustment affects directional probability
        if self.wave_count.direction > 0:
            # Bullish trend
            bullish_adj = bullish_prob + self.momentum_adjustment * 10
            bearish_adj = bearish_prob - self.momentum_adjustment * 10
        else:
            # Bearish trend
            bearish_adj = bearish_prob + self.momentum_adjustment * 10
            bullish_adj = bullish_prob - self.momentum_adjustment * 10

        # Exhaustion warning reduces confidence
        conf_adj = confidence + self.confidence_adjustment
        if self.exhaustion_warning:
            conf_adj -= 10

        # Alignment bonus
        if self.wave_aligned:
            conf_adj += 5

        # Bound values
        bullish_adj = max(5, min(95, bullish_adj))
        bearish_adj = max(5, min(95, bearish_adj))
        conf_adj = max(0, min(100, conf_adj))

        return bullish_adj, bearish_adj, conf_adj


class ElliottWaveAnalyzer:
    """
    Elliott Wave pattern analyzer.

    Identifies wave patterns from price action and provides
    signals for integration with state evolution.

    Note: Elliott Wave analysis is subjective. This implementation
    uses simplified heuristics for automated detection.
    """

    # Fibonacci ratios
    FIB_236 = 0.236
    FIB_382 = 0.382
    FIB_500 = 0.500
    FIB_618 = 0.618
    FIB_786 = 0.786
    FIB_1000 = 1.000
    FIB_1272 = 1.272
    FIB_1618 = 1.618
    FIB_2618 = 2.618

    def __init__(
        self,
        lookback_ticks: int = 500,
        min_wave_ticks: int = 20,
        degree: WaveDegree = WaveDegree.MINUETTE,
    ):
        """
        Initialize analyzer.

        Args:
            lookback_ticks: Number of ticks to analyze
            min_wave_ticks: Minimum ticks to consider a wave
            degree: Wave degree for this timeframe
        """
        self.lookback_ticks = lookback_ticks
        self.min_wave_ticks = min_wave_ticks
        self.degree = degree

        # Price history
        self.prices: Deque[float] = deque(maxlen=lookback_ticks)
        self.highs: Deque[float] = deque(maxlen=lookback_ticks)
        self.lows: Deque[float] = deque(maxlen=lookback_ticks)

        # Pivot points (swing highs/lows)
        self.pivots: List[Tuple[int, float, str]] = []  # (tick, price, "H"/"L")

        # Current wave count
        self.current_wave = WaveCount(
            wave_type=WaveType.UNKNOWN,
            degree=degree,
            direction=1,
        )

        # State
        self.tick_count = 0

    def process_tick(
        self,
        price: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
    ) -> WaveCount:
        """
        Process a price tick and update wave count.

        Args:
            price: Current price
            high: High for this tick (optional)
            low: Low for this tick (optional)

        Returns:
            Current wave count
        """
        self.tick_count += 1
        self.prices.append(price)
        self.highs.append(high or price)
        self.lows.append(low or price)

        # Detect pivot points
        self._detect_pivots()

        # Update wave count
        if len(self.pivots) >= 3:
            self._update_wave_count()

        return self.current_wave

    def _detect_pivots(self, lookback: int = 10) -> None:
        """Detect swing high/low pivot points."""
        if len(self.prices) < lookback * 2 + 1:
            return

        prices = list(self.prices)
        idx = len(prices) - lookback - 1

        # Check for swing high
        is_swing_high = all(
            prices[idx] >= prices[idx + i] and prices[idx] >= prices[idx - i]
            for i in range(1, lookback + 1)
            if idx + i < len(prices) and idx - i >= 0
        )

        # Check for swing low
        is_swing_low = all(
            prices[idx] <= prices[idx + i] and prices[idx] <= prices[idx - i]
            for i in range(1, lookback + 1)
            if idx + i < len(prices) and idx - i >= 0
        )

        tick_num = self.tick_count - lookback

        if is_swing_high:
            # Avoid duplicate pivots
            if not self.pivots or self.pivots[-1][2] != "H":
                self.pivots.append((tick_num, prices[idx], "H"))
        elif is_swing_low:
            if not self.pivots or self.pivots[-1][2] != "L":
                self.pivots.append((tick_num, prices[idx], "L"))

        # Limit pivot history
        if len(self.pivots) > 20:
            self.pivots = self.pivots[-15:]

    def _update_wave_count(self) -> None:
        """Update wave count based on pivot structure."""
        if len(self.pivots) < 3:
            return

        # Analyze recent pivots
        recent_pivots = self.pivots[-5:]

        # Determine trend direction from pivots
        highs = [p[1] for p in recent_pivots if p[2] == "H"]
        lows = [p[1] for p in recent_pivots if p[2] == "L"]

        if len(highs) >= 2 and len(lows) >= 2:
            higher_highs = highs[-1] > highs[0]
            higher_lows = lows[-1] > lows[0]
            lower_highs = highs[-1] < highs[0]
            lower_lows = lows[-1] < lows[0]

            if higher_highs and higher_lows:
                direction = 1  # Uptrend
            elif lower_highs and lower_lows:
                direction = -1  # Downtrend
            else:
                direction = self.current_wave.direction  # Keep current

            self.current_wave = WaveCount(
                wave_type=self._identify_wave_type(recent_pivots, direction),
                degree=self.degree,
                direction=direction,
                wave_start_price=recent_pivots[-1][1],
                wave_start_tick=recent_pivots[-1][0],
                wave_high=max(self.prices) if self.prices else 0,
                wave_low=min(self.prices) if self.prices else 0,
            )

            # Calculate Fibonacci targets
            self._calculate_fib_targets()

    def _identify_wave_type(
        self,
        pivots: List[Tuple[int, float, str]],
        direction: int,
    ) -> WaveType:
        """
        Identify current wave type based on pivot pattern.

        Simplified heuristic approach.
        """
        if len(pivots) < 3:
            return WaveType.UNKNOWN

        # Count alternating pivots
        alternations = 0
        for i in range(1, len(pivots)):
            if pivots[i][2] != pivots[i-1][2]:
                alternations += 1

        # Measure wave sizes
        if len(pivots) >= 4:
            wave_sizes = []
            for i in range(1, len(pivots)):
                wave_sizes.append(abs(pivots[i][1] - pivots[i-1][1]))

            # Wave 3 is typically largest
            if len(wave_sizes) >= 3:
                max_wave_idx = wave_sizes.index(max(wave_sizes))
                if max_wave_idx == 2:  # Third wave is largest
                    if alternations >= 4:
                        return WaveType.IMPULSE_5  # Completing 5-wave
                    else:
                        return WaveType.CORRECTIVE_4  # After wave 3
                elif max_wave_idx == 1:
                    return WaveType.IMPULSE_3  # In wave 3
                elif alternations >= 2:
                    return WaveType.IMPULSE_3  # Building wave 3

        # Default based on alternation count
        wave_sequence = [
            WaveType.IMPULSE_1,
            WaveType.CORRECTIVE_2,
            WaveType.IMPULSE_3,
            WaveType.CORRECTIVE_4,
            WaveType.IMPULSE_5,
        ]

        if alternations < len(wave_sequence):
            return wave_sequence[alternations]

        # Likely in correction after 5 waves
        correction_sequence = [
            WaveType.CORRECTIVE_A,
            WaveType.CORRECTIVE_B,
            WaveType.CORRECTIVE_C,
        ]
        corr_idx = (alternations - 5) % 3
        return correction_sequence[corr_idx]

    def _calculate_fib_targets(self) -> None:
        """Calculate Fibonacci extension targets."""
        if len(self.pivots) < 2:
            return

        # Use last two pivots for extension
        p1 = self.pivots[-2][1]
        p2 = self.pivots[-1][1]
        wave_size = abs(p2 - p1)

        direction = self.current_wave.direction

        if direction > 0:
            # Bullish targets (extensions up)
            self.current_wave = WaveCount(
                wave_type=self.current_wave.wave_type,
                degree=self.current_wave.degree,
                direction=direction,
                wave_start_price=p2,
                wave_start_tick=self.pivots[-1][0],
                wave_high=self.current_wave.wave_high,
                wave_low=self.current_wave.wave_low,
                target_0618=p2 + wave_size * self.FIB_618,
                target_1000=p2 + wave_size * self.FIB_1000,
                target_1618=p2 + wave_size * self.FIB_1618,
            )
        else:
            # Bearish targets (extensions down)
            self.current_wave = WaveCount(
                wave_type=self.current_wave.wave_type,
                degree=self.current_wave.degree,
                direction=direction,
                wave_start_price=p2,
                wave_start_tick=self.pivots[-1][0],
                wave_high=self.current_wave.wave_high,
                wave_low=self.current_wave.wave_low,
                target_0618=p2 - wave_size * self.FIB_618,
                target_1000=p2 - wave_size * self.FIB_1000,
                target_1618=p2 - wave_size * self.FIB_1618,
            )

    def get_signal(
        self,
        current_price: float,
        base_signal: float,
    ) -> ElliottSignal:
        """
        Generate Elliott Wave signal for integration.

        Args:
            current_price: Current price
            base_signal: Base signal from state evolution [-1, 1]

        Returns:
            ElliottSignal with adjustments
        """
        wave = self.current_wave

        # Momentum adjustment based on wave position
        if wave.wave_type == WaveType.IMPULSE_3:
            # Wave 3: strongest momentum
            momentum_adj = 0.25 * wave.direction
            confidence_adj = 15.0
        elif wave.wave_type == WaveType.IMPULSE_1:
            # Wave 1: building momentum
            momentum_adj = 0.15 * wave.direction
            confidence_adj = 5.0
        elif wave.wave_type in (WaveType.CORRECTIVE_2, WaveType.CORRECTIVE_4):
            # Corrections: favor reversion
            momentum_adj = -0.1 * wave.direction
            confidence_adj = -5.0
        elif wave.wave_type == WaveType.IMPULSE_5:
            # Wave 5: potential exhaustion
            momentum_adj = 0.05 * wave.direction
            confidence_adj = -10.0  # Lower confidence
        elif wave.wave_type in (WaveType.CORRECTIVE_A, WaveType.CORRECTIVE_C):
            # Corrective impulse waves
            momentum_adj = -0.15 * wave.direction
            confidence_adj = 0.0
        else:
            momentum_adj = 0.0
            confidence_adj = 0.0

        # Reversion adjustment (inverse of momentum)
        reversion_adj = -momentum_adj * 0.5

        # Check alignment
        signal_direction = 1 if base_signal > 0 else -1
        wave_aligned = signal_direction == wave.direction

        # Exhaustion warning
        exhaustion_warning = wave.wave_type in (
            WaveType.IMPULSE_5,
            WaveType.CORRECTIVE_C,
            WaveType.CORRECTIVE_B,
        )

        # Calculate targets and stops
        if wave.direction > 0:
            target_price = wave.target_1000  # 100% extension
            stop_price = wave.wave_low * 0.99  # Below recent low
        else:
            target_price = wave.target_1000
            stop_price = wave.wave_high * 1.01  # Above recent high

        return ElliottSignal(
            wave_count=wave,
            momentum_adjustment=momentum_adj,
            reversion_adjustment=reversion_adj,
            confidence_adjustment=confidence_adj,
            target_price=target_price,
            stop_price=stop_price,
            wave_aligned=wave_aligned,
            exhaustion_warning=exhaustion_warning,
        )

    def get_state_adjustments(self) -> dict:
        """
        Get suggested state adjustments based on wave position.

        Returns dict with suggested weight adjustments.
        """
        wave = self.current_wave

        if wave.wave_type == WaveType.IMPULSE_3:
            return {
                "w_momentum_target": 0.6,  # Boost momentum
                "w_reversion_target": 0.25,
                "w_noise_target": 0.15,
                "alpha_multiplier": 1.2,  # Faster adaptation
            }
        elif wave.wave_type in (WaveType.CORRECTIVE_2, WaveType.CORRECTIVE_4):
            return {
                "w_momentum_target": 0.25,
                "w_reversion_target": 0.55,  # Boost reversion
                "w_noise_target": 0.20,
                "alpha_multiplier": 0.8,  # Slower adaptation
            }
        elif wave.wave_type == WaveType.IMPULSE_5:
            return {
                "w_momentum_target": 0.35,
                "w_reversion_target": 0.35,
                "w_noise_target": 0.30,  # More filtering
                "alpha_multiplier": 0.7,  # Conservative
            }
        else:
            return {
                "w_momentum_target": 0.4,
                "w_reversion_target": 0.4,
                "w_noise_target": 0.2,
                "alpha_multiplier": 1.0,
            }
