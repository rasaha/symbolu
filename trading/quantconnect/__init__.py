"""
QuantConnect Integration
========================

Integration layer for running the trading framework on QuantConnect.

Main Components:
- TickEvolutionAlgorithm: Base algorithm class with state evolution
- TickEvolutionIndicator: Custom indicator wrapping the engine
"""

from trading.quantconnect.algorithm import TickEvolutionAlgorithm
from trading.quantconnect.indicator import TickEvolutionIndicator

__all__ = [
    "TickEvolutionAlgorithm",
    "TickEvolutionIndicator",
]
