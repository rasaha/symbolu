"""
Trading2: Bayesian Trading Framework for QuantConnect

A tick-based trading system using Bayesian inference instead of EMA,
with Elliott Wave analysis and technical indicators.

Key differences from trading (EMA model):
- Bayesian posterior updates instead of exponential smoothing
- Elliott Wave pattern recognition
- Fibonacci retracement/extension levels
- Probabilistic regime detection

Based on SymbolU v2.7 Bayesian State Evolution Layer.
"""

__version__ = "0.1.0-experimental"
__author__ = "SymbolU Team"

from trading2.core import (
    BayesianConfig,
    BayesianStateRegister,
    BayesianEvolutionEngine,
    BayesianObservables,
    BayesianUtility,
)

__all__ = [
    "BayesianConfig",
    "BayesianStateRegister",
    "BayesianEvolutionEngine",
    "BayesianObservables",
    "BayesianUtility",
]
