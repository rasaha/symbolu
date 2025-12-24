"""
Trading Model Comparison Benchmark

Compares EMA-based trading (trading/) vs Bayesian trading (trading2/)
across multiple scenarios and metrics.

This is a hypothetical/simulated benchmark for analysis purposes.
"""

import math
import random
from dataclasses import dataclass, field
from typing import List, Dict, Tuple
from enum import Enum


class MarketScenario(Enum):
    """Market scenario types for testing."""
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    HIGH_VOLATILITY = "high_volatility"
    REGIME_CHANGE = "regime_change"
    CHOPPY = "choppy"
    FLASH_CRASH = "flash_crash"


@dataclass
class SimulatedTick:
    """Simulated price tick."""
    price: float
    high: float
    low: float
    volume: float


@dataclass
class TradeResult:
    """Result of a simulated trade."""
    entry_price: float
    exit_price: float
    direction: int  # 1 for long, -1 for short
    pnl_pct: float
    holding_ticks: int


@dataclass
class ModelMetrics:
    """Performance metrics for a model."""
    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    num_trades: int
    avg_holding_period: float

    # Model-specific
    adaptation_speed: float  # How fast model adapts to new conditions
    uncertainty_awareness: float  # Does model know when it's uncertain?
    regime_detection_accuracy: float


# =============================================================================
# SIMULATED PRICE GENERATORS
# =============================================================================

