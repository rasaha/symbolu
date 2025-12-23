"""
Self-Improving Hybrid Engine

Integrates recursive self-improvement capabilities with the Hybrid Trading Engine.

This creates a trading system that:
1. Trades using EMA/Bayesian hybrid model
2. Tracks its own predictions and outcomes
3. Identifies patterns of failure
4. Generates hypotheses for improvement
5. Modifies its own knowledge base
6. Applies learned insights to improve future performance

Experimental: Demonstrates AGI-like self-reflection and self-modification.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime

from trading2.core.config import BayesianConfig, TradingTier
from trading2.core.hybrid_engine import HybridEvolutionEngine, ActiveModel
from trading2.core.recursive_self_improvement import (
    RecursiveSelfImprover,
    KnowledgeBase,
    SelfEvaluator,
    Belief,
    BeliefType,
    ImprovementAction,
    ImprovementType,
)


@dataclass
class SelfImprovingHybridEngine:
    """
    Hybrid trading engine with recursive self-improvement.

    This engine wraps the HybridEvolutionEngine and adds:
    - Prediction tracking and outcome evaluation
    - Knowledge base with modifiable beliefs
    - Meta-reasoning about performance
    - Self-modification based on learned insights

    The system can:
    - Adjust its own confidence thresholds
    - Modify regime-specific strategy weights
    - Deprecate beliefs that prove incorrect
    - Generate and test new hypotheses
    """
    config: BayesianConfig

    # Core trading engine
    trading_engine: HybridEvolutionEngine = field(default=None)

    # Self-improvement components
    self_improver: RecursiveSelfImprover = field(default=None)

    # Integration state
    pending_prediction_id: Optional[str] = None
    last_prediction_price: float = 0.0
    prediction_horizon: int = 10  # Ticks to wait before evaluating outcome

    # Learned adjustments (applied to trading)
    confidence_adjustment: float = 1.0  # Multiplier for confidence
    regime_weight_adjustments: Dict[str, float] = field(default_factory=dict)
    blocked_signals: List[str] = field(default_factory=list)  # Signals to avoid

    # Metrics
    total_predictions: int = 0
    correct_predictions: int = 0
    improvement_cycles: int = 0

    # Callbacks
    on_self_improvement: Optional[Callable[[ImprovementAction], None]] = None
    on_belief_update: Optional[Callable[[Belief], None]] = None

    def __post_init__(self):
        """Initialize components."""
        if self.trading_engine is None:
            self.trading_engine = HybridEvolutionEngine(config=self.config)

        if self.self_improver is None:
            self.self_improver = RecursiveSelfImprover(
                auto_improve=True,
                improvement_threshold=0.6,
            )
            self._setup_self_improvement_callbacks()
            self._initialize_trading_beliefs()

    def _setup_self_improvement_callbacks(self):
        """Wire up callbacks from self-improver."""
        self.self_improver.on_improvement_executed = self._on_improvement_executed
        self.self_improver.on_belief_changed = self._on_belief_changed

    def _initialize_trading_beliefs(self):
        """Add trading-specific beliefs to knowledge base."""
        trading_beliefs = [
            ("high_confidence_reliable", "High confidence predictions (>0.7) are reliable", 0.7),
            ("momentum_works_trending", "Momentum signals work well in trending markets", 0.7),
            ("reversion_works_ranging", "Mean reversion works well in ranging markets", 0.7),
            ("elliott_wave_useful", "Elliott Wave patterns provide useful entry/exit signals", 0.65),
            ("volume_profile_key_levels", "Volume profile identifies key support/resistance", 0.7),
            ("model_selector_accurate", "The model selector correctly identifies regime", 0.6),
            ("blending_reduces_risk", "Blending models during transitions reduces risk", 0.65),
        ]

        for belief_id, content, confidence in trading_beliefs:
            belief = Belief(
                id=belief_id,
                content=content,
                belief_type=BeliefType.PRIOR,
                confidence=confidence,
                metadata={"source": "trading_engine_init"}
            )
            self.self_improver.kb.add_belief(belief)

    @classmethod
    def create(
        cls,
        tier: TradingTier = TradingTier.SWING,
        auto_improve: bool = True,
    ) -> "SelfImprovingHybridEngine":
        """Create self-improving engine with tier-specific configuration."""
        config = BayesianConfig.from_tier(tier)
        config.asymmetric_enabled = True

        engine = cls(config=config)
        engine.self_improver.auto_improve = auto_improve

        return engine

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
        Process tick with self-improvement integration.

        1. Process through trading engine
        2. Record prediction
        3. Evaluate past predictions
        4. Apply learned adjustments
        """
        # 1. Process through trading engine
        signal = self.trading_engine.process_tick(
            price=price,
            high=high,
            low=low,
            volume=volume,
            vwap=vwap,
            **extra_data,
        )

        # 2. Evaluate pending prediction (if horizon passed)
        if self.pending_prediction_id and self.trading_engine.tick_count >= self._prediction_eval_tick:
            self._evaluate_pending_prediction(price)

        # 3. Record new prediction
        if signal.get("should_trade"):
            self._record_prediction(signal, price)

        # 4. Apply learned adjustments
        adjusted_signal = self._apply_learned_adjustments(signal)

        # 5. Add self-improvement metadata
        adjusted_signal["self_improvement"] = self._get_self_improvement_info()

        return adjusted_signal

    def _record_prediction(self, signal: Dict[str, Any], price: float) -> None:
        """Record a prediction for later evaluation."""
        context = {
            "regime": signal.get("regime", "unknown"),
            "active_model": signal.get("active_model", "bayesian"),
            "volatility_ratio": signal.get("model_selection", {}).get("volatility_ratio", 1.0),
            "hurst": signal.get("model_selection", {}).get("hurst", 0.5),
            "adx": signal.get("model_selection", {}).get("adx", 0.0),
            "elliott_signal": signal.get("elliott_signal", 0.0),
            "volume_profile_location": signal.get("volume_profile", {}).get("location", "unknown"),
        }

        self.pending_prediction_id = self.self_improver.observe_prediction(
            signal=signal.get("signal", 0.0),
            direction=signal.get("direction", "neutral"),
            confidence=signal.get("confidence", 0.5),
            context=context,
        )
        self.last_prediction_price = price
        self._prediction_eval_tick = self.trading_engine.tick_count + self.prediction_horizon
        self.total_predictions += 1

    def _evaluate_pending_prediction(self, current_price: float) -> None:
        """Evaluate a past prediction against actual outcome."""
        if not self.pending_prediction_id:
            return

        # Calculate price change
        price_change = current_price - self.last_prediction_price
        price_change_percent = (price_change / self.last_prediction_price) * 100 if self.last_prediction_price > 0 else 0

        # Normalize outcome to [-1, 1]
        actual_outcome = max(-1.0, min(1.0, price_change_percent / 2.0))

        # Record outcome in self-improver
        self.self_improver.observe_outcome(
            self.pending_prediction_id,
            actual_outcome,
            price_change_percent,
        )

        # Update correct count
        prediction = None
        for pred in self.self_improver.evaluator.completed_predictions:
            if pred.id == self.pending_prediction_id:
                prediction = pred
                break

        if prediction and prediction.was_correct:
            self.correct_predictions += 1

        # Clear pending
        self.pending_prediction_id = None

    def _apply_learned_adjustments(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Apply learned adjustments from self-improvement."""
        adjusted = signal.copy()

        # 1. Adjust confidence based on learned calibration
        adjusted["confidence"] = signal.get("confidence", 0.5) * self.confidence_adjustment

        # 2. Check for blocked signal patterns
        regime = signal.get("regime", "unknown")
        direction = signal.get("direction", "neutral")

        block_key = f"{regime}_{direction}"
        if block_key in self.blocked_signals:
            adjusted["should_trade"] = False
            adjusted["entry"] = False
            adjusted["blocked_reason"] = f"Pattern blocked by self-improvement: {block_key}"

        # 3. Apply regime-specific weight adjustments
        if regime in self.regime_weight_adjustments:
            adjustment = self.regime_weight_adjustments[regime]
            adjusted["signal"] = signal.get("signal", 0.0) * adjustment

        # 4. Check beliefs for trading decisions
        adjusted = self._apply_belief_based_adjustments(adjusted)

        return adjusted

    def _apply_belief_based_adjustments(self, signal: Dict[str, Any]) -> Dict[str, Any]:
        """Apply adjustments based on current beliefs."""
        kb = self.self_improver.kb

        # Check confidence belief
        conf_belief = kb.beliefs.get("high_confidence_reliable")
        if conf_belief and conf_belief.confidence < 0.4:
            # We've learned high confidence isn't reliable - reduce confidence
            if signal.get("confidence", 0) > 0.7:
                signal["confidence"] *= 0.8
                signal["confidence_reduced_reason"] = "Belief: high confidence unreliable"

        # Check Elliott Wave belief
        elliott_belief = kb.beliefs.get("elliott_wave_useful")
        if elliott_belief and elliott_belief.confidence < 0.4:
            # Elliott Wave signals are unreliable - reduce their weight
            elliott_sig = signal.get("elliott_signal", 0)
            if abs(elliott_sig) > 0.3:
                # Dampen Elliott signal contribution
                signal["elliott_signal"] *= 0.5
                signal["elliott_reduced_reason"] = "Belief: Elliott Wave unreliable"

        # Check model selector belief
        selector_belief = kb.beliefs.get("model_selector_accurate")
        if selector_belief and selector_belief.confidence < 0.4:
            # Model selector is unreliable - stick with Bayesian
            if signal.get("active_model") == "ema":
                signal["model_selection_override"] = "Forcing Bayesian due to selector unreliability"

        return signal

    def _on_improvement_executed(self, action: ImprovementAction) -> None:
        """Handle executed improvement action."""
        self.improvement_cycles += 1

        # Apply the improvement to trading behavior
        if action.action_type == ImprovementType.THRESHOLD_CHANGE:
            # Adjust confidence threshold
            if "overconfidence" in action.description.lower():
                self.confidence_adjustment *= 0.9  # Reduce confidence
            elif "underconfidence" in action.description.lower():
                self.confidence_adjustment *= 1.1  # Increase confidence

        elif action.action_type == ImprovementType.STRATEGY_SWITCH:
            # Adjust regime-specific behavior
            regime = action.after_state.get("beliefs", {}).get("regime", "")
            if regime:
                # Reduce weight for problematic regime
                self.regime_weight_adjustments[regime] = 0.7

        elif action.action_type == ImprovementType.RULE_ADDITION:
            # Check if we should block a pattern
            description = action.description.lower()
            if "block" in description or "avoid" in description:
                # Extract pattern to block (simplified)
                if "trending" in description and "buy" in description:
                    self.blocked_signals.append("trending_buy")
                elif "ranging" in description and "sell" in description:
                    self.blocked_signals.append("ranging_sell")

        # Fire callback
        if self.on_self_improvement:
            self.on_self_improvement(action)

    def _on_belief_changed(self, belief: Belief) -> None:
        """Handle belief change."""
        if self.on_belief_update:
            self.on_belief_update(belief)

    def _get_self_improvement_info(self) -> Dict[str, Any]:
        """Get self-improvement status information."""
        accuracy = self.correct_predictions / max(1, self.total_predictions)

        return {
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "accuracy": accuracy,
            "improvement_cycles": self.improvement_cycles,
            "confidence_adjustment": self.confidence_adjustment,
            "blocked_signals": len(self.blocked_signals),
            "regime_adjustments": len(self.regime_weight_adjustments),
            "active_beliefs": len(self.self_improver.kb.get_active_beliefs()),
            "pending_improvements": len(self.self_improver.pending_improvements),
        }

    def get_reasoning_trace(self) -> List[Dict[str, Any]]:
        """Get the reasoning trace showing self-improvement logic."""
        return self.self_improver.get_reasoning_trace()

    def get_beliefs_summary(self) -> Dict[str, Any]:
        """Get summary of current beliefs."""
        beliefs = {}
        for belief in self.self_improver.kb.get_active_beliefs():
            beliefs[belief.id] = {
                "content": belief.content,
                "confidence": belief.confidence,
                "type": belief.belief_type.value,
                "evidence_count": belief.evidence_count,
            }
        return beliefs

    def get_improvement_recommendations(self) -> List[Dict[str, Any]]:
        """Get current improvement recommendations without executing."""
        return self.self_improver.get_improvement_recommendations()

    def force_improvement_cycle(self) -> List[ImprovementAction]:
        """Manually trigger an improvement cycle."""
        return self.self_improver.run_improvement_cycle()

    def rollback_last_improvement(self) -> bool:
        """Rollback the last improvement."""
        if self.self_improver.executed_improvements:
            last = self.self_improver.executed_improvements[-1]
            return self.self_improver.rollback_improvement(last.id)
        return False

    def update_equity(self, equity: float) -> None:
        """Update equity for drawdown tracking."""
        self.trading_engine.update_equity(equity)

    def get_state_summary(self) -> Dict[str, Any]:
        """Get comprehensive state summary."""
        trading_state = self.trading_engine.get_state_summary()
        improvement_state = self.self_improver.get_state_summary()

        return {
            "trading": trading_state,
            "self_improvement": improvement_state,
            "integration": {
                "confidence_adjustment": self.confidence_adjustment,
                "regime_adjustments": self.regime_weight_adjustments,
                "blocked_signals": self.blocked_signals,
                "prediction_accuracy": self.correct_predictions / max(1, self.total_predictions),
            },
        }

    def export_learned_knowledge(self) -> Dict[str, Any]:
        """Export all learned knowledge for persistence."""
        return {
            "knowledge_base": self.self_improver.kb.export_state(),
            "confidence_adjustment": self.confidence_adjustment,
            "regime_adjustments": self.regime_weight_adjustments,
            "blocked_signals": self.blocked_signals,
            "improvement_history": [
                {
                    "id": imp.id,
                    "type": imp.action_type.value,
                    "description": imp.description,
                    "timestamp": imp.timestamp,
                }
                for imp in self.self_improver.executed_improvements
            ],
            "evaluation_summary": self.self_improver.evaluator.get_evaluation_summary(),
        }

    def import_learned_knowledge(self, knowledge: Dict[str, Any]) -> None:
        """Import previously learned knowledge."""
        if "confidence_adjustment" in knowledge:
            self.confidence_adjustment = knowledge["confidence_adjustment"]

        if "regime_adjustments" in knowledge:
            self.regime_weight_adjustments = knowledge["regime_adjustments"]

        if "blocked_signals" in knowledge:
            self.blocked_signals = knowledge["blocked_signals"]

        # Note: Full KB restoration would require more complex logic

    def reset(self) -> None:
        """Reset all state (including learned knowledge)."""
        self.trading_engine.reset()
        self.self_improver = RecursiveSelfImprover(
            auto_improve=True,
            improvement_threshold=0.6,
        )
        self._setup_self_improvement_callbacks()
        self._initialize_trading_beliefs()

        self.pending_prediction_id = None
        self.last_prediction_price = 0.0
        self.confidence_adjustment = 1.0
        self.regime_weight_adjustments.clear()
        self.blocked_signals.clear()
        self.total_predictions = 0
        self.correct_predictions = 0
        self.improvement_cycles = 0


def create_self_improving_engine(
    tier: str = "swing",
    auto_improve: bool = True,
) -> SelfImprovingHybridEngine:
    """
    Create self-improving hybrid engine.

    Args:
        tier: Trading tier ("scalper", "daytrader", "swing", "position")
        auto_improve: Enable automatic self-improvement

    Returns:
        Configured SelfImprovingHybridEngine
    """
    tier_map = {
        "scalper": TradingTier.SCALPER,
        "daytrader": TradingTier.DAYTRADER,
        "swing": TradingTier.SWING,
        "position": TradingTier.POSITION,
    }

    trading_tier = tier_map.get(tier.lower(), TradingTier.SWING)
    return SelfImprovingHybridEngine.create(tier=trading_tier, auto_improve=auto_improve)
