"""
Trading Signals & Recommendations
=================================

Explicit probability scores and buy/sell recommendations.
Extends the base signal system with confidence metrics.

Signal Levels:
- STRONG_BUY:  High confidence bullish (>80%)
- BUY:         Moderate confidence bullish (60-80%)
- HOLD:        No clear signal (<60% either direction)
- SELL:        Moderate confidence bearish (60-80%)
- STRONG_SELL: High confidence bearish (>80%)
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import math

from trading.core.state_register import TradingStateRegister
from trading.core.observables import TickObservables
from trading.core.utility import UtilityResult


class Recommendation(Enum):
    """Trading recommendation levels."""
    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"

    @property
    def is_bullish(self) -> bool:
        return self in (Recommendation.STRONG_BUY, Recommendation.BUY)

    @property
    def is_bearish(self) -> bool:
        return self in (Recommendation.STRONG_SELL, Recommendation.SELL)

    @property
    def strength(self) -> int:
        """Strength from -2 (strong sell) to +2 (strong buy)."""
        return {
            Recommendation.STRONG_BUY: 2,
            Recommendation.BUY: 1,
            Recommendation.HOLD: 0,
            Recommendation.SELL: -1,
            Recommendation.STRONG_SELL: -2,
        }[self]


@dataclass(frozen=True)
class SignalScore:
    """
    Comprehensive signal scoring with probabilities.

    Provides:
    - Probability of profitable trade (0-100%)
    - Confidence in the signal (0-100%)
    - Buy/Sell recommendation
    - Entry/Exit scores
    """

    # Core scores (0-100%)
    bullish_probability: float    # P(price goes up)
    bearish_probability: float    # P(price goes down)
    confidence: float             # Confidence in the prediction

    # Recommendation
    recommendation: Recommendation
    recommendation_strength: float  # 0-100%

    # Entry/Exit scores
    entry_score: float            # 0-100%, higher = better entry
    exit_score: float             # 0-100%, higher = should exit

    # Risk-adjusted
    risk_reward_ratio: float      # Expected reward / expected risk
    kelly_fraction: float         # Optimal position size (Kelly criterion)

    # Context
    regime: str
    signal_raw: float             # Original [-1, 1] signal
    utility: float                # Utility value

    @property
    def win_probability(self) -> float:
        """Probability of winning trade based on direction."""
        if self.recommendation.is_bullish:
            return self.bullish_probability
        elif self.recommendation.is_bearish:
            return self.bearish_probability
        return 50.0  # Neutral

    @property
    def edge(self) -> float:
        """Edge = P(win) - P(loss), as percentage."""
        return abs(self.bullish_probability - self.bearish_probability)

    @property
    def is_actionable(self) -> bool:
        """Check if signal is strong enough to act on."""
        return (
            self.confidence >= 60.0 and
            self.recommendation != Recommendation.HOLD and
            self.entry_score >= 50.0
        )

    def to_dict(self) -> dict:
        """Export to dictionary."""
        return {
            "bullish_probability": round(self.bullish_probability, 1),
            "bearish_probability": round(self.bearish_probability, 1),
            "confidence": round(self.confidence, 1),
            "recommendation": self.recommendation.value,
            "recommendation_strength": round(self.recommendation_strength, 1),
            "entry_score": round(self.entry_score, 1),
            "exit_score": round(self.exit_score, 1),
            "risk_reward_ratio": round(self.risk_reward_ratio, 2),
            "kelly_fraction": round(self.kelly_fraction, 3),
            "regime": self.regime,
            "signal_raw": round(self.signal_raw, 3),
            "utility": round(self.utility, 3),
            "is_actionable": self.is_actionable,
        }


class SignalScorer:
    """
    Converts raw signals to probability scores and recommendations.

    Uses multiple factors:
    - Signal magnitude and direction
    - Utility value
    - Noise level (inverse confidence)
    - Volatility (risk adjustment)
    - Regime context
    - Historical accuracy (if available)
    """

    def __init__(
        self,
        base_win_rate: float = 0.52,  # Slight edge assumption
        avg_win_loss_ratio: float = 1.5,  # Avg win / avg loss
    ):
        """
        Initialize scorer.

        Args:
            base_win_rate: Base probability of winning (before adjustments)
            avg_win_loss_ratio: Average win size / average loss size
        """
        self.base_win_rate = base_win_rate
        self.avg_win_loss_ratio = avg_win_loss_ratio

        # Tracking for adaptive scoring
        self.total_signals = 0
        self.correct_signals = 0

    def score(
        self,
        signal: float,
        utility_result: UtilityResult,
        state: TradingStateRegister,
        obs: TickObservables,
    ) -> SignalScore:
        """
        Generate comprehensive signal score.

        Args:
            signal: Raw composite signal [-1, 1]
            utility_result: Utility calculation result
            state: Current trading state
            obs: Current observables

        Returns:
            SignalScore with probabilities and recommendation
        """
        self.total_signals += 1

        # Base probability from signal strength
        # Signal of 0 = 50/50, Signal of ±1 = more certain
        signal_factor = abs(signal)
        base_prob = 50 + signal_factor * 30  # 50-80% range from signal

        # Utility adjustment (positive utility = higher confidence)
        utility_adj = min(10, max(-10, utility_result.utility * 20))

        # Noise adjustment (high noise = lower confidence)
        noise_penalty = obs.noise_level * 15  # 0-15% penalty

        # Volatility adjustment (high vol = lower confidence)
        vol_penalty = min(10, max(0, (obs.tick_volatility - 1) * 5))

        # Regime adjustment
        regime_adj = self._regime_adjustment(state.regime, signal)

        # Calculate final probability
        if signal > 0:
            bullish_prob = min(95, max(5, base_prob + utility_adj + regime_adj - noise_penalty - vol_penalty))
            bearish_prob = 100 - bullish_prob
        elif signal < 0:
            bearish_prob = min(95, max(5, base_prob + utility_adj + regime_adj - noise_penalty - vol_penalty))
            bullish_prob = 100 - bearish_prob
        else:
            bullish_prob = 50
            bearish_prob = 50

        # Confidence: how certain we are in the prediction
        confidence = self._calculate_confidence(
            signal, utility_result, obs, state
        )

        # Recommendation
        recommendation, rec_strength = self._determine_recommendation(
            bullish_prob, bearish_prob, confidence, state
        )

        # Entry/Exit scores
        entry_score = self._calculate_entry_score(
            signal, utility_result, state, obs
        )
        exit_score = self._calculate_exit_score(
            signal, utility_result, state, obs
        )

        # Risk-reward ratio
        risk_reward = self._calculate_risk_reward(
            bullish_prob if signal > 0 else bearish_prob,
            obs.tick_volatility
        )

        # Kelly fraction (optimal bet size)
        kelly = self._calculate_kelly(
            bullish_prob if signal > 0 else bearish_prob,
            risk_reward
        )

        return SignalScore(
            bullish_probability=bullish_prob,
            bearish_probability=bearish_prob,
            confidence=confidence,
            recommendation=recommendation,
            recommendation_strength=rec_strength,
            entry_score=entry_score,
            exit_score=exit_score,
            risk_reward_ratio=risk_reward,
            kelly_fraction=kelly,
            regime=state.regime,
            signal_raw=signal,
            utility=utility_result.utility,
        )

    def _regime_adjustment(self, regime: str, signal: float) -> float:
        """Adjust probability based on regime."""
        if regime == "trending":
            # Trending: boost momentum signals
            return 5 if signal != 0 else 0
        elif regime == "ranging":
            # Ranging: slight boost to mean reversion
            return 3
        elif regime == "crisis":
            # Crisis: reduce all confidence
            return -10
        return 0

    def _calculate_confidence(
        self,
        signal: float,
        utility_result: UtilityResult,
        obs: TickObservables,
        state: TradingStateRegister,
    ) -> float:
        """Calculate confidence in the signal (0-100%)."""
        # Start with signal strength
        base_confidence = abs(signal) * 50  # 0-50% from signal

        # Add utility contribution
        if utility_result.is_favorable:
            utility_conf = min(20, utility_result.utility * 10)
        else:
            utility_conf = max(-20, utility_result.utility * 10)

        # Subtract noise
        noise_penalty = obs.noise_level * 20

        # Subtract volatility uncertainty
        vol_penalty = min(15, (obs.tick_volatility - 1) * 10) if obs.tick_volatility > 1 else 0

        # Signal-to-penalty ratio boost
        if utility_result.signal_to_penalty_ratio > 2:
            ratio_boost = 10
        elif utility_result.signal_to_penalty_ratio > 1:
            ratio_boost = 5
        else:
            ratio_boost = 0

        # Regime penalty for crisis
        regime_penalty = 20 if state.regime == "crisis" else 0

        confidence = (
            base_confidence +
            utility_conf +
            ratio_boost -
            noise_penalty -
            vol_penalty -
            regime_penalty
        )

        return max(0, min(100, confidence + 40))  # Base 40% + adjustments

    def _determine_recommendation(
        self,
        bullish_prob: float,
        bearish_prob: float,
        confidence: float,
        state: TradingStateRegister,
    ) -> Tuple[Recommendation, float]:
        """Determine recommendation level and strength."""
        # Crisis mode: always HOLD
        if state.is_crisis_mode:
            return Recommendation.HOLD, 0.0

        # Low confidence: HOLD
        if confidence < 50:
            return Recommendation.HOLD, confidence

        prob_diff = bullish_prob - bearish_prob

        # Strong signals (>70% probability, >70% confidence)
        if bullish_prob > 75 and confidence > 70:
            return Recommendation.STRONG_BUY, min(100, bullish_prob * confidence / 100)
        if bearish_prob > 75 and confidence > 70:
            return Recommendation.STRONG_SELL, min(100, bearish_prob * confidence / 100)

        # Moderate signals (>60% probability, >60% confidence)
        if bullish_prob > 60 and confidence > 60:
            return Recommendation.BUY, min(100, bullish_prob * confidence / 100)
        if bearish_prob > 60 and confidence > 60:
            return Recommendation.SELL, min(100, bearish_prob * confidence / 100)

        # Default: HOLD
        return Recommendation.HOLD, confidence * 0.5

    def _calculate_entry_score(
        self,
        signal: float,
        utility_result: UtilityResult,
        state: TradingStateRegister,
        obs: TickObservables,
    ) -> float:
        """Calculate entry attractiveness (0-100%)."""
        score = 50.0  # Base

        # Signal above threshold
        if abs(signal) > state.tau_entry:
            score += 20

        # Positive utility
        if utility_result.is_favorable:
            score += min(15, utility_result.utility * 10)

        # Low volatility (better entries in calm markets)
        if obs.tick_volatility < 1.2:
            score += 10
        elif obs.tick_volatility > 2:
            score -= 15

        # Low noise
        if obs.noise_level < 0.4:
            score += 10
        elif obs.noise_level > 0.7:
            score -= 10

        # Position scalar (risk budget available)
        score += state.position_scalar * 10

        return max(0, min(100, score))

    def _calculate_exit_score(
        self,
        signal: float,
        utility_result: UtilityResult,
        state: TradingStateRegister,
        obs: TickObservables,
    ) -> float:
        """Calculate exit urgency (0-100%)."""
        score = 20.0  # Base (low urgency)

        # High drawdown
        if state.drawdown > 0.08:
            score += 40
        elif state.drawdown > 0.05:
            score += 20

        # Crisis mode
        if state.is_crisis_mode:
            score += 30

        # Negative utility
        if utility_result.utility < -0.3:
            score += 25
        elif utility_result.utility < 0:
            score += 10

        # High volatility
        if obs.tick_volatility > 2.5:
            score += 20
        elif obs.tick_volatility > 1.5:
            score += 10

        return max(0, min(100, score))

    def _calculate_risk_reward(
        self,
        win_prob: float,
        volatility: float,
    ) -> float:
        """Calculate expected risk-reward ratio."""
        # Simple model: RR decreases with volatility
        base_rr = self.avg_win_loss_ratio

        # Volatility adjustment
        vol_factor = 1.0 / max(0.5, volatility)

        # Probability adjustment (higher win prob = can accept lower RR)
        prob_factor = win_prob / 50  # 1.0 at 50%, 1.6 at 80%

        return base_rr * vol_factor * prob_factor

    def _calculate_kelly(
        self,
        win_prob: float,
        risk_reward: float,
    ) -> float:
        """
        Calculate Kelly fraction for optimal position sizing.

        Kelly = (p * b - q) / b
        Where p = win probability, q = 1-p, b = win/loss ratio
        """
        p = win_prob / 100
        q = 1 - p
        b = risk_reward

        if b <= 0:
            return 0.0

        kelly = (p * b - q) / b

        # Cap at 25% (quarter Kelly is more practical)
        return max(0, min(0.25, kelly))

    def record_outcome(self, was_correct: bool) -> None:
        """Record outcome for adaptive scoring."""
        if was_correct:
            self.correct_signals += 1

    @property
    def historical_accuracy(self) -> float:
        """Historical accuracy rate."""
        if self.total_signals == 0:
            return self.base_win_rate
        return self.correct_signals / self.total_signals
