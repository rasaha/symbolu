"""
QuantConnect Custom Indicator
=============================

Wraps the state evolution engine as a QC-compatible indicator.

Can be used standalone or with other QC indicators.
"""

from typing import Optional, Tuple
from datetime import datetime

# QC imports (mocked for local development)
try:
    from AlgorithmImports import PythonIndicator
except ImportError:
    class PythonIndicator:
        """Mock PythonIndicator for local development."""
        def __init__(self, name):
            self.Name = name
            self.Value = 0.0
            self.IsReady = False
            self.WarmUpPeriod = 0
            self.Current = type('obj', (object,), {'Value': 0.0})()

from trading.core import (
    TradingEvolutionEngine,
    TradingConfig,
    TradingStateRegister,
    TickObservables,
)
from trading.tick_processor import (
    TickAggregator,
    TickData,
    TickVolatility,
)


class TickEvolutionIndicator(PythonIndicator):
    """
    Custom indicator wrapping the state evolution engine.

    Outputs the composite trading signal [-1, 1].

    Usage in QC:
        self.evolution = TickEvolutionIndicator("EVO", tier="swing")
        self.RegisterIndicator(symbol, self.evolution, Resolution.Tick)
    """

    def __init__(
        self,
        name: str,
        tier: str = "swing",
        risk_profile: str = "moderate",
        warmup_ticks: int = 100,
    ):
        """
        Initialize indicator.

        Args:
            name: Indicator name
            tier: Trading tier for alpha configuration
            risk_profile: Risk profile for limits
            warmup_ticks: Ticks needed before indicator is ready
        """
        super().__init__(name)

        self.tier = tier
        self.risk_profile = risk_profile
        self.warmup_ticks = warmup_ticks

        # Initialize components
        config = TradingConfig.for_tier(tier, risk_profile)
        self.engine = TradingEvolutionEngine(config=config)
        self.aggregator = TickAggregator()
        self.volatility = TickVolatility()

        # State
        self.ticks_processed = 0
        self.last_price = 0.0
        self.last_pnl = 0.0

        # Additional outputs (accessible after Update)
        self.signal = 0.0
        self.utility = 0.0
        self.regime = "unknown"
        self.drawdown = 0.0
        self.position_scalar = 1.0

    @property
    def IsReady(self) -> bool:
        """Check if indicator has enough data."""
        return self.ticks_processed >= self.warmup_ticks

    @property
    def WarmUpPeriod(self) -> int:
        """Number of ticks needed for warmup."""
        return self.warmup_ticks

    def Update(self, input_data) -> bool:
        """
        Update indicator with new tick data.

        Args:
            input_data: QC data point (Tick or TradeBar)

        Returns:
            True if update was successful
        """
        try:
            # Extract price and volume
            if hasattr(input_data, 'Price'):
                price = float(input_data.Price)
                volume = float(getattr(input_data, 'Quantity', 1))
                bid = float(getattr(input_data, 'BidPrice', 0))
                ask = float(getattr(input_data, 'AskPrice', 0))
                timestamp = input_data.Time if hasattr(input_data, 'Time') else datetime.now()
            else:
                # TradeBar fallback
                price = float(input_data.Close)
                volume = float(input_data.Volume)
                bid = 0.0
                ask = 0.0
                timestamp = input_data.Time

            timestamp_ns = int(timestamp.timestamp() * 1e9) if hasattr(timestamp, 'timestamp') else 0

            # Create tick data
            tick = TickData(
                price=price,
                volume=volume,
                bid=bid,
                ask=ask,
                timestamp_ns=timestamp_ns,
            )

            # Process through pipeline
            self._process_tick(tick)

            # Update Value (primary output is signal)
            self.Value = self.signal
            self.Current.Value = self.signal

            return True

        except Exception as e:
            return False

    def _process_tick(self, tick: TickData) -> None:
        """Internal tick processing."""
        self.ticks_processed += 1

        # Aggregate
        signals = self.aggregator.process_tick(tick)

        # Volatility
        vol_result = self.volatility.process_tick(tick.price)

        # Convert to observables
        obs = self.aggregator.to_observables(
            signals,
            volatility_anchor=self.engine.state.volatility_anchor,
        )

        # Calculate P&L (simplified - uses price change as proxy)
        if self.last_price > 0:
            pnl_change = (tick.price - self.last_price) / self.last_price
        else:
            pnl_change = 0.0
        self.last_price = tick.price

        # Evolve state
        new_state, utility_result, action = self.engine.process_tick(obs, pnl_change)

        # Update outputs
        self.signal = self.engine.get_signal(obs)
        self.utility = utility_result.utility
        self.regime = new_state.regime
        self.drawdown = new_state.drawdown
        self.position_scalar = new_state.position_scalar

    def should_enter(self) -> Tuple[bool, str]:
        """
        Check if entry conditions are met.

        Returns:
            Tuple of (should_enter, direction)
        """
        if not self.IsReady:
            return False, "warmup"

        if self.engine.is_halted:
            return False, "halted"

        if abs(self.signal) > self.engine.state.tau_entry:
            if self.utility > 0:
                direction = "long" if self.signal > 0 else "short"
                return True, direction

        return False, "no_signal"

    def should_exit(self, position_direction: int) -> Tuple[bool, str]:
        """
        Check if exit conditions are met.

        Args:
            position_direction: 1 for long, -1 for short

        Returns:
            Tuple of (should_exit, reason)
        """
        if not self.IsReady:
            return False, "warmup"

        if self.engine.is_halted:
            return True, "halted"

        if self.engine.state.is_crisis_mode:
            return True, "crisis"

        # Signal reversal
        if position_direction * self.signal < -self.engine.state.tau_exit:
            return True, "reversal"

        # Drawdown
        if self.drawdown > 0.08:
            return True, "drawdown"

        return False, "hold"

    def get_state_dict(self) -> dict:
        """Get current state as dictionary."""
        return {
            "signal": self.signal,
            "utility": self.utility,
            "regime": self.regime,
            "drawdown": self.drawdown,
            "position_scalar": self.position_scalar,
            "ticks_processed": self.ticks_processed,
            "is_ready": self.IsReady,
            "is_halted": self.engine.is_halted,
        }

    def reset(self) -> None:
        """Reset indicator state."""
        config = TradingConfig.for_tier(self.tier, self.risk_profile)
        self.engine = TradingEvolutionEngine(config=config)
        self.aggregator = TickAggregator()
        self.volatility = TickVolatility()
        self.ticks_processed = 0
        self.last_price = 0.0
        self.signal = 0.0
        self.utility = 0.0
        self.Value = 0.0
