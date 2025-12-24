# SymbolU State Evolution - Pine Script v6

TradingView indicators converted from the QuantConnect trading module.

## Overview

This is a Pine Script v6 conversion of the SymbolU State Evolution trading system originally built for QuantConnect. The system uses adaptive state evolution with EMA blending to generate trading signals.

## Indicators

### 1. SymbolU State Evolution (Main Overlay)

**File:** `symbolu_state_evolution.pine`

Main overlay indicator that displays:
- Entry/exit signal arrows
- Regime background coloring
- Comprehensive signal table with probabilities and recommendations
- Real-time state evolution

### 2. SymbolU Oscillator (Companion Panel)

**File:** `symbolu_oscillator.pine`

Separate pane oscillator showing:
- Signal strength (-100 to +100)
- Probability view
- Utility function
- Component breakdown (momentum, reversion, imbalance)
- Confidence bands

## Installation

1. Open TradingView
2. Go to Pine Editor
3. Copy the content of the `.pine` file
4. Click "Add to Chart"

## Configuration

### Trading Tiers

| Tier | Alpha (α) | Half-Life | Use Case |
|------|-----------|-----------|----------|
| Scalper | 0.20 | ~3 bars | Very fast adaptation, intraday |
| Daytrader | 0.10 | ~7 bars | Medium adaptation, daily |
| Swing | 0.05 | ~14 bars | Moderate adaptation, multi-day |
| Position | 0.02 | ~35 bars | Slow adaptation, weeks/months |

### Risk Profiles

| Profile | Max Drawdown | Warning DD | Crisis DD | Crisis Position |
|---------|--------------|------------|-----------|-----------------|
| Conservative | 5% | 2% | 4% | 10% |
| Moderate | 10% | 5% | 8% | 25% |
| Aggressive | 20% | 10% | 15% | 50% |

## Key Concepts

### State Evolution

The core formula from v2.7:
```
θ_{t+1} = (1 - α) · θ_t + α · θ*
```

Where:
- `θ_t` = Current state
- `θ*` = Target state (from current market conditions)
- `α` = Learning rate (from tier selection)

### Observables

Adapted from tick-based to bar-based:

| Observable | Description | Range |
|------------|-------------|-------|
| Momentum | Directional pressure from price change | [-1, 1] |
| Mean Reversion | Deviation from fair value (VWAP/EMA) | [-1, 1] |
| Noise Level | Market microstructure noise | [0, 1] |
| Volatility Ratio | Current ATR / Average ATR | [0.01, 100] |
| Order Imbalance | Estimated buy/sell pressure | [-1, 1] |

### Utility Function

```
U = signal_contribution - λ_vol·volatility - λ_dd·drawdown - λ_spread·spread - λ_noise·noise + regime_adjustment
```

### Regime Detection

| Regime | Condition | Effect |
|--------|-----------|--------|
| Trending | High momentum + high intensity | Boost momentum signals |
| Ranging | High reversion + low intensity | Boost mean reversion |
| Crisis | Vol ratio > 2.5 | Dampen all signals -50% |
| Unknown | Default | No adjustment |

### Recommendations

| Level | Probability | Confidence | Action |
|-------|-------------|------------|--------|
| STRONG BUY | >75% bullish | >70% | High conviction long |
| BUY | >60% bullish | >60% | Moderate long |
| HOLD | <50% either | <50% | No action |
| SELL | >60% bearish | >60% | Moderate short |
| STRONG SELL | >75% bearish | >70% | High conviction short |

## Signal Table Fields

| Field | Description |
|-------|-------------|
| Tier | Selected trading tier and alpha value |
| Risk Profile | Selected risk management profile |
| Regime | Current detected market regime |
| Bullish Prob | Probability of upward movement (0-100%) |
| Bearish Prob | Probability of downward movement (0-100%) |
| Confidence | Signal confidence level (0-100%) |
| Recommendation | Trading recommendation |
| Entry Score | Entry attractiveness (0-100%) |
| Exit Score | Exit urgency (0-100%) |
| Risk/Reward | Expected risk-reward ratio |
| Kelly % | Optimal position size (Kelly criterion) |
| Utility | Risk-adjusted utility value |
| Signal | Final composite signal |
| Position Scalar | Position sizing factor |
| Status | ACTIVE, CRISIS, or HALTED |

## Alerts

Available alerts:
- Long Entry Signal
- Short Entry Signal
- Exit Signal
- Strong Buy
- Strong Sell
- Crisis Mode Activation

## Differences from QuantConnect Version

| Feature | QuantConnect | Pine Script |
|---------|--------------|-------------|
| Data | Tick-based | Bar-based |
| Volume Analysis | Actual tick volume | Estimated from OHLC |
| Order Flow | Real order imbalance | Estimated from close position |
| Execution | Live trading | Signals only |
| State Persistence | Full session | Per-bar |

## Best Practices

1. **Timeframe Selection**
   - Scalper tier: 1-5 minute charts
   - Daytrader tier: 15-60 minute charts
   - Swing tier: 4H-Daily charts
   - Position tier: Daily-Weekly charts

2. **Confirmation**
   - Use both main overlay and oscillator together
   - Wait for high confidence (>70%) entries
   - Respect regime context

3. **Risk Management**
   - Follow position scalar recommendations
   - Reduce size in crisis mode
   - Exit when exit score >50%

## Version History

- **v1.0** - Initial conversion from QuantConnect module
  - Full state evolution engine
  - All observables adapted for bar data
  - Utility function with asymmetric learning
  - Probability scoring and recommendations
  - Regime detection
  - Visual display with signal table
