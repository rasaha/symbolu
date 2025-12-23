"""
Bayesian Trading Algorithm for QuantConnect

Base algorithm class that integrates the Bayesian evolution engine
with QuantConnect's backtesting framework.

Usage:
    class MyAlgorithm(BayesianTradingAlgorithm):
        def Initialize(self):
            self.SetStartDate(2020, 1, 1)
            self.SetCash(100000)
            self.configure_symbols(["SPY", "QQQ"])
            self.configure_tier("swing")

        def on_signal(self, symbol, signal):
            if signal["entry"]:
                direction = 1 if signal["direction"] == "buy" else -1
                self.SetHoldings(symbol, direction * signal["position_size"])
            elif signal["exit"]:
                self.Liquidate(symbol)
"""

from typing import Dict, List, Optional, Any
from collections import defaultdict

# QuantConnect imports (available in QC environment)
try:
    from AlgorithmImports import *
except ImportError:
    # Mock for development outside QC
    class QCAlgorithm:
        pass
    Resolution = type('Resolution', (), {'Tick': 0, 'Second': 1, 'Minute': 2})()

from trading2.core.evolution_engine import BayesianEvolutionEngine, create_bayesian_engine
from trading2.core.config import TradingTier


class BayesianTradingAlgorithm(QCAlgorithm):
    """
    Base algorithm for Bayesian trading on QuantConnect.

    Integrates:
    - Bayesian state evolution
    - Elliott Wave analysis
    - Professional indicators (ADX, RSI, MACD, etc.)
    - Probabilistic buy/sell signals
    """

    def Initialize(self):
        """
        Initialize algorithm. Override in subclass.

        Example:
            def Initialize(self):
                self.SetStartDate(2020, 1, 1)
                self.SetEndDate(2023, 12, 31)
                self.SetCash(100000)

                self.configure_symbols(["SPY"])
                self.configure_tier("swing")
        """
        # Engines per symbol
        self._engines: Dict[str, BayesianEvolutionEngine] = {}

        # Position tracking
        self._positions: Dict[str, int] = defaultdict(int)
        self._entry_prices: Dict[str, float] = {}

        # Configuration
        self._tier: TradingTier = TradingTier.SWING
        self._symbols: List[str] = []

        # State
        self._initialized = False
        self._tick_count = 0

    def configure_symbols(
        self,
        symbols: List[str],
        resolution: int = None,
    ) -> None:
        """
        Configure symbols to trade.

        Args:
            symbols: List of ticker symbols
            resolution: Data resolution (default: Tick)
        """
        resolution = resolution if resolution is not None else Resolution.Tick

        for symbol_str in symbols:
            symbol = self.AddEquity(symbol_str, resolution).Symbol
            self._symbols.append(symbol)

            # Create engine for this symbol
            self._engines[str(symbol)] = create_bayesian_engine(
                tier=self._tier.value,
                asymmetric=True,
            )

        self._initialized = True

    def configure_tier(self, tier: str) -> None:
        """
        Configure trading tier.

        Args:
            tier: "scalper", "daytrader", "swing", or "position"
        """
        tier_map = {
            "scalper": TradingTier.SCALPER,
            "daytrader": TradingTier.DAYTRADER,
            "swing": TradingTier.SWING,
            "position": TradingTier.POSITION,
        }
        self._tier = tier_map.get(tier.lower(), TradingTier.SWING)

        # Update existing engines
        for symbol_key in self._engines:
            self._engines[symbol_key] = create_bayesian_engine(
                tier=tier,
                asymmetric=True,
            )

    def OnData(self, data) -> None:
        """
        Process incoming data.

        Called by QuantConnect on each data event.
        """
        if not self._initialized:
            return

        for symbol in self._symbols:
            symbol_key = str(symbol)

            if symbol not in data:
                continue

            # Get tick/bar data
            bar = data[symbol]

            # Handle different data types
            if hasattr(bar, 'Price'):
                # Tick data
                price = bar.Price
                high = price
                low = price
                volume = bar.Quantity if hasattr(bar, 'Quantity') else 0
            else:
                # Bar data
                price = bar.Close
                high = bar.High
                low = bar.Low
                volume = bar.Volume

            # Get engine for this symbol
            engine = self._engines.get(symbol_key)
            if engine is None:
                continue

            # Process tick
            utility_result = engine.process_tick(
                price=price,
                high=high,
                low=low,
                volume=volume,
            )

            # Update equity for drawdown tracking
            portfolio_value = self.Portfolio.TotalPortfolioValue
            engine.update_equity(portfolio_value)

            # Get trading signal
            signal = engine.get_trading_signal()

            # Evaluate signals
            self._evaluate_signal(symbol, signal, price)

            self._tick_count += 1

    def _evaluate_signal(
        self,
        symbol,
        signal: Dict[str, Any],
        price: float,
    ) -> None:
        """Evaluate signal and trigger callbacks."""
        symbol_key = str(symbol)
        current_position = self._positions.get(symbol_key, 0)

        # Entry signal
        if signal.get("entry") and signal.get("should_trade"):
            if current_position == 0:  # Only enter if flat
                self.on_signal(symbol, signal)

        # Exit signal
        elif signal.get("exit"):
            if current_position != 0:  # Only exit if in position
                self.on_signal(symbol, signal)

    def on_signal(self, symbol, signal: Dict[str, Any]) -> None:
        """
        Handle trading signal. Override in subclass.

        Args:
            symbol: Trading symbol
            signal: Signal dictionary with:
                - signal: Combined signal value
                - direction: "buy", "sell", or "neutral"
                - confidence: Signal confidence
                - should_trade: Whether conditions favor trading
                - position_size: Recommended position size
                - entry: Entry signal active
                - exit: Exit signal active
                - indicators: Individual indicator signals
        """
        symbol_key = str(symbol)

        if signal.get("entry"):
            direction = 1 if signal["direction"] == "buy" else -1
            size = signal.get("position_size", 0.5)

            # Update position tracking
            self._positions[symbol_key] = direction

            # Log signal
            self.Debug(
                f"ENTRY {symbol_key}: {signal['direction'].upper()} "
                f"size={size:.2f} confidence={signal['confidence']:.2f} "
                f"regime={signal['regime']}"
            )

        elif signal.get("exit"):
            self._positions[symbol_key] = 0

            self.Debug(f"EXIT {symbol_key}")

    def get_engine(self, symbol) -> Optional[BayesianEvolutionEngine]:
        """Get engine for a symbol."""
        return self._engines.get(str(symbol))

    def get_state_summary(self, symbol) -> Optional[Dict[str, Any]]:
        """Get state summary for a symbol."""
        engine = self.get_engine(symbol)
        if engine:
            return engine.get_state_summary()
        return None

    def get_all_signals(self) -> Dict[str, Dict[str, Any]]:
        """Get current signals for all symbols."""
        signals = {}
        for symbol_key, engine in self._engines.items():
            signals[symbol_key] = engine.get_trading_signal()
        return signals

    def OnEndOfAlgorithm(self) -> None:
        """Called at end of backtest."""
        self.Debug(f"Total ticks processed: {self._tick_count}")

        for symbol_key, engine in self._engines.items():
            summary = engine.get_state_summary()
            self.Debug(f"{symbol_key} final state: regime={summary['regime']}, "
                      f"uncertainty={summary['total_uncertainty']:.4f}")
