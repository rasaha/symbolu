"""
SymbolU Trading Framework (Experimental)
=========================================

Tick-based trading system built on v2.7 State Evolution concepts.
Designed for QuantConnect integration.

Core Concepts (from v2.7):
- Deterministic state evolution with EMA updates
- Bounded parameters with hard limits
- Configurable memory horizon (alpha/half-life)
- Full audit trail for compliance

Trading Extensions:
- Tick-based processing (not time-based)
- Asymmetric gain/loss treatment
- Volatility-adjusted position sizing
- Order flow imbalance detection
- Multi-timeframe signal fusion
- Drawdown circuit breakers
- Regime detection

Usage with QuantConnect:
    from trading.quantconnect import TickEvolutionAlgorithm

    class MyAlgo(TickEvolutionAlgorithm):
        def Initialize(self):
            super().Initialize()
            self.configure_symbols(["SPY", "QQQ"])
            self.configure_tier("swing")  # alpha=0.05, ~14 tick half-life
"""

from trading.core import (
    TradingStateRegister,
    TickObservables,
    TradingUtility,
    TradingEvolutionEngine,
    TradingConfig,
    AlphaConfig,
    RiskConfig,
)

from trading.tick_processor import (
    TickAggregator,
    OrderFlowImbalance,
    TickVolatility,
    TickSignals,
)

__version__ = "0.1.0-experimental"
__all__ = [
    # Core
    "TradingStateRegister",
    "TickObservables",
    "TradingUtility",
    "TradingEvolutionEngine",
    "TradingConfig",
    "AlphaConfig",
    "RiskConfig",
    # Tick Processor
    "TickAggregator",
    "OrderFlowImbalance",
    "TickVolatility",
    "TickSignals",
]
