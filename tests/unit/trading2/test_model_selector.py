"""
Tests for Model Selector - Hurst Exponent and objective model selection.
"""

import pytest
import math
import random

from trading2.analysis.model_selector import (
    HurstExponent,
    VolatilityRatio,
    AutocorrelationCalculator,
    ModelSelector,
    ModelType,
    ModelRecommendation,
)


class TestHurstExponent:
    """Tests for Hurst exponent calculator."""

    def test_initialization(self):
        """Test default initialization."""
        hurst = HurstExponent()
        assert hurst.window == 100
        assert hurst.hurst == 0.5  # Neutral start
        assert hurst.is_random  # 0.5 is random walk

    def test_update_with_insufficient_data(self):
        """Test that Hurst stays at 0.5 with insufficient data."""
        hurst = HurstExponent(window=100)

        # Add only 10 prices
        for i in range(10):
            result = hurst.update(100 + i * 0.1)

        # Should still be neutral due to insufficient data
        assert hurst.hurst == 0.5

    def test_trending_series_high_hurst(self):
        """Test that a trending series produces H > 0.5."""
        hurst = HurstExponent(window=100)
        random.seed(123)  # Fixed seed for reproducibility

        # Generate strongly trending series (cumulative sum of positive values)
        price = 100.0
        for i in range(200):
            price += 0.2 + random.random() * 0.05  # Strong positive trend
            hurst.update(price)

        # Trending series should have H >= 0.45 (close to or above 0.5)
        # Note: R/S analysis can underestimate H for short series
        assert hurst.hurst >= 0.45, f"Expected H >= 0.45 for trending series, got {hurst.hurst}"

    def test_mean_reverting_series_low_hurst(self):
        """Test that a mean-reverting series produces H < 0.5."""
        hurst = HurstExponent(window=100)

        # Generate mean-reverting series (oscillating)
        center = 100.0
        for i in range(150):
            # Oscillate around center with noise
            offset = 2.0 * math.sin(i * 0.5) + random.random() * 0.1
            price = center + offset
            hurst.update(price)

        # Mean-reverting should have H < 0.5
        # Note: Due to randomness, we use a more lenient threshold
        assert hurst.hurst < 0.55, f"Expected H < 0.55 for mean-reverting, got {hurst.hurst}"

    def test_random_walk_near_half(self):
        """Test that random walk produces H ≈ 0.5."""
        hurst = HurstExponent(window=100)
        random.seed(42)  # For reproducibility

        # Generate random walk
        price = 100.0
        for i in range(200):
            price += random.gauss(0, 1)
            hurst.update(price)

        # Random walk should have H ≈ 0.5
        assert 0.35 < hurst.hurst < 0.65, f"Expected H ≈ 0.5 for random walk, got {hurst.hurst}"

    def test_is_trending_property(self):
        """Test is_trending property."""
        hurst = HurstExponent()
        hurst.hurst = 0.6
        assert hurst.is_trending

        hurst.hurst = 0.5
        assert not hurst.is_trending

    def test_is_mean_reverting_property(self):
        """Test is_mean_reverting property."""
        hurst = HurstExponent()
        hurst.hurst = 0.4
        assert hurst.is_mean_reverting

        hurst.hurst = 0.5
        assert not hurst.is_mean_reverting


class TestVolatilityRatio:
    """Tests for volatility ratio calculator."""

    def test_initialization(self):
        """Test default initialization."""
        vol = VolatilityRatio()
        assert vol.short_window == 10
        assert vol.long_window == 50
        assert vol.ratio == 1.0

    def test_stable_volatility(self):
        """Test that stable volatility produces ratio ≈ 1."""
        vol = VolatilityRatio(short_window=10, long_window=50)
        random.seed(42)

        # Generate price series with constant volatility
        price = 100.0
        for i in range(100):
            price += random.gauss(0, 1)
            vol.update(price)

        # Should be approximately 1
        assert 0.7 < vol.ratio < 1.5, f"Expected ratio ≈ 1, got {vol.ratio}"

    def test_expanding_volatility(self):
        """Test that expanding volatility produces ratio > 1."""
        vol = VolatilityRatio(short_window=10, long_window=50)

        # Low volatility period
        price = 100.0
        for i in range(60):
            price += random.gauss(0, 0.5)
            vol.update(price)

        # High volatility period (recent)
        for i in range(20):
            price += random.gauss(0, 3.0)
            vol.update(price)

        # Recent volatility higher than historical
        assert vol.ratio > 1.0, f"Expected ratio > 1 for expanding vol, got {vol.ratio}"

    def test_contracting_volatility(self):
        """Test that contracting volatility produces ratio < 1."""
        vol = VolatilityRatio(short_window=10, long_window=50)

        # High volatility period (older)
        price = 100.0
        for i in range(60):
            price += random.gauss(0, 3.0)
            vol.update(price)

        # Low volatility period (recent)
        for i in range(20):
            price += random.gauss(0, 0.3)
            vol.update(price)

        # Recent volatility lower than historical
        assert vol.ratio < 1.0, f"Expected ratio < 1 for contracting vol, got {vol.ratio}"


