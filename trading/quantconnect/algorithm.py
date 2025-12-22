"""
QuantConnect Algorithm Integration
==================================

Base algorithm class for QuantConnect that integrates the
tick-based state evolution trading system.

Usage:
    from trading.quantconnect import TickEvolutionAlgorithm

    class MyAlgorithm(TickEvolutionAlgorithm):
        def Initialize(self):
            super().Initialize()
            self.configure_symbols(["SPY"])
            self.configure_tier("swing")

        def on_signal(self, symbol, signal, action):
            if action == "entry_long":
                self.SetHoldings(symbol, 0.5 * self.state.position_scalar)
            elif action == "exit":
                self.Liquidate(symbol)
"""

from typing import Dict, List, Optional, Any
from datetime import datetime

# Note: These imports would work in QuantConnect environment
# from AlgorithmImports import *

# For local development/testing, we mock the QC classes
try:
    from AlgorithmImports import QCAlgorithm, Symbol, Tick, Resolution
except ImportError:
    # Mock classes for local development
    class QCAlgorithm:
        """Mock QCAlgorithm for local development."""
        def __init__(self):
            self.Time = datetime.now()
            self.Portfolio = {}

        def SetStartDate(self, *args): pass
        def SetEndDate(self, *args): pass
        def SetCash(self, amount): pass
        def AddEquity(self, symbol, resolution): return symbol
        def SetHoldings(self, symbol, fraction): pass
        def Liquidate(self, symbol=None): pass
        def Debug(self, msg): print(f"[DEBUG] {msg}")
        def Log(self, msg): print(f"[LOG] {msg}")
        def Error(self, msg): print(f"[ERROR] {msg}")

    class Symbol:
        """Mock Symbol."""
        def __init__(self, value):
            self.Value = value

    class Tick:
        """Mock Tick."""
        def __init__(self):
            self.Price = 0.0
            self.Quantity = 0
            self.BidPrice = 0.0
            self.AskPrice = 0.0
            self.Time = datetime.now()

    class Resolution:
        Tick = "Tick"
        Second = "Second"
        Minute = "Minute"

from trading.core import (
    TradingEvolutionEngine,
    TradingConfig,
    TradingStateRegister,
    TickObservables,
)
from trading.tick_processor import (
    TickAggregator,
    TickData,
    OrderFlowImbalance,
    TickVolatility,
)


