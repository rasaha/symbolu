"""
Bayesian Utility Function

Risk-adjusted utility calculation for the Bayesian trading system.
Similar to trading/core/utility.py but adapted for Bayesian posteriors.
"""

from dataclasses import dataclass
from typing import Optional

from trading2.core.config import RegimeType, RiskConfig
from trading2.core.observables import BayesianObservables
from trading2.core.state_register import BayesianStateRegister


@dataclass(frozen=True)
class UtilityResult:
    """
    Result of utility computation.

    Contains the utility score and breakdown of contributing factors.
    """
    # Overall utility score [-1, 1]
    utility: float

    # Component scores
    signal_utility: float       # From composite signal
    risk_penalty: float         # From volatility, drawdown
    regime_adjustment: float    # From market regime
    uncertainty_penalty: float  # From posterior uncertainty (Bayesian-specific)
    elliott_bonus: float        # From Elliott wave alignment

    # Recommended action
    entry_signal: bool = False
    exit_signal: bool = False
    position_size: float = 0.0

    @property
    def should_trade(self) -> bool:
        """Whether conditions favor trading."""
        return abs(self.utility) > 0.3 and self.uncertainty_penalty < 0.5


class BayesianUtility:
    """
    Compute risk-adjusted utility for trading decisions.

    Key difference from EMA utility:
    - Incorporates posterior uncertainty as penalty
    - Uses credible intervals for regime detection
    - Elliott wave alignment bonus
    """

    def __init__(self, risk_config: Optional[RiskConfig] = None):
        """
        Initialize utility calculator.

        Args:
            risk_config: Risk management configuration
        """
        self.risk_config = risk_config or RiskConfig()

    def compute_utility(
        self,
        obs: BayesianObservables,
        state: BayesianStateRegister,
    ) -> UtilityResult:
        """
        Compute utility from observables and current state.

        Args:
            obs: Current market observables
            state: Current Bayesian state

        Returns:
            UtilityResult with utility score and components
        """
        # 1. Base signal utility from composite signal
        composite = obs.compute_composite_signal(
            w_momentum=state.w_momentum,
            w_reversion=state.w_reversion,
            w_elliott=state.w_elliott,
            w_imbalance=0.1,  # Fixed small weight for imbalance
        )
        signal_utility = composite

        # 2. Risk penalty
        risk_penalty = self._compute_risk_penalty(obs, state)

        # 3. Regime adjustment
        regime_adjustment = self._compute_regime_adjustment(obs, state)

        # 4. Uncertainty penalty (Bayesian-specific)
        uncertainty_penalty = self._compute_uncertainty_penalty(state)

        # 5. Elliott wave bonus
        elliott_bonus = self._compute_elliott_bonus(obs, state)

        # Combine into final utility
        utility = (
            signal_utility * (1.0 - risk_penalty) * (1.0 - uncertainty_penalty)
            + regime_adjustment
            + elliott_bonus
        )

        # Clamp to [-1, 1]
        utility = max(-1.0, min(1.0, utility))

        # Determine entry/exit signals
        entry_signal = abs(utility) > state.tau_entry
        exit_signal = abs(utility) < state.tau_exit

        # Calculate position size
        position_size = self._compute_position_size(utility, state, obs)

        return UtilityResult(
            utility=utility,
            signal_utility=signal_utility,
            risk_penalty=risk_penalty,
            regime_adjustment=regime_adjustment,
            uncertainty_penalty=uncertainty_penalty,
            elliott_bonus=elliott_bonus,
            entry_signal=entry_signal,
            exit_signal=exit_signal,
            position_size=position_size,
        )

    def _compute_risk_penalty(
        self,
        obs: BayesianObservables,
        state: BayesianStateRegister,
    ) -> float:
        """
        Compute risk penalty from volatility and drawdown.

        Returns penalty in [0, 1] where 1 = maximum penalty.
        """
        penalty = 0.0

        # Volatility penalty
        if obs.tick_volatility > 1.5:
            vol_penalty = min(0.4, (obs.tick_volatility - 1.5) * 0.2)
            penalty += vol_penalty

        # Drawdown penalty
        if state.drawdown > self.risk_config.warning_drawdown:
            dd_severity = (state.drawdown - self.risk_config.warning_drawdown) / \
                         (self.risk_config.max_drawdown - self.risk_config.warning_drawdown)
            dd_penalty = min(0.5, dd_severity * 0.5)
            penalty += dd_penalty

        # Spread penalty
        if obs.spread_normalized > 2.0:
            spread_penalty = min(0.2, (obs.spread_normalized - 2.0) * 0.1)
            penalty += spread_penalty

        # Noise penalty
        if obs.noise_level > 0.7:
            noise_penalty = min(0.2, (obs.noise_level - 0.7) * 0.67)
            penalty += noise_penalty

        return min(1.0, penalty)

    def _compute_regime_adjustment(
        self,
        obs: BayesianObservables,
        state: BayesianStateRegister,
    ) -> float:
        """
        Compute regime-based adjustment to utility.

        Returns adjustment in [-0.2, 0.2].
        """
        adjustment = 0.0

        if state.regime == RegimeType.TRENDING:
            # Trending favors momentum signals
            if abs(obs.momentum) > 0.5:
                adjustment = 0.1 * (1 if obs.momentum > 0 else -1)

        elif state.regime == RegimeType.RANGING:
            # Ranging favors mean reversion
            if abs(obs.mean_reversion) > 0.5:
                adjustment = 0.1 * (1 if obs.mean_reversion > 0 else -1)

        elif state.regime == RegimeType.CRISIS:
            # Crisis mode - reduce all signals
            adjustment = -0.2

        elif state.regime == RegimeType.VOLATILE:
            # Volatile - be cautious but don't fully retreat
            adjustment = -0.1

        return adjustment

    def _compute_uncertainty_penalty(self, state: BayesianStateRegister) -> float:
        """
        Compute penalty from posterior uncertainty.

        High uncertainty in parameters means we should be more cautious.
        This is unique to Bayesian approach - EMA has no uncertainty measure.

        Returns penalty in [0, 0.5].
        """
        uncertainties = state.posterior.get_uncertainties()

        # Focus on key trading parameters
        key_uncertainties = [
            uncertainties.get("tau_entry", 0),
            uncertainties.get("tau_exit", 0),
            uncertainties.get("w_momentum", 0),
            uncertainties.get("w_reversion", 0),
            uncertainties.get("w_elliott", 0),
        ]

        # Average uncertainty (std dev of Beta is typically < 0.2)
        avg_uncertainty = sum(key_uncertainties) / len(key_uncertainties)

        # Map to penalty: uncertainty of 0.1 = 25% penalty, 0.2 = 50% penalty
        penalty = min(0.5, avg_uncertainty * 2.5)

        return penalty

    def _compute_elliott_bonus(
        self,
        obs: BayesianObservables,
        state: BayesianStateRegister,
    ) -> float:
        """
        Compute bonus when Elliott wave aligns with other signals.

        Returns bonus in [-0.15, 0.15].
        """
        if obs.elliott_confidence < 0.5:
            return 0.0

        # Check if Elliott signal aligns with momentum
        momentum_aligned = (
            (obs.elliott_signal > 0 and obs.momentum > 0) or
            (obs.elliott_signal < 0 and obs.momentum < 0)
        )

        if momentum_aligned:
            # Bonus proportional to confidence and wave position
            bonus = 0.1 * obs.elliott_confidence

            # Extra bonus for Wave 2/4 completions (good entry points)
            if obs.current_wave in (2, 4):
                bonus += 0.05

            return bonus * (1 if obs.elliott_signal > 0 else -1)

        return 0.0

    def _compute_position_size(
        self,
        utility: float,
        state: BayesianStateRegister,
        obs: BayesianObservables,
    ) -> float:
        """
        Compute recommended position size.

        Returns position size in [0, 1] where 1 = maximum position.
        """
        if abs(utility) < state.tau_exit:
            return 0.0

        # Base size from utility strength
        base_size = abs(utility)

        # Scale by state's position scalar
        size = base_size * state.position_scalar

        # Reduce in crisis
        if state.regime == RegimeType.CRISIS:
            size *= self.risk_config.crisis_position_scalar

        # Reduce based on uncertainty
        uncertainty = state.total_uncertainty / 10.0  # Normalize
        size *= (1.0 - min(0.5, uncertainty))

        # Reduce based on volatility
        if obs.tick_volatility > 2.0:
            size *= 0.5

        # Clamp to valid range
        return max(0.0, min(self.risk_config.max_position_scalar, size))

    def detect_regime(self, obs: BayesianObservables) -> RegimeType:
        """
        Detect current market regime from observables.

        Returns detected regime type.
        """
        # Crisis detection (highest priority)
        if obs.tick_volatility > 3.0 or obs.noise_level > 0.8:
            return RegimeType.CRISIS

        # Volatile regime
        if obs.tick_volatility > 2.0:
            return RegimeType.VOLATILE

        # Trending vs Ranging
        momentum_strength = abs(obs.momentum)
        reversion_strength = abs(obs.mean_reversion)

        if momentum_strength > 0.6 and momentum_strength > reversion_strength:
            return RegimeType.TRENDING

        if reversion_strength > 0.4 and obs.tick_volatility < 1.5:
            return RegimeType.RANGING

        return RegimeType.UNKNOWN
