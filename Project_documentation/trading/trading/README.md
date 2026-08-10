# SymbolU Trading Framework (Experimental)

**Tick-based trading system built on v2.7 State Evolution concepts.**

> ⚠️ **EXPERIMENTAL**: This is a hobby project exploring cross-domain application of SymbolU concepts to trading. Not for production use.

## Overview

This framework adapts the v2.7 Deterministic State Evolution Layer for trading, using tick-based (not time-based) analysis. It's designed for QuantConnect integration.

### Core Concepts from v2.7

| v2.7 Concept | Trading Equivalent |
|--------------|-------------------|
| State Register (θ) | Risk parameters, thresholds, position sizing |
| EMA Update: θ_{t+1} = (1-α)θ_t + αθ* | Adaptive state evolution |
| Tier-specific α | Trading timeframes (scalper→position) |
| Bounded evolution | Position limits, drawdown caps |
| Utility function | Risk-adjusted signal scoring |
| Audit trail | Trade journal, compliance log |

### Trading Extensions

Additional logic not in v2.7:

1. **Asymmetric Learning** - Learn faster from losses (α×2) than gains (α×0.5)
2. **Volatility Scaling** - Reduce signals in high volatility
3. **Order Flow Imbalance** - Buy/sell pressure detection
4. **Regime Detection** - Trending/ranging/crisis modes
5. **Circuit Breakers** - Halt on max drawdown
6. **Tick-based Processing** - Not time-bar based

## Architecture

```
trading/
├── core/
│   ├── state_register.py    # TradingStateRegister (immutable state)
│   ├── observables.py       # TickObservables (market signals)
│   ├── utility.py           # TradingUtility (risk-adjusted scoring)
│   ├── evolution_engine.py  # TradingEvolutionEngine (state updates)
│   └── config.py            # TradingConfig, AlphaConfig, RiskConfig
├── tick_processor/
│   ├── aggregator.py        # TickAggregator (raw tick → signals)
│   ├── imbalance.py         # OrderFlowImbalance (buy/sell pressure)
│   └── volatility.py        # TickVolatility (vol estimation)
└── quantconnect/
    ├── algorithm.py         # TickEvolutionAlgorithm (base class)
    └── indicator.py         # TickEvolutionIndicator (custom indicator)
```

## Quick Start (QuantConnect)

### 1. Basic Algorithm

```python
from trading.quantconnect import TickEvolutionAlgorithm

class MyAlgorithm(TickEvolutionAlgorithm):
    def Initialize(self):
        super().Initialize()

        # Setup
        self.SetStartDate(2024, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)

        # Configure symbols and tier
        self.configure_symbols(["SPY", "QQQ"])
        self.configure_tier("swing", "moderate")  # 14-tick half-life

    def on_signal(self, symbol, signal, action):
        """Override for custom position management."""
        engine = self.get_engine(symbol)
        scalar = engine.state.position_scalar

        if action == "entry_long":
            self.SetHoldings(symbol, 0.3 * scalar)
        elif action == "entry_short":
            self.SetHoldings(symbol, -0.3 * scalar)
        elif action == "exit":
            self.Liquidate(symbol)
```

### 2. Using the Indicator

```python
from AlgorithmImports import *
from trading.quantconnect import TickEvolutionIndicator

class MyAlgorithm(QCAlgorithm):
    def Initialize(self):
        self.spy = self.AddEquity("SPY", Resolution.Tick).Symbol

        # Create indicator
        self.evolution = TickEvolutionIndicator(
            "SPY_EVO",
            tier="daytrader",
            warmup_ticks=100
        )
        self.RegisterIndicator(self.spy, self.evolution, Resolution.Tick)

    def OnData(self, data):
        if not self.evolution.IsReady:
            return

        # Access indicator values
        signal = self.evolution.signal
        utility = self.evolution.utility
        regime = self.evolution.regime

        # Check for signals
        should_enter, direction = self.evolution.should_enter()
        if should_enter:
            self.SetHoldings(self.spy, 0.5 if direction == "long" else -0.5)
```

## Trading Tiers

| Tier | Alpha (α) | Half-Life | Use Case |
|------|-----------|-----------|----------|
| scalper | 0.20 | ~3 ticks | High-frequency, quick adaptation |
| daytrader | 0.10 | ~7 ticks | Intraday, medium adaptation |
| swing | 0.05 | ~14 ticks | Multi-day, slower adaptation |
| position | 0.02 | ~35 ticks | Long-term, stable parameters |

