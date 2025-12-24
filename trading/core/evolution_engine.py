"""
Trading State Evolution Engine
==============================

Tick-based state evolution engine, adapted from v2.7 StateEvolutionEngine.

Core Update Formula (from v2.7):
    θ_{t+1} = (1 - α) · θ_t + α · θ*

Trading Extensions:
1. Asymmetric α: learn faster from losses
2. Regime-aware updates: freeze in crisis
3. Circuit breakers: reset on max drawdown
4. Tick-based timing (not time-based)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from datetime import datetime
import json

from trading.core.state_register import TradingStateRegister, RegimeType
from trading.core.observables import TickObservables
from trading.core.utility import TradingUtility, UtilityResult
from trading.core.config import TradingConfig, AlphaConfig, RiskConfig


@dataclass
class EvolutionAuditEntry:
    """Audit log entry for state evolution."""

    tick_number: int
    timestamp: str
    state_before: dict
    state_after: dict
    observables: dict
    utility: float
    alpha_used: float
    action: str  # "update", "crisis_freeze", "circuit_break", "skip"

    def to_json(self) -> str:
        return json.dumps({
            "tick": self.tick_number,
            "ts": self.timestamp,
            "before": self.state_before,
            "after": self.state_after,
            "obs": self.observables,
            "U": self.utility,
            "alpha": self.alpha_used,
            "action": self.action,
        })


@dataclass
class TradingEvolutionEngine:
    """
    Tick-based state evolution engine for trading.

    Manages state updates with:
    - EMA blending (v2.7 core formula)
    - Asymmetric learning rates
    - Crisis mode handling
    - Circuit breakers
    - Full audit trail
    """

    config: TradingConfig
    utility_calculator: TradingUtility = field(default_factory=TradingUtility)
    state: TradingStateRegister = field(default_factory=TradingStateRegister)
    audit_log: List[EvolutionAuditEntry] = field(default_factory=list)

    # Tracking
    ticks_processed: int = 0
    last_pnl: float = 0.0
    peak_equity: float = 1.0
    current_equity: float = 1.0

    # Circuit breaker state
    is_halted: bool = False
    halt_reason: Optional[str] = None

    def __post_init__(self):
        """Initialize utility calculator with config."""
        self.utility_calculator = TradingUtility(
            enable_asymmetric=self.config.enable_asymmetric,
            enable_regime_adjustment=self.config.enable_regime_detection,
        )

    def process_tick(
        self,
        obs: TickObservables,
        pnl_change: float = 0.0,
    ) -> Tuple[TradingStateRegister, UtilityResult, str]:
        """
        Process a single tick and evolve state.

        Args:
            obs: Tick observables
            pnl_change: P&L change since last tick (as fraction)

        Returns:
            Tuple of (new_state, utility_result, action_taken)
        """
        self.ticks_processed += 1

        # Update equity tracking
        self.current_equity *= (1 + pnl_change)
        self.peak_equity = max(self.peak_equity, self.current_equity)
        current_drawdown = 1 - (self.current_equity / self.peak_equity)

        # Update state with current drawdown
        state_with_dd = self.state.with_drawdown(current_drawdown)

        # Check circuit breakers
        if self.config.risk_config.should_halt(current_drawdown):
            return self._handle_circuit_break(obs, state_with_dd, "max_drawdown")

        if self.is_halted:
            return self._handle_halted(obs, state_with_dd)

        # Compute utility
        utility_result = self.utility_calculator.compute_utility(
            obs, state_with_dd, pnl_change
        )

        # Check for crisis mode
        vol_ratio = obs.tick_volatility
        if self.config.enable_crisis_mode:
            if self.config.risk_config.should_enter_crisis(current_drawdown, vol_ratio):
                return self._handle_crisis_mode(obs, state_with_dd, utility_result)

        # Normal update path
        return self._perform_update(obs, state_with_dd, utility_result, pnl_change)

    def _perform_update(
        self,
        obs: TickObservables,
        current_state: TradingStateRegister,
        utility_result: UtilityResult,
        pnl_change: float,
    ) -> Tuple[TradingStateRegister, UtilityResult, str]:
        """Perform normal EMA state update."""

        # Compute target state
        target_state = self.utility_calculator.compute_target_state(
            obs, current_state, utility_result
        )

        # Determine alpha (with asymmetric adjustment)
        base_alpha = self.config.alpha
        if self.config.enable_asymmetric:
            alpha = self.config.asymmetric_config.adjust_alpha(base_alpha, pnl_change)
        else:
            alpha = base_alpha

        # EMA blend: θ_{t+1} = (1 - α) · θ_t + α · θ*
        new_state = current_state.blend_with(target_state, alpha)

        # Log audit entry
        self._log_audit(
            obs, current_state, new_state, utility_result.utility, alpha, "update"
        )

        self.state = new_state
        self.last_pnl = pnl_change

        return new_state, utility_result, "update"

    def _handle_crisis_mode(
        self,
        obs: TickObservables,
        current_state: TradingStateRegister,
        utility_result: UtilityResult,
    ) -> Tuple[TradingStateRegister, UtilityResult, str]:
        """Handle crisis mode - reduce position, use crisis state."""

        # Set crisis regime
        crisis_state = TradingStateRegister.default_for_regime("crisis")

        # Blend quickly toward crisis state
        crisis_alpha = 0.3  # Fast transition to crisis mode
        new_state = current_state.blend_with(crisis_state, crisis_alpha)

        # Ensure crisis regime is set
        new_state = new_state.with_regime("crisis")

        # Reduce position scalar
        crisis_scalar = self.config.risk_config.crisis_position_scalar
        new_state = new_state.with_position_scalar(
            min(new_state.position_scalar, crisis_scalar)
        )

        self._log_audit(
            obs, current_state, new_state, utility_result.utility, crisis_alpha, "crisis_mode"
        )

        self.state = new_state
        return new_state, utility_result, "crisis_mode"

    def _handle_circuit_break(
        self,
        obs: TickObservables,
        current_state: TradingStateRegister,
        reason: str,
    ) -> Tuple[TradingStateRegister, UtilityResult, str]:
        """Handle circuit breaker activation."""

        self.is_halted = True
        self.halt_reason = reason

        # Reset to safe state
        safe_state = current_state.reset_to_defaults()
        safe_state = safe_state.with_position_scalar(0.0)
        safe_state = safe_state.with_regime("crisis")

        # Create minimal utility result
        utility_result = UtilityResult(
            utility=-1.0,
            signal_contribution=0.0,
            volatility_penalty=-0.5,
            drawdown_penalty=-0.5,
            spread_penalty=0.0,
            noise_penalty=0.0,
            regime_adjustment=0.0,
        )

        self._log_audit(
            obs, current_state, safe_state, utility_result.utility, 0.0, f"circuit_break:{reason}"
        )

        self.state = safe_state
        return safe_state, utility_result, f"circuit_break:{reason}"

    def _handle_halted(
        self,
        obs: TickObservables,
        current_state: TradingStateRegister,
    ) -> Tuple[TradingStateRegister, UtilityResult, str]:
        """Handle already halted state - check for recovery."""

        # Check if we can recover (drawdown improved)
        if current_state.drawdown < self.config.risk_config.warning_drawdown:
            # Allow recovery with slow alpha
            self.is_halted = False
            self.halt_reason = None

            recovery_state = current_state.with_regime("unknown")
            recovery_state = recovery_state.with_position_scalar(
                self.config.risk_config.crisis_position_scalar
            )

            utility_result = UtilityResult(
                utility=0.0,
                signal_contribution=0.0,
                volatility_penalty=0.0,
                drawdown_penalty=0.0,
                spread_penalty=0.0,
                noise_penalty=0.0,
                regime_adjustment=0.0,
            )

            self._log_audit(
                obs, current_state, recovery_state, 0.0,
                self.config.risk_config.recovery_alpha, "recovery"
            )

            self.state = recovery_state
            return recovery_state, utility_result, "recovery"

        # Still halted
        utility_result = UtilityResult(
            utility=-1.0,
            signal_contribution=0.0,
            volatility_penalty=-0.5,
            drawdown_penalty=-0.5,
            spread_penalty=0.0,
            noise_penalty=0.0,
            regime_adjustment=0.0,
        )

        return current_state, utility_result, "halted"

    def _log_audit(
        self,
        obs: TickObservables,
        state_before: TradingStateRegister,
        state_after: TradingStateRegister,
        utility: float,
        alpha: float,
        action: str,
    ) -> None:
        """Log audit entry for state transition."""

        # Only log every N ticks to save memory
        if self.ticks_processed % self.config.state_snapshot_interval != 0:
            if action == "update":
                return  # Skip routine updates

        entry = EvolutionAuditEntry(
            tick_number=self.ticks_processed,
            timestamp=datetime.utcnow().isoformat(),
            state_before=state_before.to_dict(),
            state_after=state_after.to_dict(),
            observables=obs.to_dict(),
            utility=utility,
            alpha_used=alpha,
            action=action,
        )
        self.audit_log.append(entry)

        # Limit audit log size
        if len(self.audit_log) > 10000:
            self.audit_log = self.audit_log[-5000:]

    def get_signal(self, obs: TickObservables) -> float:
        """
        Get composite trading signal from observables.

        Returns signal in [-1, 1]:
        - Positive = bullish
        - Negative = bearish
        - Near zero = neutral
        """
        raw_signal = obs.compute_composite_signal(
            w_momentum=self.state.w_momentum,
            w_reversion=self.state.w_reversion,
            w_imbalance=self.state.w_noise,
        )

        # Apply volatility and noise adjustments
        adj_signal = obs.volatility_adjusted_signal(raw_signal)
        adj_signal = obs.noise_adjusted_signal(adj_signal)

        # Scale by position scalar
        adj_signal *= self.state.position_scalar

        return adj_signal

    def should_enter(self, obs: TickObservables) -> Tuple[bool, float, str]:
        """
        Check if entry conditions are met.

        Returns:
            Tuple of (should_enter, signal, reason)
        """
        if self.is_halted:
            return False, 0.0, "halted"

        if self.state.is_crisis_mode:
            return False, 0.0, "crisis_mode"

        signal = self.get_signal(obs)

        utility_result = self.utility_calculator.compute_utility(
            obs, self.state, self.last_pnl
        )

        should = self.utility_calculator.should_enter(
            utility_result, self.state, signal
        )

        if should:
            direction = "long" if signal > 0 else "short"
            return True, signal, f"entry_{direction}"
        else:
            if abs(signal) < self.state.tau_entry:
                return False, signal, "signal_below_threshold"
            if not utility_result.is_favorable:
                return False, signal, "utility_unfavorable"
            return False, signal, "conditions_not_met"

    def should_exit(
        self,
        obs: TickObservables,
        position_direction: int,
    ) -> Tuple[bool, float, str]:
        """
        Check if exit conditions are met.

        Args:
            obs: Current observables
            position_direction: 1 for long, -1 for short

        Returns:
            Tuple of (should_exit, signal, reason)
        """
        if self.is_halted:
            return True, 0.0, "halted"

        if self.state.is_crisis_mode:
            return True, 0.0, "crisis_mode"

        signal = self.get_signal(obs)

        utility_result = self.utility_calculator.compute_utility(
            obs, self.state, self.last_pnl
        )

        should = self.utility_calculator.should_exit(
            utility_result, self.state, signal, position_direction
        )

        if should:
            if self.state.drawdown > 0.08:
                return True, signal, "drawdown_exit"
            if utility_result.utility < -0.3:
                return True, signal, "utility_exit"
            return True, signal, "signal_reversal"

        return False, signal, "hold"

    def reset(self, preserve_audit: bool = False) -> None:
        """Reset engine to initial state."""
        self.state = TradingStateRegister()
        self.ticks_processed = 0
        self.last_pnl = 0.0
        self.peak_equity = 1.0
        self.current_equity = 1.0
        self.is_halted = False
        self.halt_reason = None

        if not preserve_audit:
            self.audit_log = []

    def apply_restart_decay(self, decay_factor: Optional[float] = None) -> None:
        """
        Apply restart decay to state (v2.7 concept).

        θ_restart = factor × θ_saved + (1 - factor) × θ_0
        """
        factor = decay_factor or self.config.risk_config.restart_decay_factor
        default_state = TradingStateRegister()

        self.state = default_state.blend_with(self.state, factor)

    def export_audit_log(self) -> List[dict]:
        """Export audit log as list of dicts."""
        return [
            {
                "tick": e.tick_number,
                "ts": e.timestamp,
                "utility": e.utility,
                "alpha": e.alpha_used,
                "action": e.action,
                "drawdown": e.state_after.get("drawdown", 0),
                "position_scalar": e.state_after.get("position_scalar", 1),
                "regime": e.state_after.get("regime", "unknown"),
            }
            for e in self.audit_log
        ]


def create_trading_engine_for_tier(
    tier: str,
    risk_profile: str = "moderate",
) -> TradingEvolutionEngine:
    """
    Factory to create trading engine for specified tier.

    Args:
        tier: "scalper", "daytrader", "swing", or "position"
        risk_profile: "conservative", "moderate", or "aggressive"

    Returns:
        Configured TradingEvolutionEngine
    """
    config = TradingConfig.for_tier(tier, risk_profile)
    return TradingEvolutionEngine(config=config)