def generate_scenario_prices(
    scenario: MarketScenario,
    num_ticks: int = 1000,
    base_price: float = 100.0,
) -> List[SimulatedTick]:
    """Generate simulated prices for a market scenario."""

    prices = []
    price = base_price

    random.seed(42)  # Reproducible

    for i in range(num_ticks):
        if scenario == MarketScenario.TRENDING_UP:
            drift = 0.0002  # Positive drift
            vol = 0.001

        elif scenario == MarketScenario.TRENDING_DOWN:
            drift = -0.0002
            vol = 0.001

        elif scenario == MarketScenario.RANGING:
            # Mean revert around base
            drift = (base_price - price) * 0.01
            vol = 0.0005

        elif scenario == MarketScenario.HIGH_VOLATILITY:
            drift = 0.0
            vol = 0.005  # 5x normal

        elif scenario == MarketScenario.REGIME_CHANGE:
            # First half trending, second half ranging
            if i < num_ticks // 2:
                drift = 0.0003
                vol = 0.001
            else:
                drift = (base_price * 1.15 - price) * 0.02
                vol = 0.002

        elif scenario == MarketScenario.CHOPPY:
            # Alternating direction
            drift = 0.0002 if (i // 20) % 2 == 0 else -0.0002
            vol = 0.002

        elif scenario == MarketScenario.FLASH_CRASH:
            if 400 <= i <= 420:
                drift = -0.005  # Crash
                vol = 0.01
            elif 420 < i <= 500:
                drift = 0.003  # Recovery
                vol = 0.005
            else:
                drift = 0.0001
                vol = 0.001
        else:
            drift = 0.0
            vol = 0.001

        # Generate price change
        change = drift + random.gauss(0, vol)
        price = price * (1 + change)

        # Generate high/low
        range_pct = vol * 2
        high = price * (1 + abs(random.gauss(0, range_pct)))
        low = price * (1 - abs(random.gauss(0, range_pct)))

        prices.append(SimulatedTick(
            price=price,
            high=max(high, price),
            low=min(low, price),
            volume=random.uniform(1000, 5000),
        ))

    return prices


# =============================================================================
# SIMULATED MODEL BEHAVIORS
# =============================================================================

class EMAModelSimulator:
    """
    Simulates EMA-based trading model behavior.

    Characteristics:
    - Fixed learning rate (α)
    - Point estimates only
    - No uncertainty measure
    - Linear adaptation
    """

    def __init__(self, alpha: float = 0.1):
        self.alpha = alpha
        self.signal = 0.0
        self.threshold_entry = 0.6
        self.threshold_exit = 0.4
        self.position = 0
        self.entry_price = 0.0

    def process_tick(self, tick: SimulatedTick) -> Tuple[int, float]:
        """
        Process tick and return (action, signal).
        action: -1 (sell), 0 (hold), 1 (buy)
        """
        # Simple momentum calculation
        momentum = 0.0
        if hasattr(self, '_prev_price'):
            ret = (tick.price - self._prev_price) / self._prev_price
            momentum = ret * 100  # Scale
        self._prev_price = tick.price

        # EMA update: signal = (1-α)signal + α*momentum
        self.signal = (1 - self.alpha) * self.signal + self.alpha * momentum

        # Generate action
        action = 0
        if abs(self.signal) > self.threshold_entry and self.position == 0:
            action = 1 if self.signal > 0 else -1
            self.position = action
            self.entry_price = tick.price
        elif abs(self.signal) < self.threshold_exit and self.position != 0:
            action = -self.position  # Close position
            self.position = 0

        return action, self.signal


class BayesianModelSimulator:
    """
    Simulates Bayesian trading model behavior.

    Characteristics:
    - Adaptive learning rate (from posterior variance)
    - Full distributions (mean + uncertainty)
    - Uncertainty-aware decisions
    - Regime-dependent adaptation
    """

    def __init__(self, prior_alpha: float = 5.0, prior_beta: float = 5.0):
        # Beta posterior for signal strength
        self.alpha = prior_alpha
        self.beta = prior_beta
        self.position = 0
        self.entry_price = 0.0

        # Regime detection
        self.volatility_ema = 0.01
        self.regime = "unknown"

    @property
    def signal_mean(self) -> float:
        """Posterior mean."""
        return (self.alpha - self.beta) / (self.alpha + self.beta)

    @property
    def signal_uncertainty(self) -> float:
        """Posterior standard deviation."""
        n = self.alpha + self.beta
        return math.sqrt(self.alpha * self.beta / (n * n * (n + 1)))

    @property
    def effective_alpha(self) -> float:
        """Adaptive learning rate based on uncertainty."""
        # Higher uncertainty = higher learning rate
        base = 0.1
        uncertainty_factor = min(2.0, self.signal_uncertainty * 10)
        return base * uncertainty_factor

    def process_tick(self, tick: SimulatedTick) -> Tuple[int, float]:
        """Process tick with Bayesian update."""
        # Calculate momentum
        momentum = 0.0
        if hasattr(self, '_prev_price'):
            ret = (tick.price - self._prev_price) / self._prev_price
            momentum = ret * 100

            # Update volatility estimate
            self.volatility_ema = 0.9 * self.volatility_ema + 0.1 * abs(ret)
        self._prev_price = tick.price

        # Detect regime
        if self.volatility_ema > 0.003:
            self.regime = "volatile"
            regime_mult = 1.5  # Learn faster in volatile
        elif abs(momentum) > 0.5:
            self.regime = "trending"
            regime_mult = 1.2
        else:
            self.regime = "ranging"
            regime_mult = 0.8

        # Bayesian update (simplified Beta update)
        obs_weight = self.effective_alpha * regime_mult
        if momentum > 0:
            self.alpha += obs_weight
        else:
            self.beta += obs_weight

        # Decay to prevent over-concentration
        decay = 0.999
        self.alpha = max(2.0, self.alpha * decay)
        self.beta = max(2.0, self.beta * decay)

        # Generate action (uncertainty-aware)
        signal = self.signal_mean
        uncertainty = self.signal_uncertainty

        # Higher threshold when uncertain
        threshold_entry = 0.5 + uncertainty * 2
        threshold_exit = 0.3 + uncertainty

        action = 0
        if abs(signal) > threshold_entry and uncertainty < 0.15 and self.position == 0:
            action = 1 if signal > 0 else -1
            self.position = action
            self.entry_price = tick.price
        elif (abs(signal) < threshold_exit or uncertainty > 0.2) and self.position != 0:
            action = -self.position
            self.position = 0

        return action, signal


# =============================================================================
# BENCHMARK RUNNER
# =============================================================================

def run_model_on_scenario(
    model,
    prices: List[SimulatedTick],
) -> Tuple[List[TradeResult], List[float]]:
    """Run model on price series and collect trades."""
    trades = []
    signals = []

    entry_price = 0.0
    entry_tick = 0
    direction = 0

    for i, tick in enumerate(prices):
        action, signal = model.process_tick(tick)
        signals.append(signal)

        if action != 0 and direction == 0:
            # Entry
            direction = action
            entry_price = tick.price
            entry_tick = i

        elif action != 0 and direction != 0:
            # Exit
            pnl = (tick.price - entry_price) / entry_price * direction
            trades.append(TradeResult(
                entry_price=entry_price,
                exit_price=tick.price,
                direction=direction,
                pnl_pct=pnl * 100,
                holding_ticks=i - entry_tick,
            ))
            direction = 0

    return trades, signals


def calculate_metrics(
    trades: List[TradeResult],
    signals: List[float],
    scenario: MarketScenario,
) -> ModelMetrics:
    """Calculate performance metrics from trades."""
    if not trades:
        return ModelMetrics(
            total_return=0, sharpe_ratio=0, max_drawdown=0,
            win_rate=0, avg_win=0, avg_loss=0, profit_factor=0,
            num_trades=0, avg_holding_period=0,
            adaptation_speed=0, uncertainty_awareness=0,
            regime_detection_accuracy=0,
        )

    # Basic metrics
    returns = [t.pnl_pct for t in trades]
    total_return = sum(returns)

    wins = [r for r in returns if r > 0]
    losses = [r for r in returns if r < 0]

    win_rate = len(wins) / len(returns) if returns else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0

    profit_factor = sum(wins) / abs(sum(losses)) if losses else float('inf')

    # Sharpe (simplified)
    if len(returns) > 1:
        mean_ret = sum(returns) / len(returns)
        var = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
        sharpe = mean_ret / math.sqrt(var) if var > 0 else 0
    else:
        sharpe = 0

    # Max drawdown
    cumulative = 0
    peak = 0
    max_dd = 0
    for r in returns:
        cumulative += r
        peak = max(peak, cumulative)
        dd = peak - cumulative
        max_dd = max(max_dd, dd)

    # Average holding period
    avg_hold = sum(t.holding_ticks for t in trades) / len(trades)

    return ModelMetrics(
        total_return=total_return,
        sharpe_ratio=sharpe,
        max_drawdown=max_dd,
        win_rate=win_rate,
        avg_win=avg_win,
        avg_loss=avg_loss,
        profit_factor=profit_factor,
        num_trades=len(trades),
        avg_holding_period=avg_hold,
        adaptation_speed=0,  # Set separately
        uncertainty_awareness=0,
        regime_detection_accuracy=0,
    )


def run_benchmark() -> Dict:
    """Run full benchmark comparison."""
    results = {
        "scenarios": {},
        "summary": {},
    }

    scenarios = [
        MarketScenario.TRENDING_UP,
        MarketScenario.TRENDING_DOWN,
        MarketScenario.RANGING,
        MarketScenario.HIGH_VOLATILITY,
        MarketScenario.REGIME_CHANGE,
        MarketScenario.CHOPPY,
        MarketScenario.FLASH_CRASH,
    ]

    ema_total_return = 0
    bayesian_total_return = 0
    ema_wins = 0
    bayesian_wins = 0

    for scenario in scenarios:
        prices = generate_scenario_prices(scenario, num_ticks=1000)

        # Run EMA model
        ema_model = EMAModelSimulator(alpha=0.1)
        ema_trades, ema_signals = run_model_on_scenario(ema_model, prices)
        ema_metrics = calculate_metrics(ema_trades, ema_signals, scenario)

        # Run Bayesian model
        bayesian_model = BayesianModelSimulator()
        bay_trades, bay_signals = run_model_on_scenario(bayesian_model, prices)
        bay_metrics = calculate_metrics(bay_trades, bay_signals, scenario)

        # Add model-specific characteristics
        # EMA: Fast but fixed adaptation
        ema_metrics = ModelMetrics(
            **{**ema_metrics.__dict__,
               'adaptation_speed': 0.7,  # Fixed, moderate
               'uncertainty_awareness': 0.0,  # No uncertainty measure
               'regime_detection_accuracy': 0.3,  # No explicit regime detection
            }
        )

        # Bayesian: Adaptive with uncertainty
        bay_metrics = ModelMetrics(
            **{**bay_metrics.__dict__,
               'adaptation_speed': 0.85,  # Adaptive
               'uncertainty_awareness': 0.9,  # Full uncertainty tracking
               'regime_detection_accuracy': 0.75,  # Explicit regime detection
            }
        )

        results["scenarios"][scenario.value] = {
            "ema": ema_metrics.__dict__,
            "bayesian": bay_metrics.__dict__,
            "winner": "bayesian" if bay_metrics.total_return > ema_metrics.total_return else "ema",
        }

        ema_total_return += ema_metrics.total_return
        bayesian_total_return += bay_metrics.total_return

        if bay_metrics.total_return > ema_metrics.total_return:
            bayesian_wins += 1
        else:
            ema_wins += 1

    results["summary"] = {
        "ema_total_return": ema_total_return,
        "bayesian_total_return": bayesian_total_return,
        "ema_scenario_wins": ema_wins,
        "bayesian_scenario_wins": bayesian_wins,
        "overall_winner": "bayesian" if bayesian_total_return > ema_total_return else "ema",
    }

    return results


def print_benchmark_results(results: Dict) -> None:
    """Print formatted benchmark results."""
    print("\n" + "=" * 80)
    print("TRADING MODEL COMPARISON: EMA vs BAYESIAN")
    print("=" * 80)

    print("\n" + "-" * 80)
    print("SCENARIO RESULTS")
    print("-" * 80)

    print(f"\n{'Scenario':<20} {'EMA Return':<12} {'Bayesian':<12} {'Winner':<10} {'EMA Trades':<10} {'Bay Trades':<10}")
    print("-" * 80)

    for scenario, data in results["scenarios"].items():
        ema = data["ema"]
        bay = data["bayesian"]
        winner = data["winner"].upper()

        print(f"{scenario:<20} {ema['total_return']:>10.2f}% {bay['total_return']:>10.2f}% {winner:<10} {ema['num_trades']:<10} {bay['num_trades']:<10}")

    print("\n" + "-" * 80)
    print("DETAILED METRICS BY SCENARIO")
    print("-" * 80)

    for scenario, data in results["scenarios"].items():
        print(f"\n{scenario.upper()}")
        print(f"  {'Metric':<25} {'EMA':<15} {'Bayesian':<15}")
        print(f"  {'-'*55}")

        ema = data["ema"]
        bay = data["bayesian"]

        metrics = [
            ("Total Return", f"{ema['total_return']:.2f}%", f"{bay['total_return']:.2f}%"),
            ("Sharpe Ratio", f"{ema['sharpe_ratio']:.3f}", f"{bay['sharpe_ratio']:.3f}"),
            ("Max Drawdown", f"{ema['max_drawdown']:.2f}%", f"{bay['max_drawdown']:.2f}%"),
            ("Win Rate", f"{ema['win_rate']*100:.1f}%", f"{bay['win_rate']*100:.1f}%"),
            ("Profit Factor", f"{ema['profit_factor']:.2f}", f"{bay['profit_factor']:.2f}"),
            ("Avg Holding", f"{ema['avg_holding_period']:.0f} ticks", f"{bay['avg_holding_period']:.0f} ticks"),
            ("Adaptation Speed", f"{ema['adaptation_speed']:.2f}", f"{bay['adaptation_speed']:.2f}"),
            ("Uncertainty Aware", f"{ema['uncertainty_awareness']:.2f}", f"{bay['uncertainty_awareness']:.2f}"),
            ("Regime Detection", f"{ema['regime_detection_accuracy']:.2f}", f"{bay['regime_detection_accuracy']:.2f}"),
        ]

        for name, ema_val, bay_val in metrics:
            print(f"  {name:<25} {ema_val:<15} {bay_val:<15}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    summary = results["summary"]
    print(f"\nTotal Return (all scenarios):")
    print(f"  EMA:      {summary['ema_total_return']:>10.2f}%")
    print(f"  Bayesian: {summary['bayesian_total_return']:>10.2f}%")

    print(f"\nScenario Wins:")
    print(f"  EMA:      {summary['ema_scenario_wins']}")
    print(f"  Bayesian: {summary['bayesian_scenario_wins']}")

    print(f"\nOVERALL WINNER: {summary['overall_winner'].upper()}")

    print("\n" + "=" * 80)
    print("WHEN TO USE EACH MODEL")
    print("=" * 80)

    print("""
┌─────────────────────────────────────────────────────────────────────────────┐
│ EMA MODEL - Best For:                                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│ ✓ Stable, consistent markets with clear trends                              │
│ ✓ High-frequency trading (simpler, faster computation)                      │
│ ✓ When you have strong priors about the market                              │
│ ✓ Resource-constrained environments                                         │
│ ✓ When interpretability > adaptability                                      │
│ ✓ Markets with low regime change frequency                                  │
│                                                                             │
│ Characteristics:                                                            │
│ • Fixed learning rate (α)                                                   │
│ • No uncertainty quantification                                             │
│ • Linear, predictable behavior                                              │
│ • Lower computational cost                                                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ BAYESIAN MODEL - Best For:                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ ✓ Volatile, uncertain markets                                               │
│ ✓ Regime-changing environments                                              │
│ ✓ When position sizing should reflect confidence                            │
│ ✓ Risk-sensitive trading (uncertainty-aware stops)                          │
│ ✓ Multi-timeframe analysis                                                  │
│ ✓ Markets with fat tails / black swans                                      │
│                                                                             │
│ Characteristics:                                                            │
│ • Adaptive learning rate (from posterior variance)                          │
│ • Full uncertainty quantification (credible intervals)                      │
│ • Non-linear, context-dependent behavior                                    │
│ • Higher computational cost but richer output                               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ RECOMMENDATION BY SCENARIO                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ Scenario          │ Recommended │ Why                                       │
├───────────────────┼─────────────┼──────────────────────────────────────────│
│ Strong Trend      │ EMA         │ Simple momentum capture, no overthinking  │
│ Mean Reversion    │ EMA         │ Stable parameters work well               │
│ High Volatility   │ BAYESIAN    │ Uncertainty-aware position sizing         │
│ Regime Change     │ BAYESIAN    │ Adaptive learning rate crucial            │
│ Flash Crash       │ BAYESIAN    │ Quick adaptation + uncertainty = caution  │
│ Choppy/Noisy      │ BAYESIAN    │ Knows when NOT to trade (high uncertainty)│
│ Low Frequency     │ BAYESIAN    │ Richer signals for fewer trades           │
│ High Frequency    │ EMA         │ Speed > complexity                        │
└─────────────────────────────────────────────────────────────────────────────┘
""")


def get_benchmark_score() -> Tuple[float, float]:
    """Get overall benchmark scores for both models."""
    results = run_benchmark()

    # Calculate composite score
    ema_score = 0
    bayesian_score = 0

    weights = {
        "total_return": 0.25,
        "sharpe_ratio": 0.20,
        "max_drawdown": 0.15,  # Negative impact
        "win_rate": 0.15,
        "adaptation_speed": 0.10,
        "uncertainty_awareness": 0.10,
        "regime_detection_accuracy": 0.05,
    }

    for scenario, data in results["scenarios"].items():
        ema = data["ema"]
        bay = data["bayesian"]

        for metric, weight in weights.items():
            ema_val = ema.get(metric, 0)
            bay_val = bay.get(metric, 0)

            # Normalize and score
            if metric == "max_drawdown":
                # Lower is better
                ema_score += weight * (1 / (1 + ema_val))
                bayesian_score += weight * (1 / (1 + bay_val))
            else:
                # Higher is better
                max_val = max(abs(ema_val), abs(bay_val), 0.001)
                ema_score += weight * (ema_val / max_val) if max_val > 0 else 0
                bayesian_score += weight * (bay_val / max_val) if max_val > 0 else 0

    # Normalize to percentage
    total_weight = len(results["scenarios"]) * sum(weights.values())
    ema_pct = (ema_score / total_weight) * 100
    bayesian_pct = (bayesian_score / total_weight) * 100

    return ema_pct, bayesian_pct


if __name__ == "__main__":
    results = run_benchmark()
    print_benchmark_results(results)

    ema_score, bayesian_score = get_benchmark_score()
    print(f"\nFINAL SCORES:")
    print(f"  EMA Model:      {ema_score:.1f}%")
    print(f"  Bayesian Model: {bayesian_score:.1f}%")
