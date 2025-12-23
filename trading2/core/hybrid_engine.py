"""
Hybrid Evolution Engine

Merges EMA and Bayesian trading models into a single adaptive system
that automatically switches between them based on market regime.

Model Selection Logic:
- Uses Hurst Exponent, ADX, Volatility Ratio, and Autocorrelation
- EMA activated when: H > 0.55, ADX > 25, low volatility
- Bayesian activated when: H < 0.45, ADX < 20, high volatility

The engine maintains both models running in parallel and uses the
appropriate one for signal generation based on current conditions.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Callable, List
from enum import Enum

from trading2.core.config import BayesianConfig, TradingTier, RegimeType
from trading2.core.state_register import BayesianStateRegister
from trading2.core.utility import BayesianUtility, UtilityResult
from trading2.core.observables import BayesianObservables
from trading2.analysis.elliott_wave import ElliottWaveAnalyzer, WaveCount
from trading2.analysis.indicators import IndicatorSuite, CompositeSignal
from trading2.analysis.model_selector import ModelSelector, ModelType, ModelRecommendation
from trading2.analysis.volume_profile import VolumeProfile, VolumeProfileResult


class ActiveModel(Enum):
    """Currently active model."""
    EMA = "ema"
    BAYESIAN = "bayesian"
    BLENDED = "blended"  # Use weighted combination of both


@dataclass
class EMAState:
    """Simple EMA-based state tracker."""
    # EMA values for key parameters
    momentum_ema: float = 0.0
    volatility_ema: float = 1.0
    signal_ema: float = 0.0
    position_scalar_ema: float = 0.5

    # EMA alpha values (learning rate)
    fast_alpha: float = 0.1  # For quick-responding metrics
    slow_alpha: float = 0.02  # For slow-responding metrics

    # Signal thresholds
    entry_threshold: float = 0.3
    exit_threshold: float = 0.1

    def update(
        self,
        momentum: float,
        volatility: float,
        signal: float,
    ) -> None:
        """Update EMA values with new observations."""
        self.momentum_ema = self._ema(self.momentum_ema, momentum, self.fast_alpha)
        self.volatility_ema = self._ema(self.volatility_ema, volatility, self.slow_alpha)
        self.signal_ema = self._ema(self.signal_ema, signal, self.fast_alpha)

        # Adjust position scalar based on volatility
        target_scalar = 1.0 / max(0.5, self.volatility_ema)
        target_scalar = max(0.25, min(1.0, target_scalar))
        self.position_scalar_ema = self._ema(
            self.position_scalar_ema, target_scalar, self.slow_alpha
        )

    def _ema(self, current: float, observation: float, alpha: float) -> float:
        """Exponential moving average update."""
        return (1 - alpha) * current + alpha * observation

    def get_signal(self) -> float:
        """Get current trading signal [-1, 1]."""
        return max(-1.0, min(1.0, self.signal_ema))

    def get_entry_signal(self) -> bool:
        """Check if entry conditions met."""
        return abs(self.signal_ema) >= self.entry_threshold

    def get_exit_signal(self) -> bool:
        """Check if exit conditions met."""
        return abs(self.signal_ema) < self.exit_threshold

    def reset(self) -> None:
        """Reset to initial state."""
        self.momentum_ema = 0.0
        self.volatility_ema = 1.0
        self.signal_ema = 0.0
        self.position_scalar_ema = 0.5


@dataclass
class HybridEvolutionEngine:
    """
    Hybrid trading engine that adapts between EMA and Bayesian models.

    Key Features:
    - Runs both EMA and Bayesian models in parallel
    - Uses objective indicators (Hurst, ADX, etc.) to select active model
    - Smooth transitions with optional blending period
    - Unified signal output regardless of active model
    """
    config: BayesianConfig

    # Bayesian components (from evolution_engine)
    bayesian_state: BayesianStateRegister = field(default=None)
    utility_calc: BayesianUtility = field(default=None)

    # EMA components
    ema_state: EMAState = field(default=None)

    # Shared components
    elliott_analyzer: ElliottWaveAnalyzer = field(default=None)
    indicators: IndicatorSuite = field(default=None)
    model_selector: ModelSelector = field(default=None)
    volume_profile: VolumeProfile = field(default=None)

    # Runtime state
    tick_count: int = 0
    active_model: ActiveModel = ActiveModel.BAYESIAN  # Default to Bayesian (more robust)
    blend_weight: float = 0.0  # 0 = pure Bayesian, 1 = pure EMA

    # Transition tracking
    ticks_since_switch: int = 0
    transition_period: int = 50  # Ticks to blend during transitions
    min_ticks_between_switches: int = 100  # Prevent rapid switching

    # Last values
    last_utility: Optional[UtilityResult] = None
    last_wave_count: Optional[WaveCount] = None
    last_indicator_signal: Optional[CompositeSignal] = None
    last_model_recommendation: Optional[ModelRecommendation] = None
    last_volume_profile: Optional[VolumeProfileResult] = None

    # Callbacks
    on_entry_signal: Optional[Callable[[float, float], None]] = None
    on_exit_signal: Optional[Callable[[float], None]] = None
    on_model_switch: Optional[Callable[[ActiveModel, ActiveModel], None]] = None

    def __post_init__(self):
        """Initialize all components."""
        if self.bayesian_state is None:
            self.bayesian_state = BayesianStateRegister.initialize(self.config.prior)

        if self.utility_calc is None:
            self.utility_calc = BayesianUtility(self.config.risk)

        if self.ema_state is None:
            self.ema_state = EMAState()

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

        if self.volume_profile is None:
            self.volume_profile = VolumeProfile(tick_size=0.01)

    @classmethod
    def create(
        cls,
        tier: TradingTier = TradingTier.SWING,
    ) -> "HybridEvolutionEngine":
        """Create hybrid engine with tier-specific configuration."""
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
    ) -> Dict[str, Any]:
        """
        Process a single tick and update both models.

        Returns unified signal from the appropriate model.
        """
        self.tick_count += 1
        self.ticks_since_switch += 1
        high = high or price
        low = low or price
        vwap = vwap or price

        # 1. Update technical indicators (shared by both models)
        indicator_signal = self.indicators.update(price, high, low)
        self.last_indicator_signal = indicator_signal

        # 2. Update model selector
        adx_value = self.indicators.adx.adx
        model_rec = self.model_selector.update(price, adx_value)
        self.last_model_recommendation = model_rec

        # 2.5. Update volume profile with tick data
        tick_volume = volume if volume else 1.0
        self.last_volume_profile = self.volume_profile.update(price, tick_volume)

        # 3. Update Elliott Wave (shared)
        wave_count = self.elliott_analyzer.process_bar(price, high, low)
        self.last_wave_count = wave_count

        # 4. Build observables (shared)
        obs = self._build_observables(price, vwap, indicator_signal, wave_count, **extra_data)

        # 5. Update Bayesian model
        regime = self.utility_calc.detect_regime(obs)
        self.bayesian_state = self.bayesian_state.with_regime(regime)
        bayesian_utility = self.utility_calc.compute_utility(obs, self.bayesian_state)
        self._update_bayesian_posteriors(obs, bayesian_utility)
        self.last_utility = bayesian_utility

        # 6. Update EMA model
        momentum = indicator_signal.net_signal
        volatility = self.indicators.atr.atr_percent / 0.015 if self.indicators.atr.atr_percent > 0 else 1.0
        ema_signal = self._compute_ema_signal(indicator_signal, wave_count)
        self.ema_state.update(momentum, volatility, ema_signal)

        # 7. Check for model switch
        self._check_model_switch(model_rec)

        # 8. Generate unified signal
        signal = self._generate_unified_signal(bayesian_utility)

        # 9. Handle signals
        self._handle_signals(signal, price)

        return signal

    def _build_observables(
        self,
        price: float,
        vwap: float,
        indicator_signal: CompositeSignal,
        wave_count: WaveCount,
        **extra_data,
    ) -> BayesianObservables:
        """Build observables from indicator and wave data."""
        rsi_signal = next(
            (s for s in indicator_signal.signals if s.name == "RSI"),
            None
        )
        momentum = 0.0
        if rsi_signal:
            momentum = (rsi_signal.value - 50) / 50

        order_imbalance = indicator_signal.net_signal
        atr_percent = self.indicators.atr.atr_percent
        volatility_ratio = atr_percent / 0.015 if atr_percent > 0 else 1.0
        noise = 1.0 - indicator_signal.confidence

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

    def _update_bayesian_posteriors(
        self,
        obs: BayesianObservables,
        utility: UtilityResult,
    ) -> None:
        """Perform Bayesian posterior updates."""
        base_weight = self.config.likelihood.get_adjusted_weight(self.bayesian_state.regime)

        if self.config.asymmetric_enabled:
            pnl_direction = utility.utility
            if pnl_direction < 0:
                weight = base_weight * self.config.loss_multiplier
            elif pnl_direction > 0:
                weight = base_weight * self.config.gain_multiplier
            else:
                weight = base_weight
        else:
            weight = base_weight

        likelihood_obs = obs.to_likelihood_observation()
        for param_name, (observation, obs_weight) in likelihood_obs.items():
            combined_weight = weight * obs_weight
            self.bayesian_state = self.bayesian_state.with_posterior_update(
                param=param_name,
                observation=observation,
                weight=combined_weight,
            )

    def _compute_ema_signal(
        self,
        indicator_signal: CompositeSignal,
        wave_count: WaveCount,
    ) -> float:
        """Compute EMA-style signal from indicators."""
        # Simple weighted combination
        indicator_sig = indicator_signal.net_signal
        elliott_sig = wave_count.signal if wave_count else 0.0

        # EMA just uses simple combination
        return 0.6 * indicator_sig + 0.4 * elliott_sig

    def _check_model_switch(self, rec: ModelRecommendation) -> None:
        """Check if we should switch models based on recommendation."""
        if self.ticks_since_switch < self.min_ticks_between_switches:
            return  # Too soon to switch

        current = self.active_model
        recommended = rec.model

        # Determine if switch is needed
        should_switch = False
        new_model = current

        if recommended == ModelType.EMA and current != ActiveModel.EMA:
            if rec.confidence > 0.6:
                should_switch = True
                new_model = ActiveModel.EMA
        elif recommended == ModelType.BAYESIAN and current != ActiveModel.BAYESIAN:
            if rec.confidence > 0.6:
                should_switch = True
                new_model = ActiveModel.BAYESIAN
        elif recommended == ModelType.EITHER:
            # Stay with current model
            pass
        elif recommended == ModelType.NEITHER:
            # Default to Bayesian (more conservative)
            if current != ActiveModel.BAYESIAN:
                should_switch = True
                new_model = ActiveModel.BAYESIAN

        if should_switch:
            old_model = self.active_model
            self.active_model = new_model
            self.ticks_since_switch = 0
            self.blend_weight = 0.5  # Start blending

            if self.on_model_switch:
                self.on_model_switch(old_model, new_model)

        # Update blend weight for smooth transitions
        if self.ticks_since_switch < self.transition_period:
            # During transition, use blending
            progress = self.ticks_since_switch / self.transition_period
            if self.active_model == ActiveModel.EMA:
                self.blend_weight = progress  # Ramp up to EMA
            else:
                self.blend_weight = 1.0 - progress  # Ramp down to Bayesian
        else:
            # After transition, use pure model
            self.blend_weight = 1.0 if self.active_model == ActiveModel.EMA else 0.0

    def _generate_unified_signal(self, bayesian_utility: UtilityResult) -> Dict[str, Any]:
        """Generate unified signal from active model(s)."""
        # Get signals from both models
        bayesian_signal = bayesian_utility.utility
        ema_signal = self.ema_state.get_signal()

        # Blend based on active model and transition state
        if self.active_model == ActiveModel.BLENDED or 0 < self.blend_weight < 1:
            # Use weighted blend
            combined_signal = (1 - self.blend_weight) * bayesian_signal + self.blend_weight * ema_signal
        elif self.active_model == ActiveModel.EMA:
            combined_signal = ema_signal
        else:
            combined_signal = bayesian_signal

        # Add indicator and Elliott wave signals
        indicator_signal = self.last_indicator_signal.net_signal if self.last_indicator_signal else 0.0
        elliott_signal = self.last_wave_count.signal if self.last_wave_count else 0.0

        # Get volume profile signal (key levels, value area positioning)
        vp_signal_data = self.volume_profile.get_trading_signal(
            self.last_volume_profile.poc if self.last_volume_profile else 0.0
        ) if self.last_volume_profile else {"signal": 0.0, "strength": 0.0}
        volume_profile_signal = vp_signal_data.get("signal", 0.0)

        # Final weighted combination including volume profile
        # Volume profile helps identify key S/R levels
        final_signal = (
            0.35 * combined_signal +      # Primary model signal
            0.25 * indicator_signal +      # Technical indicators
            0.20 * elliott_signal +        # Elliott wave pattern
            0.20 * volume_profile_signal   # Volume profile (POC, VA, HVN/LVN)
        )

        # Direction
        if final_signal > 0.2:
            direction = "buy"
        elif final_signal < -0.2:
            direction = "sell"
        else:
            direction = "neutral"

        # Entry/Exit logic depends on active model
        if self.active_model == ActiveModel.EMA:
            base_entry = self.ema_state.get_entry_signal()
            exit_sig = self.ema_state.get_exit_signal()
            position_size = self.ema_state.position_scalar_ema
        else:
            base_entry = bayesian_utility.entry_signal
            exit_sig = bayesian_utility.exit_signal
            position_size = bayesian_utility.position_size

        # Volume Profile Entry Filtering (autonomous safety)
        # Don't enter long at resistance (VAH), don't enter short at support (VAL)
        vp_location = vp_signal_data.get("location", "inside_value_area")
        entry_blocked_by_vp = False
        vp_block_reason = ""

        if direction == "buy" and vp_location in ["at_vah", "above_value_area"]:
            # Trying to go long at/above resistance - risky
            if vp_signal_data.get("strength", 0) > 0.5:
                entry_blocked_by_vp = True
                vp_block_reason = "Long blocked: at VAH resistance"
        elif direction == "sell" and vp_location in ["at_val", "below_value_area"]:
            # Trying to go short at/below support - risky
            if vp_signal_data.get("strength", 0) > 0.5:
                entry_blocked_by_vp = True
                vp_block_reason = "Short blocked: at VAL support"

        # Final entry decision
        entry = base_entry and not entry_blocked_by_vp

        # Boost confidence if entering at good VP levels
        # (long at VAL support, short at VAH resistance)
        vp_confidence_boost = 0.0
        if direction == "buy" and vp_location in ["at_val", "below_value_area"]:
            vp_confidence_boost = 0.15  # Long at support
        elif direction == "sell" and vp_location in ["at_vah", "above_value_area"]:
            vp_confidence_boost = 0.15  # Short at resistance

        # Confidence
        indicator_conf = self.last_indicator_signal.confidence if self.last_indicator_signal else 0.5
        model_conf = self.last_model_recommendation.confidence if self.last_model_recommendation else 0.5
        vp_strength = vp_signal_data.get("strength", 0.5)
        confidence = min(1.0, indicator_conf * model_conf * (0.8 + 0.2 * vp_strength) + vp_confidence_boost)

        return {
            "signal": final_signal,
            "direction": direction,
            "confidence": confidence,
            "should_trade": abs(final_signal) > 0.15 and not entry_blocked_by_vp,
            "entry": entry,
            "exit": exit_sig,
            "entry_blocked_by_vp": entry_blocked_by_vp,
            "vp_block_reason": vp_block_reason,
            "position_size": position_size,
            "bayesian_signal": bayesian_signal,
            "ema_signal": ema_signal,
            "indicator_signal": indicator_signal,
            "elliott_signal": elliott_signal,
            "volume_profile_signal": volume_profile_signal,
            "regime": self.bayesian_state.regime.value,
            "active_model": self.active_model.value,
            "blend_weight": self.blend_weight,
            "model_selection": {
                "recommended": self.last_model_recommendation.model.value if self.last_model_recommendation else "bayesian",
                "hurst": self.last_model_recommendation.hurst if self.last_model_recommendation else 0.5,
                "adx": self.last_model_recommendation.adx if self.last_model_recommendation else 0.0,
                "volatility_ratio": self.last_model_recommendation.volatility_ratio if self.last_model_recommendation else 1.0,
                "reason": self.last_model_recommendation.reason if self.last_model_recommendation else "",
            },
            "indicators": {
                "buy_score": self.last_indicator_signal.buy_score if self.last_indicator_signal else 0.0,
                "sell_score": self.last_indicator_signal.sell_score if self.last_indicator_signal else 0.0,
                "consensus": self.last_indicator_signal.consensus.value if self.last_indicator_signal else "neutral",
            },
            "volume_profile": self._get_volume_profile_info(),
        }

    def _get_volume_profile_info(self) -> Dict[str, Any]:
        """Get volume profile information for signal output."""
        if not self.last_volume_profile:
            return {
                "poc": 0.0,
                "vah": 0.0,
                "val": 0.0,
                "location": "unknown",
                "signal": 0.0,
            }

        vp = self.last_volume_profile
        vp_signal = self.volume_profile.get_trading_signal(vp.poc)

        return {
            "poc": vp.poc,
            "vah": vp.vah,
            "val": vp.val,
            "location": vp.current_location.value,
            "distance_to_poc_pct": vp.distance_to_poc,
            "hvn_above": vp.nearest_hvn_above,
            "hvn_below": vp.nearest_hvn_below,
            "lvn_nearby": vp.nearest_lvn,
            "signal": vp_signal["signal"],
            "bias": vp_signal["bias"],
            "reason": vp_signal["reason"],
        }

    def _handle_signals(self, signal: Dict[str, Any], price: float) -> None:
        """Handle entry/exit signals."""
        if signal.get("entry") and self.on_entry_signal:
            direction = 1.0 if signal["direction"] == "buy" else -1.0
            self.on_entry_signal(direction, signal["position_size"])
        elif signal.get("exit") and self.on_exit_signal:
            self.on_exit_signal(price)

    def update_equity(self, equity: float) -> None:
        """Update equity for drawdown tracking."""
        self.bayesian_state = self.bayesian_state.with_equity(equity)

    def get_state_summary(self) -> Dict[str, Any]:
        """Get current state summary."""
        estimates = self.bayesian_state.posterior.get_point_estimates()
        uncertainties = self.bayesian_state.posterior.get_uncertainties()

        return {
            "tick_count": self.tick_count,
            "active_model": self.active_model.value,
            "blend_weight": self.blend_weight,
            "regime": self.bayesian_state.regime.value,
            "drawdown": self.bayesian_state.drawdown,
            "bayesian_estimates": estimates,
            "bayesian_uncertainties": uncertainties,
            "ema_signal": self.ema_state.get_signal(),
            "ema_position_scalar": self.ema_state.position_scalar_ema,
            "model_recommendation": self.last_model_recommendation.model.value if self.last_model_recommendation else None,
            "hurst": self.last_model_recommendation.hurst if self.last_model_recommendation else 0.5,
            "ticks_since_switch": self.ticks_since_switch,
        }

    def force_model(self, model: ActiveModel) -> None:
        """Force a specific model (for testing/override)."""
        self.active_model = model
        self.ticks_since_switch = self.min_ticks_between_switches  # Prevent immediate auto-switch

    def reset(self) -> None:
        """Reset engine to initial state."""
        self.bayesian_state = BayesianStateRegister.initialize(self.config.prior)
        self.ema_state.reset()
        self.elliott_analyzer.reset()
        self.indicators.reset()
        self.model_selector.reset()
        self.volume_profile.reset()
        self.tick_count = 0
        self.active_model = ActiveModel.BAYESIAN
        self.blend_weight = 0.0
        self.ticks_since_switch = 0
        self.last_utility = None
        self.last_wave_count = None
        self.last_indicator_signal = None
        self.last_model_recommendation = None
        self.last_volume_profile = None


def create_hybrid_engine(
    tier: str = "swing",
) -> HybridEvolutionEngine:
    """
    Create hybrid evolution engine.

    Args:
        tier: Trading tier ("scalper", "daytrader", "swing", "position")

    Returns:
        Configured HybridEvolutionEngine
    """
    tier_map = {
        "scalper": TradingTier.SCALPER,
        "daytrader": TradingTier.DAYTRADER,
        "swing": TradingTier.SWING,
        "position": TradingTier.POSITION,
    }

    trading_tier = tier_map.get(tier.lower(), TradingTier.SWING)
    config = BayesianConfig.from_tier(trading_tier)
    config.asymmetric_enabled = True

    return HybridEvolutionEngine(config=config)
