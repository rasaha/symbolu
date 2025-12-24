"""
Trading Utility Function
========================

Risk-adjusted utility function for trading, inspired by v2.7 compute_utility.

v2.7 Formula:
    U = c_S·S + c_R·R + c_T·T + λ_H·H + λ_C·C_contr + λ_F·F_fail

Trading Formula:
    U = w_mom·momentum + w_rev·reversion + w_imb·imbalance
        - λ_vol·volatility_penalty
        - λ_dd·drawdown_penalty
        - λ_spread·spread_penalty

Key Differences from v2.7:
1. Asymmetric treatment of gains/losses
2. Volatility-scaled contributions
3. Risk penalty terms (drawdown, spread)
4. Regime-aware adjustments
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import math

from trading.core.observables import TickObservables
from trading.core.state_register import TradingStateRegister


@dataclass(frozen=True)
class UtilityCoefficients:
    """
    Configurable coefficients for utility calculation.

    Analogous to v2.7 UtilityCoefficients.
    """

    # Signal contributions (can be positive or negative)
    c_momentum: float = 1.0      # Momentum contribution
    c_reversion: float = 1.0     # Mean-reversion contribution
    c_imbalance: float = 0.5     # Order imbalance contribution

    # Penalty terms (should be negative or zero)
    lambda_vol: float = -0.3     # Volatility penalty
    lambda_dd: float = -0.5      # Drawdown penalty
    lambda_spread: float = -0.2  # Spread penalty
    lambda_noise: float = -0.2   # Noise penalty

    def validate(self) -> None:
        """Validate coefficients are sensible."""
        # Penalties should be non-positive
        if self.lambda_vol > 0:
            raise ValueError("lambda_vol should be <= 0")
        if self.lambda_dd > 0:
            raise ValueError("lambda_dd should be <= 0")
        if self.lambda_spread > 0:
            raise ValueError("lambda_spread should be <= 0")
        if self.lambda_noise > 0:
            raise ValueError("lambda_noise should be <= 0")


@dataclass(frozen=True)
class UtilityResult:
    """Result of utility calculation with breakdown."""

    utility: float                    # Final utility value
    signal_contribution: float        # Contribution from signals
    volatility_penalty: float         # Penalty from volatility
    drawdown_penalty: float           # Penalty from drawdown
    spread_penalty: float             # Penalty from spread
    noise_penalty: float              # Penalty from noise
    regime_adjustment: float          # Regime-based adjustment

    @property
    def total_penalty(self) -> float:
        """Sum of all penalties."""
        return (
            self.volatility_penalty +
            self.drawdown_penalty +
            self.spread_penalty +
            self.noise_penalty
        )

    @property
    def is_favorable(self) -> bool:
        """Check if utility is positive (favorable for entry)."""
        return self.utility > 0

    @property
    def signal_to_penalty_ratio(self) -> float:
        """Ratio of signal strength to penalties (higher is better)."""
        if self.total_penalty == 0:
            return float('inf') if self.signal_contribution > 0 else 0
        return abs(self.signal_contribution / self.total_penalty)


class TradingUtility:
    """
    Trading utility calculator.

    Computes risk-adjusted utility from observables and state.
    Supports asymmetric treatment and regime awareness.
    """

    def __init__(
        self,
        coefficients: Optional[UtilityCoefficients] = None,
        enable_asymmetric: bool = True,
        enable_regime_adjustment: bool = True,
    ):
        self.coefficients = coefficients or UtilityCoefficients()
        self.coefficients.validate()
        self.enable_asymmetric = enable_asymmetric
        self.enable_regime_adjustment = enable_regime_adjustment

    def compute_utility(
        self,
        obs: TickObservables,
        state: TradingStateRegister,
        recent_pnl: float = 0.0,  # Recent P&L for asymmetric
    ) -> UtilityResult:
        """
        Compute utility from observables and current state.

        Args:
            obs: Current tick observables
            state: Current trading state
            recent_pnl: Recent P&L change (for asymmetric adjustment)

        Returns:
            UtilityResult with utility value and breakdown
        """
        c = self.coefficients

        # Signal contribution (weighted by state)
        signal_raw = (
            c.c_momentum * obs.momentum * state.w_momentum +
            c.c_reversion * obs.mean_reversion * state.w_reversion +
            c.c_imbalance * obs.order_imbalance * state.w_noise
        )

        # Apply asymmetric adjustment based on recent P&L
        if self.enable_asymmetric and recent_pnl != 0:
            # If we're losing, be more cautious (reduce positive signals)
            # If we're winning, be slightly more aggressive
            if recent_pnl < 0:
                # Losing: reduce bullish signals, amplify bearish warnings
                asymmetric_factor = 0.8 if signal_raw > 0 else 1.2
            else:
                # Winning: slight boost to confidence
                asymmetric_factor = 1.1 if signal_raw > 0 else 0.9
            signal_contribution = signal_raw * asymmetric_factor
        else:
            signal_contribution = signal_raw

        # Volatility penalty (increases with vol ratio)
        vol_excess = max(0, obs.tick_volatility - 1.0)
        volatility_penalty = c.lambda_vol * vol_excess

        # Drawdown penalty (increases with drawdown)
        drawdown_penalty = c.lambda_dd * state.drawdown

        # Spread penalty (increases with spread)
        spread_excess = max(0, obs.spread_normalized - 1.0)
        spread_penalty = c.lambda_spread * spread_excess

        # Noise penalty
        noise_excess = max(0, obs.noise_level - 0.5)
        noise_penalty = c.lambda_noise * noise_excess

        # Regime adjustment
        regime_adjustment = 0.0
        if self.enable_regime_adjustment:
            if state.regime == "crisis":
                # In crisis: heavily dampen signals
                regime_adjustment = -abs(signal_contribution) * 0.5
            elif state.regime == "trending":
                # In trend: boost momentum, reduce reversion
                if obs.momentum * c.c_momentum > 0:
                    regime_adjustment = 0.1 * abs(obs.momentum)
            elif state.regime == "ranging":
                # In range: boost reversion, reduce momentum
                if obs.mean_reversion * c.c_reversion > 0:
                    regime_adjustment = 0.1 * abs(obs.mean_reversion)

        # Final utility
        utility = (
            signal_contribution +
            volatility_penalty +
            drawdown_penalty +
            spread_penalty +
            noise_penalty +
            regime_adjustment
        )

        return UtilityResult(
            utility=utility,
            signal_contribution=signal_contribution,
            volatility_penalty=volatility_penalty,
            drawdown_penalty=drawdown_penalty,
            spread_penalty=spread_penalty,
            noise_penalty=noise_penalty,
            regime_adjustment=regime_adjustment,
        )

    def compute_target_state(
        self,
        obs: TickObservables,
        current_state: TradingStateRegister,
        utility_result: UtilityResult,
    ) -> TradingStateRegister:
        """
        Compute target state based on observables and utility.

        This is the θ* in the EMA update: θ_{t+1} = (1-α)θ_t + αθ*

        The target state represents what the state "should" be
        given current market conditions.
        """
        # Adjust thresholds based on utility
        # High positive utility -> lower entry threshold (easier to enter)
        # Negative utility -> higher entry threshold (harder to enter)
        utility_normalized = max(-1, min(1, utility_result.utility))

        # Entry threshold: inversely related to utility
        target_tau_entry = 0.5 - 0.2 * utility_normalized
        target_tau_entry = max(0.1, min(0.9, target_tau_entry))

        # Exit threshold: directly related to volatility
        vol_factor = min(1, obs.tick_volatility / 2)
        target_tau_exit = 0.3 + 0.2 * vol_factor
        target_tau_exit = max(0.1, min(0.9, target_tau_exit))

        # Adjust weights based on regime
        if obs.tick_volatility > 2.0:
            # High vol: favor noise filtering
            target_w_mom = 0.2
            target_w_rev = 0.2
            target_w_noise = 0.6
        elif abs(obs.momentum) > abs(obs.mean_reversion):
            # Strong momentum: favor momentum
            target_w_mom = 0.5
            target_w_rev = 0.3
            target_w_noise = 0.2
        else:
            # Mean reverting: favor reversion
            target_w_mom = 0.3
            target_w_rev = 0.5
            target_w_noise = 0.2

        # Adjust position scalar based on risk
        # Lower utility or higher drawdown -> lower position
        position_factor = (1 + utility_normalized) / 2  # [0, 1]
        risk_factor = 1 - current_state.drawdown
        target_position_scalar = position_factor * risk_factor

        # Volatility anchor: EMA toward current vol
        target_vol_anchor = obs.tick_volatility * current_state.volatility_anchor

        # Detect regime
        if obs.tick_volatility > 2.5:
            target_regime = "crisis"
        elif abs(obs.momentum) > 0.5 and obs.tick_intensity > 1.5:
            target_regime = "trending"
        elif abs(obs.mean_reversion) > 0.5 and obs.tick_intensity < 0.8:
            target_regime = "ranging"
        else:
            target_regime = current_state.regime

        return TradingStateRegister(
            tau_entry=target_tau_entry,
            tau_exit=target_tau_exit,
            w_momentum=target_w_mom,
            w_reversion=target_w_rev,
            w_noise=target_w_noise,
            position_scalar=target_position_scalar,
            volatility_anchor=max(0.001, min(1.0, target_vol_anchor)),
            regime=target_regime,
            drawdown=current_state.drawdown,
            tick_count=obs.tick_number,
            last_update_tick=obs.tick_number,
        )

    def should_enter(
        self,
        utility_result: UtilityResult,
        state: TradingStateRegister,
        signal: float,
    ) -> bool:
        """
        Determine if entry signal should be acted on.

        Args:
            utility_result: Computed utility
            state: Current state
            signal: Composite signal [-1, 1]

        Returns:
            True if entry conditions are met
        """
        # Must have positive utility
        if not utility_result.is_favorable:
            return False

        # Signal must exceed entry threshold
        if abs(signal) < state.tau_entry:
            return False

        # Must not be in crisis mode
        if state.is_crisis_mode:
            return False

        # Signal to penalty ratio must be acceptable
        if utility_result.signal_to_penalty_ratio < 1.5:
            return False

        return True

    def should_exit(
        self,
        utility_result: UtilityResult,
        state: TradingStateRegister,
        signal: float,
        position_direction: int,  # 1 for long, -1 for short
    ) -> bool:
        """
        Determine if exit signal should be acted on.

        Args:
            utility_result: Computed utility
            state: Current state
            signal: Composite signal [-1, 1]
            position_direction: Current position direction

        Returns:
            True if exit conditions are met
        """
        # Crisis mode: always exit
        if state.is_crisis_mode:
            return True

        # High drawdown: exit
        if state.drawdown > 0.08:
            return True

        # Signal reversal beyond exit threshold
        signal_against = -position_direction * signal
        if signal_against > state.tau_exit:
            return True

        # Negative utility: consider exit
        if utility_result.utility < -0.3:
            return True

        return False
