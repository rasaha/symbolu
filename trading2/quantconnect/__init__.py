"""
Trading2 QuantConnect Integration

Bayesian trading algorithm for QuantConnect backtesting platform.
"""

from trading2.quantconnect.algorithm import BayesianTradingAlgorithm
from trading2.quantconnect.indicator import BayesianIndicator

__all__ = [
    "BayesianTradingAlgorithm",
    "BayesianIndicator",
]
