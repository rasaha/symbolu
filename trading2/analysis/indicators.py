"""
Professional Trading Indicators

Industry-standard technical indicators used by professional trading desks:
- ADX (Average Directional Index) - Trend strength
- RSI (Relative Strength Index) - Momentum oscillator
- MACD (Moving Average Convergence Divergence) - Trend & momentum
- Bollinger Bands - Volatility & mean reversion
- ATR (Average True Range) - Volatility measure
- Stochastic - Momentum oscillator
- OBV (On-Balance Volume) - Volume-based momentum

These indicators generate probabilistic buy/sell signals.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from collections import deque
from enum import Enum
import math


class SignalType(Enum):
    """Trading signal types."""
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


@dataclass
class IndicatorSignal:
    """Signal from a single indicator."""
    name: str
    value: float
    signal: SignalType
    strength: float  # 0-1, confidence in signal
    description: str = ""


@dataclass
class CompositeSignal:
    """Combined signal from multiple indicators."""
    signals: List[IndicatorSignal] = field(default_factory=list)

    @property
    def buy_score(self) -> float:
        """Aggregate buy score [0, 1]."""
        buy_signals = [s for s in self.signals
                      if s.signal in (SignalType.BUY, SignalType.STRONG_BUY)]
        if not buy_signals:
            return 0.0
        weights = [s.strength * (1.5 if s.signal == SignalType.STRONG_BUY else 1.0)
                  for s in buy_signals]
        return min(1.0, sum(weights) / len(self.signals))

    @property
    def sell_score(self) -> float:
        """Aggregate sell score [0, 1]."""
        sell_signals = [s for s in self.signals
                       if s.signal in (SignalType.SELL, SignalType.STRONG_SELL)]
        if not sell_signals:
            return 0.0
        weights = [s.strength * (1.5 if s.signal == SignalType.STRONG_SELL else 1.0)
                  for s in sell_signals]
        return min(1.0, sum(weights) / len(self.signals))

    @property
    def net_signal(self) -> float:
        """Net signal [-1, 1]. Positive = buy, negative = sell."""
        return self.buy_score - self.sell_score

    @property
    def consensus(self) -> SignalType:
        """Overall consensus signal."""
        net = self.net_signal
        if net > 0.5:
            return SignalType.STRONG_BUY
        elif net > 0.2:
            return SignalType.BUY
        elif net < -0.5:
            return SignalType.STRONG_SELL
        elif net < -0.2:
            return SignalType.SELL
        return SignalType.NEUTRAL

    @property
    def confidence(self) -> float:
        """Confidence in consensus [0, 1]."""
        if not self.signals:
            return 0.0

        # Higher when indicators agree
        signal_types = [s.signal for s in self.signals]
        most_common = max(set(signal_types), key=signal_types.count)
        agreement = signal_types.count(most_common) / len(signal_types)

        # Weight by individual strengths
        avg_strength = sum(s.strength for s in self.signals) / len(self.signals)

        return agreement * avg_strength


class ADX:
    """
    Average Directional Index - measures trend strength.

    Interpretation:
        < 20: Weak trend (ranging market)
        20-25: Trend emerging
        25-50: Strong trend
        50-75: Very strong trend
        > 75: Extremely strong trend

    +DI > -DI: Bullish trend
    -DI > +DI: Bearish trend
    """

    def __init__(self, period: int = 14):
        self.period = period
        self._highs: deque = deque(maxlen=period + 1)
        self._lows: deque = deque(maxlen=period + 1)
        self._closes: deque = deque(maxlen=period + 1)

        self._tr_values: deque = deque(maxlen=period)
        self._plus_dm: deque = deque(maxlen=period)
        self._minus_dm: deque = deque(maxlen=period)
        self._dx_values: deque = deque(maxlen=period)

        self.adx: float = 0.0
        self.plus_di: float = 0.0
        self.minus_di: float = 0.0

    def update(self, high: float, low: float, close: float) -> Optional[IndicatorSignal]:
        """Update ADX with new bar."""
        self._highs.append(high)
        self._lows.append(low)
        self._closes.append(close)

        if len(self._highs) < 2:
            return None

        # Calculate True Range
        prev_close = self._closes[-2]
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        self._tr_values.append(tr)

        # Calculate Directional Movement
        prev_high = self._highs[-2]
        prev_low = self._lows[-2]

        up_move = high - prev_high
        down_move = prev_low - low

        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0

        self._plus_dm.append(plus_dm)
        self._minus_dm.append(minus_dm)

        if len(self._tr_values) < self.period:
            return None

        # Smoothed averages
        atr = sum(self._tr_values) / self.period
        plus_dm_avg = sum(self._plus_dm) / self.period
        minus_dm_avg = sum(self._minus_dm) / self.period

        # Directional Indicators
        if atr > 0:
            self.plus_di = 100 * plus_dm_avg / atr
            self.minus_di = 100 * minus_dm_avg / atr

        # DX and ADX
        di_sum = self.plus_di + self.minus_di
        if di_sum > 0:
            dx = 100 * abs(self.plus_di - self.minus_di) / di_sum
            self._dx_values.append(dx)

            if len(self._dx_values) >= self.period:
                self.adx = sum(self._dx_values) / len(self._dx_values)

        return self._generate_signal()

    def _generate_signal(self) -> IndicatorSignal:
        """Generate trading signal from ADX."""
        signal = SignalType.NEUTRAL
        strength = 0.0
        description = ""

        # Trend strength
        if self.adx < 20:
            description = "No trend (ranging)"
            strength = 0.3
        elif self.adx < 25:
            description = "Weak trend emerging"
            strength = 0.5
        elif self.adx < 50:
            description = "Strong trend"
            strength = 0.7
        elif self.adx < 75:
            description = "Very strong trend"
            strength = 0.85
        else:
            description = "Extremely strong trend"
            strength = 0.95

        # Direction from DI crossover
        if self.adx >= 20:  # Only signal when trend exists
            if self.plus_di > self.minus_di:
                if self.adx >= 25:
                    signal = SignalType.STRONG_BUY
                else:
                    signal = SignalType.BUY
                description += " - Bullish"
            elif self.minus_di > self.plus_di:
                if self.adx >= 25:
                    signal = SignalType.STRONG_SELL
                else:
                    signal = SignalType.SELL
                description += " - Bearish"

        return IndicatorSignal(
            name="ADX",
            value=self.adx,
            signal=signal,
            strength=strength,
            description=description,
        )


class RSI:
    """
    Relative Strength Index - momentum oscillator.

    Interpretation:
        > 70: Overbought (potential sell)
        < 30: Oversold (potential buy)
        50: Neutral

    Divergences with price indicate potential reversals.
    """

    def __init__(self, period: int = 14):
        self.period = period
        self._prices: deque = deque(maxlen=period + 1)
        self._gains: deque = deque(maxlen=period)
        self._losses: deque = deque(maxlen=period)

        self.rsi: float = 50.0
        self._avg_gain: float = 0.0
        self._avg_loss: float = 0.0

    def update(self, price: float) -> Optional[IndicatorSignal]:
        """Update RSI with new price."""
        self._prices.append(price)

        if len(self._prices) < 2:
            return None

        change = price - self._prices[-2]
        gain = max(0, change)
        loss = max(0, -change)

        self._gains.append(gain)
        self._losses.append(loss)

        if len(self._gains) < self.period:
            return None

        # Calculate RSI using Wilder's smoothing
        if self._avg_gain == 0 and self._avg_loss == 0:
            self._avg_gain = sum(self._gains) / self.period
            self._avg_loss = sum(self._losses) / self.period
        else:
            self._avg_gain = (self._avg_gain * (self.period - 1) + gain) / self.period
            self._avg_loss = (self._avg_loss * (self.period - 1) + loss) / self.period

        if self._avg_loss == 0:
            self.rsi = 100.0
        else:
            rs = self._avg_gain / self._avg_loss
            self.rsi = 100 - (100 / (1 + rs))

        return self._generate_signal()

    def _generate_signal(self) -> IndicatorSignal:
        """Generate trading signal from RSI."""
        signal = SignalType.NEUTRAL
        strength = 0.5
        description = ""

        if self.rsi >= 80:
            signal = SignalType.STRONG_SELL
            strength = 0.9
            description = "Extremely overbought"
        elif self.rsi >= 70:
            signal = SignalType.SELL
            strength = 0.7
            description = "Overbought"
        elif self.rsi <= 20:
            signal = SignalType.STRONG_BUY
            strength = 0.9
            description = "Extremely oversold"
        elif self.rsi <= 30:
            signal = SignalType.BUY
            strength = 0.7
            description = "Oversold"
        elif 45 <= self.rsi <= 55:
            description = "Neutral momentum"
            strength = 0.3
        elif self.rsi > 55:
            signal = SignalType.BUY
            strength = 0.4
            description = "Bullish momentum"
        else:
            signal = SignalType.SELL
            strength = 0.4
            description = "Bearish momentum"

        return IndicatorSignal(
            name="RSI",
            value=self.rsi,
            signal=signal,
            strength=strength,
            description=description,
        )


class MACD:
    """
    Moving Average Convergence Divergence.

    Components:
        MACD Line: Fast EMA - Slow EMA
        Signal Line: EMA of MACD Line
        Histogram: MACD Line - Signal Line

    Signals:
        - MACD crosses above signal: Buy
        - MACD crosses below signal: Sell
        - Histogram increasing: Strengthening momentum
        - Divergence with price: Potential reversal
    """

    def __init__(
        self,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period

        self._prices: deque = deque(maxlen=slow_period + signal_period)

        self._fast_ema: float = 0.0
        self._slow_ema: float = 0.0
        self._signal_ema: float = 0.0

        self._fast_mult = 2 / (fast_period + 1)
        self._slow_mult = 2 / (slow_period + 1)
        self._signal_mult = 2 / (signal_period + 1)

        self.macd_line: float = 0.0
        self.signal_line: float = 0.0
        self.histogram: float = 0.0
        self._prev_histogram: float = 0.0
        self._initialized: bool = False

    def update(self, price: float) -> Optional[IndicatorSignal]:
        """Update MACD with new price."""
        self._prices.append(price)

        if len(self._prices) < self.slow_period:
            return None

        if not self._initialized:
            # Initialize EMAs with SMA
            self._fast_ema = sum(list(self._prices)[-self.fast_period:]) / self.fast_period
            self._slow_ema = sum(self._prices) / self.slow_period
            self._initialized = True
        else:
            # Update EMAs
            self._fast_ema = (price - self._fast_ema) * self._fast_mult + self._fast_ema
            self._slow_ema = (price - self._slow_ema) * self._slow_mult + self._slow_ema

        self._prev_histogram = self.histogram
        self.macd_line = self._fast_ema - self._slow_ema

        # Update signal line
        if self._signal_ema == 0:
            self._signal_ema = self.macd_line
        else:
            self._signal_ema = (self.macd_line - self._signal_ema) * self._signal_mult + self._signal_ema

        self.signal_line = self._signal_ema
        self.histogram = self.macd_line - self.signal_line

        return self._generate_signal()

    def _generate_signal(self) -> IndicatorSignal:
        """Generate trading signal from MACD."""
        signal = SignalType.NEUTRAL
        strength = 0.5
        description = ""

        # Crossover detection
        crossed_above = self._prev_histogram <= 0 and self.histogram > 0
        crossed_below = self._prev_histogram >= 0 and self.histogram < 0

        if crossed_above:
            signal = SignalType.STRONG_BUY
            strength = 0.85
            description = "Bullish crossover"
        elif crossed_below:
            signal = SignalType.STRONG_SELL
            strength = 0.85
            description = "Bearish crossover"
        elif self.histogram > 0:
            if self.histogram > self._prev_histogram:
                signal = SignalType.BUY
                strength = 0.6
                description = "Bullish momentum increasing"
            else:
                signal = SignalType.BUY
                strength = 0.4
                description = "Bullish momentum weakening"
        elif self.histogram < 0:
            if self.histogram < self._prev_histogram:
                signal = SignalType.SELL
                strength = 0.6
                description = "Bearish momentum increasing"
            else:
                signal = SignalType.SELL
                strength = 0.4
                description = "Bearish momentum weakening"
        else:
            description = "Neutral"
            strength = 0.3

        return IndicatorSignal(
            name="MACD",
            value=self.histogram,
            signal=signal,
            strength=strength,
            description=description,
        )


class BollingerBands:
    """
    Bollinger Bands - volatility and mean reversion indicator.

    Components:
        Middle Band: SMA
        Upper Band: SMA + (std * multiplier)
        Lower Band: SMA - (std * multiplier)

    Signals:
        - Price at lower band: Potential buy (oversold)
        - Price at upper band: Potential sell (overbought)
        - Band squeeze: Volatility contraction, breakout expected
        - Band expansion: Volatility expansion, trend confirmation
    """

    def __init__(self, period: int = 20, std_multiplier: float = 2.0):
        self.period = period
        self.std_multiplier = std_multiplier

        self._prices: deque = deque(maxlen=period)

        self.middle_band: float = 0.0
        self.upper_band: float = 0.0
        self.lower_band: float = 0.0
        self.bandwidth: float = 0.0
        self.percent_b: float = 0.5  # Position within bands

    def update(self, price: float) -> Optional[IndicatorSignal]:
        """Update Bollinger Bands with new price."""
        self._prices.append(price)

        if len(self._prices) < self.period:
            return None

        prices = list(self._prices)

        # Calculate bands
        self.middle_band = sum(prices) / self.period
        variance = sum((p - self.middle_band) ** 2 for p in prices) / self.period
        std = math.sqrt(variance)

        self.upper_band = self.middle_band + (std * self.std_multiplier)
        self.lower_band = self.middle_band - (std * self.std_multiplier)

        # Bandwidth (volatility measure)
        if self.middle_band > 0:
            self.bandwidth = (self.upper_band - self.lower_band) / self.middle_band

        # %B (position within bands)
        band_range = self.upper_band - self.lower_band
        if band_range > 0:
            self.percent_b = (price - self.lower_band) / band_range

        return self._generate_signal(price)

    def _generate_signal(self, price: float) -> IndicatorSignal:
        """Generate trading signal from Bollinger Bands."""
        signal = SignalType.NEUTRAL
        strength = 0.5
        description = ""

        if self.percent_b <= 0:
            signal = SignalType.STRONG_BUY
            strength = 0.85
            description = "Below lower band - oversold"
        elif self.percent_b < 0.2:
            signal = SignalType.BUY
            strength = 0.7
            description = "Near lower band"
        elif self.percent_b >= 1.0:
            signal = SignalType.STRONG_SELL
            strength = 0.85
            description = "Above upper band - overbought"
        elif self.percent_b > 0.8:
            signal = SignalType.SELL
            strength = 0.7
            description = "Near upper band"
        elif 0.4 <= self.percent_b <= 0.6:
            description = "Near middle band - neutral"
            strength = 0.3
        elif self.percent_b > 0.5:
            signal = SignalType.BUY
            strength = 0.4
            description = "Upper half of bands"
        else:
            signal = SignalType.SELL
            strength = 0.4
            description = "Lower half of bands"

        # Adjust for bandwidth (volatility)
        if self.bandwidth < 0.02:  # Squeeze
            description += " (squeeze - breakout expected)"
            strength *= 1.2

        return IndicatorSignal(
            name="Bollinger",
            value=self.percent_b,
            signal=signal,
            strength=min(1.0, strength),
            description=description,
        )


class Stochastic:
    """
    Stochastic Oscillator - momentum indicator.

    Components:
        %K: (Current - Lowest Low) / (Highest High - Lowest Low) * 100
        %D: SMA of %K

    Signals:
        > 80: Overbought
        < 20: Oversold
        %K crosses %D: Buy/Sell signal
    """

    def __init__(self, k_period: int = 14, d_period: int = 3):
        self.k_period = k_period
        self.d_period = d_period

        self._highs: deque = deque(maxlen=k_period)
        self._lows: deque = deque(maxlen=k_period)
        self._k_values: deque = deque(maxlen=d_period)

        self.k: float = 50.0
        self.d: float = 50.0
        self._prev_k: float = 50.0
        self._prev_d: float = 50.0

    def update(self, high: float, low: float, close: float) -> Optional[IndicatorSignal]:
        """Update Stochastic with new bar."""
        self._highs.append(high)
        self._lows.append(low)

        if len(self._highs) < self.k_period:
            return None

        highest_high = max(self._highs)
        lowest_low = min(self._lows)

        self._prev_k = self.k
        self._prev_d = self.d

        range_hl = highest_high - lowest_low
        if range_hl > 0:
            self.k = ((close - lowest_low) / range_hl) * 100
        else:
            self.k = 50.0

        self._k_values.append(self.k)

        if len(self._k_values) >= self.d_period:
            self.d = sum(self._k_values) / len(self._k_values)

        return self._generate_signal()

    def _generate_signal(self) -> IndicatorSignal:
        """Generate trading signal from Stochastic."""
        signal = SignalType.NEUTRAL
        strength = 0.5
        description = ""

        # Crossover detection
        crossed_above = self._prev_k <= self._prev_d and self.k > self.d
        crossed_below = self._prev_k >= self._prev_d and self.k < self.d

        if self.k <= 20:
            if crossed_above:
                signal = SignalType.STRONG_BUY
                strength = 0.9
                description = "Bullish crossover in oversold zone"
            else:
                signal = SignalType.BUY
                strength = 0.7
                description = "Oversold"
        elif self.k >= 80:
            if crossed_below:
                signal = SignalType.STRONG_SELL
                strength = 0.9
                description = "Bearish crossover in overbought zone"
            else:
                signal = SignalType.SELL
                strength = 0.7
                description = "Overbought"
        elif crossed_above:
            signal = SignalType.BUY
            strength = 0.6
            description = "Bullish crossover"
        elif crossed_below:
            signal = SignalType.SELL
            strength = 0.6
            description = "Bearish crossover"
        else:
            description = "No clear signal"
            strength = 0.3

        return IndicatorSignal(
            name="Stochastic",
            value=self.k,
            signal=signal,
            strength=strength,
            description=description,
        )


class ATR:
    """
    Average True Range - volatility indicator.

    Used for:
        - Position sizing
        - Stop loss placement
        - Volatility regime detection
    """

    def __init__(self, period: int = 14):
        self.period = period
        self._tr_values: deque = deque(maxlen=period)
        self._prev_close: Optional[float] = None

        self.atr: float = 0.0
        self.atr_percent: float = 0.0  # ATR as % of price

    def update(self, high: float, low: float, close: float) -> float:
        """Update ATR with new bar. Returns current ATR."""
        if self._prev_close is not None:
            tr = max(
                high - low,
                abs(high - self._prev_close),
                abs(low - self._prev_close)
            )
        else:
            tr = high - low

        self._tr_values.append(tr)
        self._prev_close = close

        if len(self._tr_values) >= self.period:
            self.atr = sum(self._tr_values) / self.period
            if close > 0:
                self.atr_percent = self.atr / close

        return self.atr


class IndicatorSuite:
    """
    Complete suite of trading indicators.

    Combines multiple indicators for robust signal generation.
    """

    def __init__(
        self,
        adx_period: int = 14,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        stoch_k: int = 14,
        stoch_d: int = 3,
        atr_period: int = 14,
    ):
        """Initialize all indicators."""
        self.adx = ADX(adx_period)
        self.rsi = RSI(rsi_period)
        self.macd = MACD(macd_fast, macd_slow, macd_signal)
        self.bollinger = BollingerBands(bb_period)
        self.stochastic = Stochastic(stoch_k, stoch_d)
        self.atr = ATR(atr_period)

        self._tick_count = 0

    def update(
        self,
        price: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
    ) -> CompositeSignal:
        """
        Update all indicators with new data.

        Args:
            price: Close price (required)
            high: High price (uses price if not provided)
            low: Low price (uses price if not provided)

        Returns:
            CompositeSignal with all indicator signals
        """
        high = high or price
        low = low or price

        self._tick_count += 1

        signals = []

        # Update each indicator
        adx_signal = self.adx.update(high, low, price)
        if adx_signal:
            signals.append(adx_signal)

        rsi_signal = self.rsi.update(price)
        if rsi_signal:
            signals.append(rsi_signal)

        macd_signal = self.macd.update(price)
        if macd_signal:
            signals.append(macd_signal)

        bb_signal = self.bollinger.update(price)
        if bb_signal:
            signals.append(bb_signal)

        stoch_signal = self.stochastic.update(high, low, price)
        if stoch_signal:
            signals.append(stoch_signal)

        # ATR doesn't generate signals, just volatility measure
        self.atr.update(high, low, price)

        return CompositeSignal(signals=signals)

    def get_position_size_multiplier(self, base_risk: float = 0.02) -> float:
        """
        Get position size multiplier based on ATR.

        Uses ATR for volatility-adjusted position sizing.
        Higher volatility = smaller position.

        Args:
            base_risk: Base risk per trade (default 2%)

        Returns:
            Position size multiplier [0.25, 2.0]
        """
        if self.atr.atr_percent <= 0:
            return 1.0

        # Target consistent risk
        target_atr_percent = 0.015  # 1.5% daily
        multiplier = target_atr_percent / self.atr.atr_percent

        # Clamp to reasonable range
        return max(0.25, min(2.0, multiplier))

    def reset(self) -> None:
        """Reset all indicators."""
        self.adx = ADX(self.adx.period)
        self.rsi = RSI(self.rsi.period)
        self.macd = MACD(
            self.macd.fast_period,
            self.macd.slow_period,
            self.macd.signal_period
        )
        self.bollinger = BollingerBands(
            self.bollinger.period,
            self.bollinger.std_multiplier
        )
        self.stochastic = Stochastic(
            self.stochastic.k_period,
            self.stochastic.d_period
        )
        self.atr = ATR(self.atr.period)
        self._tick_count = 0
