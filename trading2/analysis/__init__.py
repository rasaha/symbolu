"""
Trading2 Analysis Module

Technical analysis components including Elliott Wave analysis,
Fibonacci retracement/extension calculations, and professional
trading indicators.
"""

from trading2.analysis.elliott_wave import (
    ElliottWaveAnalyzer,
    WaveType,
    WavePattern,
    WaveCount,
    PivotPoint,
    FibonacciLevel,
)

from trading2.analysis.indicators import (
    IndicatorSuite,
    CompositeSignal,
    IndicatorSignal,
    SignalType,
    ADX,
    RSI,
    MACD,
    BollingerBands,
    Stochastic,
    ATR,
)

from trading2.analysis.model_selector import (
    ModelSelector,
    ModelType,
    ModelRecommendation,
    HurstExponent,
    VolatilityRatio,
    AutocorrelationCalculator,
)

__all__ = [
    # Elliott Wave
    "ElliottWaveAnalyzer",
    "WaveType",
    "WavePattern",
    "WaveCount",
    "PivotPoint",
    "FibonacciLevel",

    # Indicators
    "IndicatorSuite",
    "CompositeSignal",
    "IndicatorSignal",
    "SignalType",
    "ADX",
    "RSI",
    "MACD",
    "BollingerBands",
    "Stochastic",
    "ATR",

    # Model Selector
    "ModelSelector",
    "ModelType",
    "ModelRecommendation",
    "HurstExponent",
    "VolatilityRatio",
    "AutocorrelationCalculator",
]