Half-life = number of ticks for 50% decay of old information.

## State Register

The `TradingStateRegister` contains:

```python
@dataclass(frozen=True)
class TradingStateRegister:
    # Thresholds (entry/exit signal levels)
    tau_entry: float = 0.6       # [0.1, 0.9]
    tau_exit: float = 0.4        # [0.1, 0.9]

    # Signal weights (must sum to 1)
    w_momentum: float = 0.4      # Trend-following weight
    w_reversion: float = 0.4     # Mean-reversion weight
    w_noise: float = 0.2         # Noise filtering weight

    # Risk management
    position_scalar: float = 1.0  # [0, 1] position sizing
    volatility_anchor: float = 0.02  # Reference volatility
    regime: str = "unknown"       # trending/ranging/crisis
    drawdown: float = 0.0         # Current drawdown [0, 1]
```

## Observables (Tick Signals)

```python
@dataclass(frozen=True)
class TickObservables:
    # Core signals [-1, 1]
    momentum: float         # Directional pressure
    mean_reversion: float   # Price vs fair value
    noise_level: float      # Market noise [0, 1]

    # Additional signals
    tick_volatility: float  # Current vol / anchor vol
    order_imbalance: float  # Buy/sell pressure [-1, 1]
    spread_normalized: float # Current spread / avg spread
    tick_intensity: float   # Ticks/sec / avg ticks/sec
```

## Utility Function

Trading utility with asymmetric treatment:

```
U = signal_contribution
    - λ_vol × volatility_penalty
    - λ_dd × drawdown_penalty
    - λ_spread × spread_penalty
    - λ_noise × noise_penalty
    + regime_adjustment
```

Where signal_contribution is weighted by state and adjusted for recent P&L (asymmetric learning).

## Risk Management

### Circuit Breakers

```python
risk_config = RiskConfig(
    max_drawdown=0.10,        # 10% max → halt trading
    warning_drawdown=0.05,    # 5% → reduce position
    crisis_drawdown=0.08,     # 8% → crisis mode
    crisis_position_scalar=0.25,  # 25% of normal size
)
```

### Regime Handling

- **trending**: Boost momentum signals
- **ranging**: Boost mean-reversion signals
- **crisis**: Heavily dampen all signals, reduce position

## v2.7 Formula Reference

Core EMA update (same as v2.7):
```
θ_{t+1} = (1 - α) × θ_t + α × θ*
```

Half-life:
```
t_½ = ln(0.5) / ln(1 - α) ≈ 0.693 / α
```

Asymmetric alpha (trading extension):
```
α_effective = α × 2.0  if P&L < 0  (learn fast from losses)
α_effective = α × 0.5  if P&L > 0  (learn slow from gains)
```

## Differences from v2.7

| Aspect | v2.7 (Original) | Trading Extension |
|--------|-----------------|-------------------|
| Time basis | Request-based | Tick-based |
| Observables | S, R, T, H, C, F | Momentum, reversion, imbalance |
| Learning | Symmetric α | Asymmetric (loss/gain) |
| Risk | Token-based | Drawdown-based |
| State persistence | Per-user | Per-symbol |
| Circuit breakers | None | Max drawdown halt |

## Local Development

For testing without QuantConnect:

```python
from trading.core import TradingEvolutionEngine, TradingConfig
from trading.tick_processor import TickAggregator, TickData

# Create engine
config = TradingConfig.for_tier("swing")
engine = TradingEvolutionEngine(config=config)

# Create aggregator
aggregator = TickAggregator()

# Simulate ticks
for price, volume in tick_stream:
    tick = TickData(price=price, volume=volume, bid=0, ask=0, timestamp_ns=0)
    signals = aggregator.process_tick(tick)
    obs = aggregator.to_observables(signals)

    state, utility, action = engine.process_tick(obs)

    if action != "update":
        print(f"Action: {action}, Utility: {utility.utility:.3f}")
```

## Future Enhancements

- [ ] Multi-timeframe fusion (combine multiple α values)
- [ ] Correlation-aware portfolio management
- [ ] Transaction cost modeling
- [ ] Slippage estimation
- [ ] More sophisticated regime detection
- [ ] Backtesting harness for local development

## License

Experimental / Personal Use Only.
