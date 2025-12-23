"""
Bayesian Indicator for QuantConnect

Custom indicator wrapper that exposes the Bayesian evolution engine
as a QuantConnect-compatible indicator.

Usage:
    self.bayesian = BayesianIndicator("BAY", tier="swing")
    self.RegisterIndicator(symbol, self.bayesian, Resolution.Tick)

    # Access signals
    if self.bayesian.IsReady:
        signal = self.bayesian.signal
        if self.bayesian.entry_signal:
            self.SetHoldings(symbol, self.bayesian.position_size)
"""

from typing import Optional, Dict, Any

# QuantConnect imports
try:
    from AlgorithmImports import *
    from QuantConnect.Indicators import PythonIndicator
except ImportError:
    # Mock for development
    class PythonIndicator:
        def __init__(self, name):
            self.Name = name
            self.Value = 0
            self.IsReady = False

        def Update(self, data):
            pass

from trading2.core.evolution_engine import BayesianEvolutionEngine, create_bayesian_engine


class BayesianIndicator(PythonIndicator):
    """
    QuantConnect-compatible indicator wrapping Bayesian engine.

    Properties:
        signal: Combined trading signal [-1, 1]
        direction: "buy", "sell", or "neutral"
        confidence: Signal confidence [0, 1]
        entry_signal: True if entry conditions met
        exit_signal: True if exit conditions met
        position_size: Recommended position size [0, 1]
        regime: Current market regime
        adx: ADX indicator value
        rsi: RSI indicator value
        elliott_wave: Current Elliott wave number
    """

    def __init__(
        self,
        name: str = "Bayesian",
        tier: str = "swing",
        asymmetric: bool = True,
    ):
        """
        Initialize Bayesian indicator.

        Args:
            name: Indicator name
            tier: Trading tier
            asymmetric: Enable asymmetric updates
        """
        super().__init__(name)
        self.Name = name

        # Create engine
        self._engine = create_bayesian_engine(tier=tier, asymmetric=asymmetric)

        # Cached values
        self._signal: float = 0.0
        self._direction: str = "neutral"
        self._confidence: float = 0.0
        self._entry_signal: bool = False
        self._exit_signal: bool = False
        self._position_size: float = 0.0
        self._regime: str = "unknown"
        self._adx: float = 0.0
        self._rsi: float = 50.0
        self._elliott_wave: Optional[int] = None

        # Readiness
        self._warmup_ticks = 50
        self._tick_count = 0

    def Update(self, data) -> bool:
        """
        Update indicator with new data.

        Args:
            data: Tick or bar data from QuantConnect

        Returns:
            True if update successful
        """
        # Extract price data
        if hasattr(data, 'Price'):
            # Tick data
            price = data.Price
            high = price
            low = price
        elif hasattr(data, 'Close'):
            # Bar data
            price = data.Close
            high = data.High
            low = data.Low
        else:
            return False

        # Process through engine
        self._engine.process_tick(
            price=price,
            high=high,
            low=low,
        )

        self._tick_count += 1

        # Get signal
        signal_data = self._engine.get_trading_signal()
        self._update_cached_values(signal_data)

        # Update indicator value (primary output)
        self.Value = self._signal

        return True

    def _update_cached_values(self, signal_data: Dict[str, Any]) -> None:
        """Update cached property values from signal data."""
        self._signal = signal_data.get("signal", 0.0)
        self._direction = signal_data.get("direction", "neutral")
        self._confidence = signal_data.get("confidence", 0.0)
        self._entry_signal = signal_data.get("entry", False)
        self._exit_signal = signal_data.get("exit", False)
        self._position_size = signal_data.get("position_size", 0.0)
        self._regime = signal_data.get("regime", "unknown")

        # Get indicator values
        indicators = signal_data.get("indicators", {})

        # ADX and RSI from engine's indicator suite
        if self._engine.indicators:
            self._adx = self._engine.indicators.adx.adx
            self._rsi = self._engine.indicators.rsi.rsi

        # Elliott wave
        if self._engine.last_wave_count and self._engine.last_wave_count.current_pattern:
            self._elliott_wave = self._engine.last_wave_count.current_pattern.current_wave_number
        else:
            self._elliott_wave = None

    @property
    def IsReady(self) -> bool:
        """Indicator is ready after warmup period."""
        return self._tick_count >= self._warmup_ticks

    @property
    def signal(self) -> float:
        """Combined trading signal [-1, 1]."""
        return self._signal

    @property
    def direction(self) -> str:
        """Signal direction: 'buy', 'sell', or 'neutral'."""
        return self._direction

    @property
    def confidence(self) -> float:
        """Signal confidence [0, 1]."""
        return self._confidence

    @property
    def entry_signal(self) -> bool:
        """True if entry conditions are met."""
        return self._entry_signal

    @property
    def exit_signal(self) -> bool:
        """True if exit conditions are met."""
        return self._exit_signal

    @property
    def position_size(self) -> float:
        """Recommended position size [0, 1]."""
        return self._position_size

    @property
    def regime(self) -> str:
        """Current market regime."""
        return self._regime

    @property
    def adx(self) -> float:
        """ADX indicator value."""
        return self._adx

    @property
    def rsi(self) -> float:
        """RSI indicator value."""
        return self._rsi

    @property
    def elliott_wave(self) -> Optional[int]:
        """Current Elliott wave number (1-5 or None)."""
        return self._elliott_wave

    def update_equity(self, equity: float) -> None:
        """Update equity for drawdown tracking."""
        self._engine.update_equity(equity)

    def get_full_signal(self) -> Dict[str, Any]:
        """Get complete signal dictionary."""
        return self._engine.get_trading_signal()

    def get_state_summary(self) -> Dict[str, Any]:
        """Get engine state summary."""
        return self._engine.get_state_summary()

    def reset(self) -> None:
        """Reset indicator state."""
        self._engine.reset()
        self._tick_count = 0
        self._signal = 0.0
        self._direction = "neutral"
        self._confidence = 0.0
        self._entry_signal = False
        self._exit_signal = False
        self._position_size = 0.0