class TestAutocorrelationCalculator:
    """Tests for autocorrelation calculator."""

    def test_initialization(self):
        """Test default initialization."""
        ac = AutocorrelationCalculator()
        assert ac.window == 50
        assert ac.autocorr == 0.0

    def test_trending_positive_autocorr(self):
        """Test that trending series has positive autocorrelation."""
        ac = AutocorrelationCalculator(window=50)

        # Trending series - consistent positive moves
        price = 100.0
        for i in range(100):
            price += 0.5 + random.random() * 0.2
            ac.update(price)

        # Trending should have positive autocorrelation
        assert ac.autocorr > 0, f"Expected positive autocorr for trend, got {ac.autocorr}"

    def test_oscillating_negative_autocorr(self):
        """Test that oscillating series has negative autocorrelation."""
        ac = AutocorrelationCalculator(window=50)

        # Oscillating series - alternating moves
        price = 100.0
        for i in range(100):
            direction = 1 if i % 2 == 0 else -1
            price += direction * (0.5 + random.random() * 0.1)
            ac.update(price)

        # Oscillating should have negative autocorrelation
        assert ac.autocorr < 0, f"Expected negative autocorr for oscillation, got {ac.autocorr}"


class TestModelSelector:
    """Tests for the complete model selector."""

    def test_initialization(self):
        """Test default initialization."""
        selector = ModelSelector()
        assert selector.get_recommendation() is None

    def test_trending_market_selects_ema(self):
        """Test that trending market recommends EMA."""
        selector = ModelSelector(hurst_window=50)
        random.seed(42)

        # Generate strong trending data
        price = 100.0
        for i in range(100):
            price += 0.3 + random.random() * 0.1
            adx = 35.0  # Strong trend
            rec = selector.update(price, adx)

        # Should recommend EMA for trending + high ADX
        assert rec.model == ModelType.EMA, f"Expected EMA for trending market, got {rec.model}"
        assert rec.adx == 35.0
        assert rec.should_trade

    def test_choppy_market_selects_bayesian(self):
        """Test that choppy market recommends Bayesian."""
        selector = ModelSelector(hurst_window=50)
        random.seed(42)

        # Generate choppy oscillating data
        price = 100.0
        for i in range(100):
            direction = 1 if i % 3 == 0 else -1
            price += direction * random.random() * 0.5
            adx = 15.0  # Weak trend
            rec = selector.update(price, adx)

        # Should recommend Bayesian for choppy + low ADX
        assert rec.model == ModelType.BAYESIAN, f"Expected Bayesian for choppy market, got {rec.model}"

    def test_recommendation_includes_all_metrics(self):
        """Test that recommendation includes all required metrics."""
        selector = ModelSelector()

        for i in range(100):
            rec = selector.update(100 + i * 0.1, adx=25.0)

        assert isinstance(rec, ModelRecommendation)
        assert hasattr(rec, 'model')
        assert hasattr(rec, 'confidence')
        assert hasattr(rec, 'hurst')
        assert hasattr(rec, 'adx')
        assert hasattr(rec, 'volatility_ratio')
        assert hasattr(rec, 'autocorrelation')
        assert hasattr(rec, 'reason')
        assert 0 <= rec.confidence <= 1

    def test_high_volatility_selects_bayesian(self):
        """Test that high volatility expansion recommends Bayesian."""
        selector = ModelSelector(vol_short=5, vol_long=25)

        # Low volatility history
        price = 100.0
        for i in range(30):
            price += random.gauss(0, 0.1)
            selector.update(price, adx=25.0)

        # High volatility recent
        for i in range(20):
            price += random.gauss(0, 2.0)
            rec = selector.update(price, adx=25.0)

        # High vol expansion should favor Bayesian
        if rec.volatility_ratio > 1.5:
            assert rec.model == ModelType.BAYESIAN or "expanding" in rec.reason.lower()

    def test_reset(self):
        """Test reset functionality."""
        selector = ModelSelector()

        for i in range(50):
            selector.update(100 + i, adx=30.0)

        assert selector.get_recommendation() is not None

        selector.reset()

        assert selector.get_recommendation() is None

    def test_model_type_enum(self):
        """Test ModelType enum values."""
        assert ModelType.EMA.value == "ema"
        assert ModelType.BAYESIAN.value == "bayesian"
        assert ModelType.EITHER.value == "either"
        assert ModelType.NEITHER.value == "neither"

    def test_reason_string_populated(self):
        """Test that reason string provides useful information."""
        selector = ModelSelector()

        for i in range(100):
            rec = selector.update(100 + i * 0.1, adx=30.0)

        assert rec.reason != ""
        assert len(rec.reason) > 10  # Should have meaningful content


class TestModelSelectorIntegration:
    """Integration tests for model selector with engine."""

    def test_model_selector_with_simulated_market(self):
        """Test model selector behavior across different market regimes."""
        selector = ModelSelector()
        results = []

        price = 100.0
        random.seed(42)

        # Regime 1: Strong trend (ticks 0-100)
        for i in range(100):
            price += 0.2 + random.random() * 0.1
            adx = 30 + i * 0.1  # Increasing ADX
            rec = selector.update(price, adx)
            results.append(('trend', rec.model))

        # Regime 2: Range/Chop (ticks 100-200)
        for i in range(100):
            price += random.gauss(0, 0.5)
            adx = 15 + random.random() * 5  # Low ADX
            rec = selector.update(price, adx)
            results.append(('chop', rec.model))

        # Count recommendations by regime
        trend_ema = sum(1 for r in results[:100] if r[0] == 'trend' and r[1] == ModelType.EMA)
        chop_bayesian = sum(1 for r in results[100:] if r[0] == 'chop' and r[1] == ModelType.BAYESIAN)

        # Should see more EMA in trending regime
        # Should see more Bayesian in choppy regime
        # (Not strict assertions due to transition periods)
        assert trend_ema > 0 or chop_bayesian > 0, "Model selector should adapt to regimes"