class TickEvolutionAlgorithm(QCAlgorithm):
    """
    Base algorithm integrating tick-based state evolution.

    Handles:
    - Tick data subscription and processing
    - State evolution engine management
    - Signal generation and position management
    - Audit trail logging

    Subclass and override on_signal() for custom behavior.
    """

    def Initialize(self):
        """
        Initialize algorithm. Call super().Initialize() in subclass.
        """
        # Trading configuration
        self._tier: str = "swing"
        self._risk_profile: str = "moderate"
        self._symbols: List[str] = []

        # Per-symbol components
        self._engines: Dict[str, TradingEvolutionEngine] = {}
        self._aggregators: Dict[str, TickAggregator] = {}
        self._imbalance_calcs: Dict[str, OrderFlowImbalance] = {}
        self._volatility_calcs: Dict[str, TickVolatility] = {}

        # Position tracking
        self._positions: Dict[str, int] = {}  # 1=long, -1=short, 0=flat
        self._entry_prices: Dict[str, float] = {}

        # Performance tracking
        self._peak_equity: float = 0.0
        self._trade_count: int = 0

        # Configuration
        self._min_ticks_before_trade: int = 100
        self._log_frequency: int = 1000

    def configure_symbols(self, symbols: List[str]) -> None:
        """
        Configure symbols to trade.

        Args:
            symbols: List of symbol strings (e.g., ["SPY", "QQQ"])
        """
        self._symbols = symbols

        for symbol in symbols:
            # Add tick data subscription
            equity = self.AddEquity(symbol, Resolution.Tick)

            # Initialize components for each symbol
            self._init_symbol_components(symbol)

    def configure_tier(
        self,
        tier: str,
        risk_profile: str = "moderate"
    ) -> None:
        """
        Configure trading tier (alpha/half-life).

        Args:
            tier: "scalper", "daytrader", "swing", or "position"
            risk_profile: "conservative", "moderate", or "aggressive"
        """
        self._tier = tier
        self._risk_profile = risk_profile

        # Reinitialize engines with new config
        for symbol in self._symbols:
            self._init_symbol_components(symbol)

    def _init_symbol_components(self, symbol: str) -> None:
        """Initialize all components for a symbol."""
        config = TradingConfig.for_tier(self._tier, self._risk_profile)

        self._engines[symbol] = TradingEvolutionEngine(config=config)
        self._aggregators[symbol] = TickAggregator(
            price_window_size=100,
            volume_window_size=50,
            spread_window_size=20,
        )
        self._imbalance_calcs[symbol] = OrderFlowImbalance(window_size=100)
        self._volatility_calcs[symbol] = TickVolatility(window_size=100)
        self._positions[symbol] = 0
        self._entry_prices[symbol] = 0.0

    def OnData(self, data) -> None:
        """
        Process incoming data. Called by QuantConnect on each data event.
        """
        for symbol in self._symbols:
            if symbol not in data.Ticks:
                continue

            ticks = data.Ticks[symbol]
            for tick in ticks:
                self._process_tick(symbol, tick)

    def _process_tick(self, symbol: str, tick: Any) -> None:
        """Process a single tick for a symbol."""
        if symbol not in self._engines:
            return

        # Convert QC tick to our TickData
        tick_data = TickData(
            price=float(tick.Price),
            volume=float(tick.Quantity),
            bid=float(tick.BidPrice) if hasattr(tick, 'BidPrice') else 0.0,
            ask=float(tick.AskPrice) if hasattr(tick, 'AskPrice') else 0.0,
            timestamp_ns=int(tick.Time.timestamp() * 1e9) if hasattr(tick.Time, 'timestamp') else 0,
        )

        # Aggregate tick
        aggregator = self._aggregators[symbol]
        signals = aggregator.process_tick(tick_data)

        # Process imbalance
        imbalance_calc = self._imbalance_calcs[symbol]
        is_buy = signals.tick_direction >= 0
        imbalance_result = imbalance_calc.process_tick(
            tick_data.volume, tick_data.price, is_buy
        )

        # Process volatility
        vol_calc = self._volatility_calcs[symbol]
        vol_result = vol_calc.process_tick(tick_data.price)

        # Convert to observables
        engine = self._engines[symbol]
        obs = aggregator.to_observables(
            signals,
            volatility_anchor=engine.state.volatility_anchor,
            avg_tps=10.0,  # Approximate
        )

        # Calculate P&L change
        pnl_change = self._calculate_pnl_change(symbol, tick_data.price)

        # Evolve state
        new_state, utility_result, action = engine.process_tick(obs, pnl_change)

        # Generate trading signals
        self._evaluate_signals(symbol, obs, engine)

        # Periodic logging
        if engine.ticks_processed % self._log_frequency == 0:
            self._log_state(symbol, engine, utility_result)

    def _calculate_pnl_change(self, symbol: str, current_price: float) -> float:
        """Calculate P&L change since last tick."""
        position = self._positions.get(symbol, 0)
        entry_price = self._entry_prices.get(symbol, 0.0)

        if position == 0 or entry_price == 0:
            return 0.0

        # Simple P&L calculation
        pnl = (current_price - entry_price) / entry_price * position
        return pnl

    def _evaluate_signals(
        self,
        symbol: str,
        obs: TickObservables,
        engine: TradingEvolutionEngine
    ) -> None:
        """Evaluate and act on trading signals."""
        if engine.ticks_processed < self._min_ticks_before_trade:
            return  # Wait for warmup

        position = self._positions.get(symbol, 0)

        if position == 0:
            # Look for entry
            should_enter, signal, reason = engine.should_enter(obs)
            if should_enter:
                direction = "long" if signal > 0 else "short"
                self._positions[symbol] = 1 if signal > 0 else -1
                self._entry_prices[symbol] = obs.tick_number  # Would be actual price
                self._trade_count += 1

                self.on_signal(symbol, signal, f"entry_{direction}")
                self.Debug(f"{symbol}: Entry {direction} | Signal: {signal:.3f} | {reason}")
        else:
            # Look for exit
            should_exit, signal, reason = engine.should_exit(obs, position)
            if should_exit:
                self._positions[symbol] = 0
                self._entry_prices[symbol] = 0.0

                self.on_signal(symbol, signal, "exit")
                self.Debug(f"{symbol}: Exit | Signal: {signal:.3f} | {reason}")

    def on_signal(
        self,
        symbol: str,
        signal: float,
        action: str
    ) -> None:
        """
        Called when a trading signal is generated.

        Override in subclass for custom position management.

        Args:
            symbol: Symbol string
            signal: Signal value [-1, 1]
            action: "entry_long", "entry_short", or "exit"
        """
        engine = self._engines.get(symbol)
        if not engine:
            return

        position_scalar = engine.state.position_scalar

        if action == "entry_long":
            self.SetHoldings(symbol, 0.5 * position_scalar)
        elif action == "entry_short":
            self.SetHoldings(symbol, -0.5 * position_scalar)
        elif action == "exit":
            self.Liquidate(symbol)

    def _log_state(
        self,
        symbol: str,
        engine: TradingEvolutionEngine,
        utility_result: Any
    ) -> None:
        """Log current state for debugging."""
        state = engine.state
        self.Log(
            f"{symbol} | Tick: {engine.ticks_processed} | "
            f"U: {utility_result.utility:.3f} | "
            f"Regime: {state.regime} | "
            f"DD: {state.drawdown:.2%} | "
            f"PosScalar: {state.position_scalar:.2f} | "
            f"Halted: {engine.is_halted}"
        )

    def get_engine(self, symbol: str) -> Optional[TradingEvolutionEngine]:
        """Get evolution engine for a symbol."""
        return self._engines.get(symbol)

    def get_state(self, symbol: str) -> Optional[TradingStateRegister]:
        """Get current state for a symbol."""
        engine = self._engines.get(symbol)
        return engine.state if engine else None

    def get_audit_log(self, symbol: str) -> List[dict]:
        """Get audit log for a symbol."""
        engine = self._engines.get(symbol)
        return engine.export_audit_log() if engine else []

    def OnEndOfAlgorithm(self) -> None:
        """Called at end of backtest."""
        self.Log(f"=== Algorithm Complete ===")
        self.Log(f"Total Trades: {self._trade_count}")

        for symbol in self._symbols:
            engine = self._engines.get(symbol)
            if engine:
                self.Log(f"{symbol}: Ticks Processed: {engine.ticks_processed}")
                if engine.audit_log:
                    self.Log(f"{symbol}: Audit Entries: {len(engine.audit_log)}")
