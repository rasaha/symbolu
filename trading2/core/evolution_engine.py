"""
Bayesian Evolution Engine

Core state evolution engine using Bayesian posterior updates.

Key difference from EMA engine:
- EMA: θ_{t+1} = (1-α)θ_t + αx (fixed learning rate)
- Bayesian: P(θ|x) ∝ P(x|θ)P(θ) (adaptive, uncertainty-aware)

The Bayesian approach:
1. Maintains full posterior distributions (not point estimates)
2. Naturally adapts learning rate based on uncertainty
3. Provides credible intervals for decision making
4. Supports regime-dependent likelihood weighting
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from collections import deque
import math

from trading2.core.config import (
    BayesianConfig,
    RegimeType,
    TradingTier,
)
from trading2.core.state_register import BayesianStateRegister, BayesianPosterior
from trading2.core.observables import BayesianObservables
from trading2.core.utility import BayesianUtility, UtilityResult
from trading2.analysis.elliott_wave import ElliottWaveAnalyzer, WaveCount
from trading2.analysis.indicators import IndicatorSuite, CompositeSignal
from trading2.analysis.model_selector import ModelSelector, ModelRecommendation, ModelType


@dataclass
class EngineAuditEntry:
    """Single audit log entry."""
    tick: int
    utility: float
    signal: float
    regime: str
    drawdown: float
    position_scalar: float
    elliott_wave: Optional[int]
    indicator_consensus: str
    action: str


@dataclass
class BayesianEvolutionEngine:
    """
    Bayesian state evolution engine for trading.

    Processes ticks and updates posterior distributions
    based on observed market conditions.
    """
    config: BayesianConfig
    state: BayesianStateRegister = field(default=None)

    # Components
    utility_calc: BayesianUtility = field(default=None)
    elliott_analyzer: ElliottWaveAnalyzer = field(default=None)
    indicators: IndicatorSuite = field(default=None)
    model_selector: ModelSelector = field(default=None)

    # Runtime state
    tick_count: int = 0
    last_utility: Optional[UtilityResult] = None
    last_wave_count: Optional[WaveCount] = None
    last_indicator_signal: Optional[CompositeSignal] = None
    last_model_recommendation: Optional[ModelRecommendation] = None

    # Audit trail
    audit_log: List[EngineAuditEntry] = field(default_factory=list)
    _audit_interval: int = 100

    # Callbacks
    on_entry_signal: Optional[Callable[[float, float], None]] = None
    on_exit_signal: Optional[Callable[[float], None]] = None

    def __post_init__(self):
        """Initialize components."""
        if self.state is None:
            self.state = BayesianStateRegister.initialize(self.config.prior)

        if self.utility_calc is None:
            self.utility_calc = BayesianUtility(self.config.risk)

        if self.elliott_analyzer is None:
            self.elliott_analyzer = ElliottWaveAnalyzer(
                min_wave_size=self.config.elliott.min_wave_size,
                pivot_lookback=self.config.elliott.pivot_lookback,
                wave_lookback=self.config.elliott.wave_lookback,
            )

        if self.indicators is None:
            self.indicators = IndicatorSuite()

        if self.model_selector is None:
            self.model_selector = ModelSelector()

        self._audit_interval = self.config.audit_interval

    @classmethod
    def create(
        cls,
        tier: TradingTier = TradingTier.SWING,
        **config_overrides,
    ) -> "BayesianEvolutionEngine":
        """
        Create engine with tier-specific configuration.

        Args:
            tier: Trading tier (scalper, daytrader, swing, position)
            **config_overrides: Override specific config values

        Returns:
            Configured BayesianEvolutionEngine
        """
        config = BayesianConfig.from_tier(tier)
        return cls(config=config)

    def process_tick(
        self,
        price: float,
        high: Optional[float] = None,
        low: Optional[float] = None,
        volume: Optional[float] = None,
        vwap: Optional[float] = None,
        **extra_data,
    ) -> UtilityResult:
        """
        Process a single tick and update state.

        Args:
            price: Current price
            high: High price (uses price if not provided)
            low: Low price (uses price if not provided)
            volume: Tick volume
            vwap: Volume-weighted average price
            **extra_data: Additional tick data

        Returns:
            UtilityResult with trading signals
        """
        self.tick_count += 1
        high = high or price
        low = low or price
        vwap = vwap or price

        # 1. Update technical indicators
        indicator_signal = self.indicators.update(price, high, low)
        self.last_indicator_signal = indicator_signal

        # 1.5. Update model selector with ADX
        adx_value = self.indicators.adx.adx
        self.last_model_recommendation = self.model_selector.update(price, adx_value)

        # 2. Update Elliott Wave analysis
        wave_count = self.elliott_analyzer.process_bar(price, high, low)
        self.last_wave_count = wave_count

        # 3. Build observables from all sources
        obs = self._build_observables(
            price=price,
            vwap=vwap,
            indicator_signal=indicator_signal,
            wave_count=wave_count,
            **extra_data,
        )

        # 4. Detect regime
        regime = self.utility_calc.detect_regime(obs)
        self.state = self.state.with_regime(regime)

        # 5. Compute utility
        utility_result = self.utility_calc.compute_utility(obs, self.state)
        self.last_utility = utility_result

        # 6. Perform Bayesian update
        self._perform_bayesian_update(obs, utility_result)

        # 7. Update wave state
        if wave_count.current_pattern:
            self.state = self.state.with_wave(
                wave=wave_count.current_pattern.current_wave_number,
                confidence=wave_count.current_pattern.confidence,
            )

        # 8. Handle signals
        self._handle_signals(utility_result, price)

        # 9. Check circuit breakers
        self._check_circuit_breakers()

        # 10. Audit logging
        if self.config.audit_enabled and self.tick_count % self._audit_interval == 0:
            self._log_audit(utility_result, indicator_signal)

        # 11. Apply decay to prevent over-concentration
        if self.tick_count % 100 == 0:
            self.state = self.state.decay(0.999)

        return utility_result

    def _build_observables(
        self,
        price: float,
        vwap: float,
        indicator_signal: CompositeSignal,
        wave_count: WaveCount,
        **extra_data,
    ) -> BayesianObservables:
        """Build observables from indicator and wave data."""
        # Extract momentum from indicators
        rsi_signal = next(
            (s for s in indicator_signal.signals if s.name == "RSI"),
            None
        )
        momentum = 0.0
        if rsi_signal:
            # Map RSI (0-100) to momentum (-1, 1)
            momentum = (rsi_signal.value - 50) / 50

        # Order imbalance from indicator net signal
        order_imbalance = indicator_signal.net_signal

        # Volatility from ATR
        atr_percent = self.indicators.atr.atr_percent
        volatility_ratio = atr_percent / 0.015 if atr_percent > 0 else 1.0  # Normalized to 1.5% baseline

        # Noise from indicator disagreement
        noise = 1.0 - indicator_signal.confidence

        # Elliott wave signal
        elliott_signal = wave_count.signal
        elliott_confidence = wave_count.signal_confidence
        current_wave = None
        if wave_count.current_pattern:
            current_wave = wave_count.current_pattern.current_wave_number

        return BayesianObservables.from_tick_data(
            price=price,
            vwap=vwap,
            momentum=momentum,
            order_imbalance=order_imbalance,
            volatility_ratio=volatility_ratio,
            spread_ratio=extra_data.get('spread_ratio', 1.0),
            noise=noise,
            elliott_signal=elliott_signal,
            elliott_confidence=elliott_confidence,
            current_wave=current_wave,
        )

    def _perform_bayesian_update(
        self,
        obs: BayesianObservables,
        utility: UtilityResult,
    ) -> None:
        """
        Perform Bayesian posterior updates based on observations.

        Updates each parameter's posterior based on:
        1. The observation's likelihood
        2. Regime-adjusted observation weight
        3. Asymmetric gain/loss multiplier
        """
        # Get regime-adjusted observation weight
        base_weight = self.config.likelihood.get_adjusted_weight(self.state.regime)

        # Apply asymmetric multiplier if enabled
        if self.config.asymmetric_enabled:
            # Determine if recent PnL was positive or negative
            pnl_direction = utility.utility  # Positive utility = gains

            if pnl_direction < 0:
                weight = base_weight * self.config.loss_multiplier
            elif pnl_direction > 0:
                weight = base_weight * self.config.gain_multiplier
            else:
                weight = base_weight
        else:
            weight = base_weight

        # Get observation targets from observables
        likelihood_obs = obs.to_likelihood_observation()

        # Update each posterior
        for param_name, (observation, obs_weight) in likelihood_obs.items():
            combined_weight = weight * obs_weight
            self.state = self.state.with_posterior_update(
                param=param_name,
                observation=observation,
                weight=combined_weight,
            )

    def _handle_signals(self, utility: UtilityResult, price: float) -> None:
        """Handle entry/exit signals from utility result."""
        if utility.entry_signal and self.on_entry_signal:
            direction = 1.0 if utility.utility > 0 else -1.0
            self.on_entry_signal(direction, utility.position_size)

        elif utility.exit_signal and self.on_exit_signal:
            self.on_exit_signal(price)

    def _check_circuit_breakers(self) -> None:
        """Check and handle circuit breaker conditions."""
        if not self.config.risk.circuit_break_enabled:
            return

        # Crisis mode check
        if self.state.drawdown >= self.config.risk.crisis_drawdown:
            self.state = self.state.with_regime(RegimeType.CRISIS)

            # Force position reduction
            crisis_scalar = self.config.risk.crisis_position_scalar
            self.state = self.state.with_posterior_update(
                "position_scalar",
                crisis_scalar,
                weight=2.0,  # Strong update
            )

        # Full circuit break
        if self.state.drawdown >= self.config.risk.max_drawdown:
            # Reset to conservative state
            self.state = BayesianStateRegister.initialize(self.config.prior)
            self.state = self.state.with_regime(RegimeType.CRISIS)

    def _log_audit(
        self,
        utility: UtilityResult,
        indicators: CompositeSignal,
    ) -> None:
        """Log audit entry."""
        entry = EngineAuditEntry(
            tick=self.tick_count,
            utility=utility.utility,
            signal=utility.signal_utility,
            regime=self.state.regime.value,
            drawdown=self.state.drawdown,
            position_scalar=self.state.position_scalar,
            elliott_wave=self.state.current_wave,
            indicator_consensus=indicators.consensus.value,
            action="entry" if utility.entry_signal else ("exit" if utility.exit_signal else "hold"),
        )
        self.audit_log.append(entry)

        # Limit audit log size
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-5000:]

    def update_equity(self, equity: float) -> None:
        """Update equity for drawdown tracking."""
        self.state = self.state.with_equity(equity)

    def get_state_summary(self) -> Dict[str, Any]:
        """Get current state summary."""
        estimates = self.state.posterior.get_point_estimates()
        uncertainties = self.state.posterior.get_uncertainties()

        return {
            "tick_count": self.tick_count,
            "regime": self.state.regime.value,
            "drawdown": self.state.drawdown,
            "estimates": estimates,
            "uncertainties": uncertainties,
            "total_uncertainty": self.state.total_uncertainty,
            "current_wave": self.state.current_wave,
            "wave_confidence": self.state.wave_confidence,
            "last_utility": self.last_utility.utility if self.last_utility else None,
            "indicator_consensus": self.last_indicator_signal.consensus.value if self.last_indicator_signal else None,
            "model_recommendation": self.last_model_recommendation.model.value if self.last_model_recommendation else None,
            "hurst": self.last_model_recommendation.hurst if self.last_model_recommendation else 0.5,
        }

    def get_trading_signal(self) -> Dict[str, Any]:
        """
        Get current trading signal with probability scores.

        Returns comprehensive signal information for trading decisions.
        """
        if not self.last_utility or not self.last_indicator_signal:
            return {
                "signal": 0.0,
                "direction": "neutral",
                "confidence": 0.0,
                "should_trade": False,
            }

        utility = self.last_utility
        indicators = self.last_indicator_signal

        # Combine signals
        bayesian_signal = utility.utility
        indicator_signal = indicators.net_signal
        elliott_signal = self.last_wave_count.signal if self.last_wave_count else 0.0

        # Weighted combination
        combined_signal = (
            0.4 * bayesian_signal +
            0.35 * indicator_signal +
            0.25 * elliott_signal
        )

        # Direction
        if combined_signal > 0.2:
            direction = "buy"
        elif combined_signal < -0.2:
            direction = "sell"
        else:
            direction = "neutral"

        # Confidence from indicator agreement and uncertainty
        confidence = indicators.confidence * (1.0 - utility.uncertainty_penalty)

        return {
            "signal": combined_signal,
            "direction": direction,
            "confidence": confidence,
            "should_trade": utility.should_trade,
            "bayesian_signal": bayesian_signal,
            "indicator_signal": indicator_signal,
            "elliott_signal": elliott_signal,
            "position_size": utility.position_size,
            "entry": utility.entry_signal,
            "exit": utility.exit_signal,
            "regime": self.state.regime.value,
            "indicators": {
                "buy_score": indicators.buy_score,
                "sell_score": indicators.sell_score,
                "consensus": indicators.consensus.value,
            },
            "model_selection": self._get_model_selection_info(),
        }

    def _get_model_selection_info(self) -> Dict[str, Any]:
        """Get model selection information."""
        if not self.last_model_recommendation:
            return {
                "recommended_model": "bayesian",
                "confidence": 0.5,
                "hurst": 0.5,
                "adx": 0.0,
                "volatility_ratio": 1.0,
                "autocorrelation": 0.0,
                "reason": "Insufficient data",
            }

        rec = self.last_model_recommendation
        return {
            "recommended_model": rec.model.value,
            "confidence": rec.confidence,
            "hurst": rec.hurst,
            "adx": rec.adx,
            "volatility_ratio": rec.volatility_ratio,
            "autocorrelation": rec.autocorrelation,
            "reason": rec.reason,
            "should_trade": rec.should_trade,
        }

    def reset(self) -> None:
        """Reset engine to initial state."""
        self.state = BayesianStateRegister.initialize(self.config.prior)
        self.elliott_analyzer.reset()
        self.indicators.reset()
        self.model_selector.reset()
        self.tick_count = 0
        self.last_utility = None
        self.last_wave_count = None
        self.last_indicator_signal = None
        self.last_model_recommendation = None
        self.audit_log.clear()


# Factory functions

def create_bayesian_engine(
    tier: str = "swing",
    asymmetric: bool = True,
) -> BayesianEvolutionEngine:
    """
    Create Bayesian evolution engine.

    Args:
        tier: Trading tier ("scalper", "daytrader", "swing", "position")
        asymmetric: Enable asymmetric updates (learn faster from losses)

    Returns:
        Configured BayesianEvolutionEngine
    """
    tier_map = {
        "scalper": TradingTier.SCALPER,
        "daytrader": TradingTier.DAYTRADER,
        "swing": TradingTier.SWING,
        "position": TradingTier.POSITION,
    }

    trading_tier = tier_map.get(tier.lower(), TradingTier.SWING)
    config = BayesianConfig.from_tier(trading_tier)
    config.asymmetric_enabled = asymmetric

    return BayesianEvolutionEngine(config=config)
