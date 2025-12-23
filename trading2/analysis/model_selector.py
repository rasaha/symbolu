"""
Model Selector - Objective indicators for EMA vs Bayesian model selection.

Uses quantitative metrics to determine optimal trading model:
- Hurst Exponent: Trend persistence (H > 0.5 = trending, H < 0.5 = mean-reverting)
- ADX: Trend strength
- Volatility Ratio: Short-term vs long-term volatility
- Autocorrelation: Price predictability

This removes guesswork from model selection.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from collections import deque
from enum import Enum
import math


class ModelType(Enum):
    """Trading model types."""
    EMA = "ema"
    BAYESIAN = "bayesian"
    EITHER = "either"  # Both work equally well
    NEITHER = "neither"  # Stay out of market


@dataclass
class ModelRecommendation:
    """Model selection recommendation with confidence."""
    model: ModelType
    confidence: float  # 0-1
    hurst: float
    adx: float
    volatility_ratio: float
    autocorrelation: float
    reason: str

    @property
    def should_trade(self) -> bool:
        """Whether market conditions favor trading at all."""
        return self.model not in (ModelType.NEITHER,)


class HurstExponent:
    """
    Hurst Exponent Calculator using Rescaled Range (R/S) Analysis.

    Interpretation:
        H = 0.5: Random walk (unpredictable)
        H > 0.5: Trending/persistent (past predicts future direction)
        H < 0.5: Mean-reverting/anti-persistent (reversals likely)

    For trading:
        H > 0.55: Use EMA (trend-following works)
        H < 0.45: Use Bayesian (mean reversion, need uncertainty)
        0.45-0.55: Either model, or stay out
    """

    def __init__(self, window: int = 100, min_subseries: int = 8):
        """
        Initialize Hurst calculator.

        Args:
            window: Number of prices to use for calculation
            min_subseries: Minimum subseries length for R/S
        """
        self.window = window
        self.min_subseries = min_subseries
        self._prices: deque = deque(maxlen=window)
        self._returns: deque = deque(maxlen=window - 1)

        self.hurst: float = 0.5  # Start neutral
        self._last_calc_count: int = 0
        self._recalc_interval: int = 10  # Recalculate every N prices

    def update(self, price: float) -> float:
        """
        Update with new price and recalculate Hurst if needed.

        Args:
            price: New price

        Returns:
            Current Hurst exponent estimate
        """
        if len(self._prices) > 0:
            # Calculate log return
            prev_price = self._prices[-1]
            if prev_price > 0 and price > 0:
                log_return = math.log(price / prev_price)
                self._returns.append(log_return)

        self._prices.append(price)
        self._last_calc_count += 1

        # Recalculate periodically when we have enough data
        if (len(self._returns) >= self.window - 1 and
            self._last_calc_count >= self._recalc_interval):
            self.hurst = self._calculate_hurst()
            self._last_calc_count = 0

        return self.hurst

    def _calculate_hurst(self) -> float:
        """
        Calculate Hurst exponent using R/S analysis.

        Uses multiple subseries lengths and fits log(R/S) vs log(n).
        """
        returns = list(self._returns)
        n = len(returns)

        if n < self.min_subseries * 2:
            return 0.5  # Not enough data

        # Calculate R/S for different subseries lengths
        rs_values: List[Tuple[int, float]] = []

        # Use powers of 2 for subseries lengths
        lengths = []
        length = self.min_subseries
        while length <= n // 2:
            lengths.append(length)
            length *= 2

        if not lengths:
            return 0.5

        for length in lengths:
            rs = self._rescaled_range(returns, length)
            if rs > 0:
                rs_values.append((length, rs))

        if len(rs_values) < 2:
            return 0.5

        # Linear regression of log(R/S) vs log(n)
        # H is the slope
        log_n = [math.log(n) for n, _ in rs_values]
        log_rs = [math.log(rs) for _, rs in rs_values]

        hurst = self._linear_regression_slope(log_n, log_rs)

        # Clamp to valid range
        return max(0.0, min(1.0, hurst))

    def _rescaled_range(self, returns: List[float], length: int) -> float:
        """Calculate average R/S for given subseries length."""
        n = len(returns)
        num_subseries = n // length

        if num_subseries == 0:
            return 0.0

        rs_sum = 0.0
        valid_count = 0

        for i in range(num_subseries):
            start = i * length
            end = start + length
            subseries = returns[start:end]

            # Mean of subseries
            mean = sum(subseries) / length

            # Mean-adjusted cumulative deviations
            cumsum = 0.0
            cumulative = []
            for r in subseries:
                cumsum += (r - mean)
                cumulative.append(cumsum)

            # Range
            R = max(cumulative) - min(cumulative)

            # Standard deviation
            variance = sum((r - mean) ** 2 for r in subseries) / length
            S = math.sqrt(variance) if variance > 0 else 1e-10

            if S > 0:
                rs_sum += R / S
                valid_count += 1

        return rs_sum / valid_count if valid_count > 0 else 0.0

    def _linear_regression_slope(self, x: List[float], y: List[float]) -> float:
        """Calculate slope using least squares."""
        n = len(x)
        if n < 2:
            return 0.5

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)

        denominator = n * sum_x2 - sum_x ** 2
        if abs(denominator) < 1e-10:
            return 0.5

        slope = (n * sum_xy - sum_x * sum_y) / denominator
        return slope

    @property
    def is_trending(self) -> bool:
        """Returns True if market is trending (H > 0.55)."""
        return self.hurst > 0.55

    @property
    def is_mean_reverting(self) -> bool:
        """Returns True if market is mean-reverting (H < 0.45)."""
        return self.hurst < 0.45

    @property
    def is_random(self) -> bool:
        """Returns True if market is random walk (H ≈ 0.5)."""
        return 0.45 <= self.hurst <= 0.55


class VolatilityRatio:
    """
    Calculates ratio of short-term to long-term volatility.

    Interpretation:
        Ratio > 1.5: Volatility expanding (use Bayesian)
        Ratio < 0.7: Volatility contracting (use EMA)
        0.7-1.5: Normal volatility
    """

    def __init__(self, short_window: int = 10, long_window: int = 50):
        self.short_window = short_window
        self.long_window = long_window

        self._returns: deque = deque(maxlen=long_window)
        self._prev_price: Optional[float] = None

        self.ratio: float = 1.0
        self.short_vol: float = 0.0
        self.long_vol: float = 0.0

    def update(self, price: float) -> float:
        """Update with new price and return volatility ratio."""
        if self._prev_price is not None and self._prev_price > 0:
            ret = (price - self._prev_price) / self._prev_price
            self._returns.append(ret)

        self._prev_price = price

        if len(self._returns) >= self.long_window:
            returns = list(self._returns)

            # Short-term volatility
            short_returns = returns[-self.short_window:]
            short_mean = sum(short_returns) / len(short_returns)
            self.short_vol = math.sqrt(
                sum((r - short_mean) ** 2 for r in short_returns) / len(short_returns)
            )

            # Long-term volatility
            long_mean = sum(returns) / len(returns)
            self.long_vol = math.sqrt(
                sum((r - long_mean) ** 2 for r in returns) / len(returns)
            )

            if self.long_vol > 0:
                self.ratio = self.short_vol / self.long_vol

        return self.ratio

    @property
    def is_expanding(self) -> bool:
        """Volatility is expanding."""
        return self.ratio > 1.5

    @property
    def is_contracting(self) -> bool:
        """Volatility is contracting."""
        return self.ratio < 0.7


class AutocorrelationCalculator:
    """
    Calculates first-order autocorrelation of returns.

    Interpretation:
        High positive: Trends persist (EMA works)
        High negative: Reversals common (mean reversion)
        Near zero: Random/unpredictable
    """

    def __init__(self, window: int = 50):
        self.window = window
        self._returns: deque = deque(maxlen=window)
        self._prev_price: Optional[float] = None

        self.autocorr: float = 0.0

    def update(self, price: float) -> float:
        """Update with new price and return autocorrelation."""
        if self._prev_price is not None and self._prev_price > 0:
            ret = (price - self._prev_price) / self._prev_price
            self._returns.append(ret)

        self._prev_price = price

        if len(self._returns) >= self.window:
            self.autocorr = self._calculate_autocorr()

        return self.autocorr

    def _calculate_autocorr(self) -> float:
        """Calculate lag-1 autocorrelation."""
        returns = list(self._returns)
        n = len(returns)

        if n < 2:
            return 0.0

        mean = sum(returns) / n

        # Covariance between r(t) and r(t-1)
        cov = sum(
            (returns[i] - mean) * (returns[i-1] - mean)
            for i in range(1, n)
        ) / (n - 1)

        # Variance
        var = sum((r - mean) ** 2 for r in returns) / n

        if var < 1e-10:
            return 0.0

        return cov / var


class ModelSelector:
    """
    Objective model selector using quantitative indicators.

    Combines:
    - Hurst Exponent: Trend persistence
    - ADX: Trend strength (passed in from IndicatorSuite)
    - Volatility Ratio: Regime stability
    - Autocorrelation: Return predictability
    """

    def __init__(
        self,
        hurst_window: int = 100,
        vol_short: int = 10,
        vol_long: int = 50,
        autocorr_window: int = 50,
    ):
        self.hurst_calc = HurstExponent(window=hurst_window)
        self.vol_ratio = VolatilityRatio(short_window=vol_short, long_window=vol_long)
        self.autocorr = AutocorrelationCalculator(window=autocorr_window)

        self._current_recommendation: Optional[ModelRecommendation] = None
        self._update_count: int = 0
        self._recalc_interval: int = 5

    def update(self, price: float, adx: float = 0.0) -> ModelRecommendation:
        """
        Update all indicators and return model recommendation.

        Args:
            price: Current price
            adx: ADX value from IndicatorSuite

        Returns:
            ModelRecommendation with selected model and reasoning
        """
        # Update all calculators
        hurst = self.hurst_calc.update(price)
        vol_ratio = self.vol_ratio.update(price)
        autocorr = self.autocorr.update(price)

        self._update_count += 1

        # Only recalculate recommendation periodically
        if (self._current_recommendation is None or
            self._update_count >= self._recalc_interval):
            self._current_recommendation = self._select_model(
                hurst, adx, vol_ratio, autocorr
            )
            self._update_count = 0

        return self._current_recommendation

    def _select_model(
        self,
        hurst: float,
        adx: float,
        vol_ratio: float,
        autocorr: float,
    ) -> ModelRecommendation:
        """
        Select optimal model based on current market conditions.

        Decision matrix:

        | Condition                        | Model    | Reason                          |
        |----------------------------------|----------|----------------------------------|
        | H > 0.55 & ADX > 25              | EMA      | Strong trend, persistent        |
        | H < 0.45                         | Bayesian | Mean-reverting                  |
        | Vol ratio > 1.5                  | Bayesian | High uncertainty                |
        | ADX < 20 & H ≈ 0.5               | Bayesian | Choppy, need uncertainty aware  |
        | ADX > 30 & autocorr > 0.3        | EMA      | Strong momentum                 |
        | Vol ratio < 0.5 & ADX > 20       | EMA      | Stable trend                    |
        """
        ema_score = 0.0
        bayesian_score = 0.0
        reasons: List[str] = []

        # Hurst exponent contribution
        if hurst > 0.55:
            ema_score += 0.3
            reasons.append(f"H={hurst:.2f} (trending)")
        elif hurst < 0.45:
            bayesian_score += 0.3
            reasons.append(f"H={hurst:.2f} (mean-reverting)")
        else:
            # Random walk - slight preference for Bayesian (uncertainty aware)
            bayesian_score += 0.1
            reasons.append(f"H={hurst:.2f} (random)")

        # ADX contribution
        if adx > 25:
            ema_score += 0.25
            if adx > 40:
                ema_score += 0.1  # Very strong trend
            reasons.append(f"ADX={adx:.1f} (strong trend)")
        elif adx < 20:
            bayesian_score += 0.2
            reasons.append(f"ADX={adx:.1f} (no trend)")

        # Volatility ratio contribution
        if vol_ratio > 1.5:
            bayesian_score += 0.25
            reasons.append(f"VolRatio={vol_ratio:.2f} (expanding)")
        elif vol_ratio < 0.7:
            ema_score += 0.15
            reasons.append(f"VolRatio={vol_ratio:.2f} (contracting)")

        # Autocorrelation contribution
        if autocorr > 0.3:
            ema_score += 0.2
            reasons.append(f"AutoCorr={autocorr:.2f} (persistent)")
        elif autocorr < -0.2:
            bayesian_score += 0.2
            reasons.append(f"AutoCorr={autocorr:.2f} (reverting)")

        # Determine model
        score_diff = ema_score - bayesian_score

        if score_diff > 0.15:
            model = ModelType.EMA
            confidence = min(1.0, 0.5 + score_diff)
        elif score_diff < -0.15:
            model = ModelType.BAYESIAN
            confidence = min(1.0, 0.5 - score_diff)
        else:
            # Close call - default to Bayesian (more robust)
            if bayesian_score > 0.3:
                model = ModelType.BAYESIAN
                confidence = 0.5 + bayesian_score * 0.3
            elif ema_score > 0.3:
                model = ModelType.EMA
                confidence = 0.5 + ema_score * 0.3
            else:
                # Neither model is clearly better
                model = ModelType.EITHER
                confidence = 0.4

        # Check for conditions where neither model works well
        if hurst > 0.48 and hurst < 0.52 and adx < 15 and abs(autocorr) < 0.1:
            model = ModelType.NEITHER
            confidence = 0.7
            reasons.append("Pure random walk - stay out")

        return ModelRecommendation(
            model=model,
            confidence=confidence,
            hurst=hurst,
            adx=adx,
            volatility_ratio=vol_ratio,
            autocorrelation=autocorr,
            reason=" | ".join(reasons),
        )

    def get_recommendation(self) -> Optional[ModelRecommendation]:
        """Get current recommendation without update."""
        return self._current_recommendation

    def reset(self) -> None:
        """Reset all calculators."""
        self.hurst_calc = HurstExponent(window=self.hurst_calc.window)
        self.vol_ratio = VolatilityRatio(
            short_window=self.vol_ratio.short_window,
            long_window=self.vol_ratio.long_window
        )
        self.autocorr = AutocorrelationCalculator(window=self.autocorr.window)
        self._current_recommendation = None
        self._update_count = 0
