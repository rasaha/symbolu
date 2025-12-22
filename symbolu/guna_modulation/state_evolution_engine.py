"""
State Evolution Engine for SymbolU v2.7
=======================================

The core v2.7 boundary: deterministic state update.

This engine:
1. Evaluates runs using explicit formulas
2. Computes policy-aligned utility
3. Produces target state
4. Updates state using bounded deterministic rule
5. Emits machine-auditable explanation

This is NOT learning. This is deterministic state evolution.

Version: 2.7
Date: 2025-12-22
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime
import uuid

from symbolu.guna_modulation.state_types import (
    StateRegister,
    StateBounds,
    StateDelta,
    DEFAULT_STATE,
    DEFAULT_BOUNDS,
    DEFAULT_ALPHA,
    normalize_weights,
    clip,
    EPSILON,
)
from symbolu.guna_modulation.observables import Observables
from symbolu.guna_modulation.utility import (
    compute_utility,
    compute_target_state,
    UtilityAudit,
    TargetStateAudit,
)


# =============================================================================
# Configuration
# =============================================================================

@dataclass(frozen=True)
class V27Config:
    """
    Configuration for v2.7 state evolution.

    Attributes:
        v2_7_enabled: Master switch. When False, behaves like v2.6 (no evolution)
        alpha: Learning rate (fixed, not per-run configurable)
    """
    v2_7_enabled: bool = False  # Default: behave like v2.6
    alpha: float = DEFAULT_ALPHA

    def __post_init__(self):
        """Validate configuration."""
        if not (0.0 < self.alpha < 1.0):
            raise ValueError(f"alpha must be in (0, 1), got {self.alpha}")


# Default configuration (v2.7 disabled)
DEFAULT_V27_CONFIG = V27Config(v2_7_enabled=False)

# Enabled configuration
ENABLED_V27_CONFIG = V27Config(v2_7_enabled=True)


# =============================================================================
# Audit Types
# =============================================================================

@dataclass(frozen=True)
class RuleFired:
    """A rule that was evaluated during state update."""
    rule_id: str
    condition: str
    action: str
    fired: bool


@dataclass(frozen=True)
class StateUpdateAudit:
    """
    Complete audit trail for a state update.

    Contains all information needed to reproduce or verify the update.
    """
    # Identification
    run_id: str
    timestamp: str

    # Observed signals
    observables: Observables

    # Utility computation
    utility: float
    utility_audit: UtilityAudit

    # Target state computation
    target_state: StateRegister
    target_audit: TargetStateAudit

    # State before update
    state_before: StateRegister

    # State after update
    state_after: StateRegister

    # Applied delta
    delta: StateDelta

    # Rules evaluated
    rules_fired: Tuple[RuleFired, ...]

    # Version info
    v2_7_enabled: bool
    alpha: float

    @property
    def explanation(self) -> str:
        """Human-readable explanation of the update."""
        if not self.v2_7_enabled:
            return "v2.7 disabled: state unchanged"

        if self.delta.is_zero:
            return "State unchanged (delta within epsilon)"

        lines = []

        if abs(self.delta.delta_tau_768) > EPSILON:
            direction = "increased" if self.delta.delta_tau_768 > 0 else "decreased"
            lines.append(
                f"tau_768 {direction} by {abs(self.delta.delta_tau_768):.4f} "
                f"(U={self.utility:.3f}, H={self.observables.H:.3f})"
            )

        if abs(self.delta.delta_tau_175) > EPSILON:
            direction = "increased" if self.delta.delta_tau_175 > 0 else "decreased"
            lines.append(
                f"tau_175 {direction} by {abs(self.delta.delta_tau_175):.4f} "
                f"(U={self.utility:.3f}, C_contr={self.observables.C_contr:.3f})"
            )

        if any(abs(d) > EPSILON for d in self.delta.delta_w_tone):
            lines.append(
                f"w_tone shifted: sweet={self.delta.delta_w_tone[0]:+.4f}, "
                f"jolt={self.delta.delta_w_tone[1]:+.4f}, "
                f"metaphor={self.delta.delta_w_tone[2]:+.4f}"
            )

        return "; ".join(lines) if lines else "Minor adjustments applied"


# =============================================================================
# State Evolution Engine
# =============================================================================

class StateEvolutionEngine:
    """
    The v2.7 Deterministic State Evolution Engine.

    Core equation:
        θ_{t+1} = clip((1 - α) × θ_t + α × θ*_t, bounds)

    Properties:
        - Deterministic: same inputs → same outputs
        - Bounded: all values stay within hard bounds
        - Reversible: by decay toward θ_0
        - Auditable: every update logged
    """

    def __init__(
        self,
        config: V27Config = DEFAULT_V27_CONFIG,
        bounds: StateBounds = DEFAULT_BOUNDS,
        initial_state: Optional[StateRegister] = None,
    ):
        """
        Initialize the state evolution engine.

        Args:
            config: v2.7 configuration (includes enabled flag)
            bounds: Hard bounds for state values
            initial_state: Starting state (defaults to DEFAULT_STATE)
        """
        self._config = config
        self._bounds = bounds
        self._state = initial_state or DEFAULT_STATE
        self._update_count = 0

    @property
    def config(self) -> V27Config:
        """Current configuration."""
        return self._config

    @property
    def state(self) -> StateRegister:
        """Current state θ_t."""
        return self._state

    @property
    def is_enabled(self) -> bool:
        """Whether v2.7 evolution is enabled."""
        return self._config.v2_7_enabled

    def update(self, observables: Observables) -> StateUpdateAudit:
        """
        Perform one state update step.

        If v2.7 is disabled, returns audit showing no change.
        If v2.7 is enabled, applies deterministic update equation.

        Args:
            observables: Observable signals from pipeline

        Returns:
            StateUpdateAudit with complete audit trail
        """
        run_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().isoformat()

        # Compute utility
        utility, utility_audit = compute_utility(observables, self._state)

        # Compute target state
        target_state, target_audit = compute_target_state(
            observables, utility, self._state, self._bounds
        )

        # Evaluate rules
        rules = self._evaluate_rules(observables, utility)

        state_before = self._state

        if not self._config.v2_7_enabled:
            # v2.6 behavior: state remains constant
            state_after = state_before
        else:
            # v2.7 behavior: apply update equation
            state_after = self._apply_update(state_before, target_state)
            self._state = state_after
            self._update_count += 1

        delta = StateDelta.compute(state_before, state_after)

        return StateUpdateAudit(
            run_id=run_id,
            timestamp=timestamp,
            observables=observables,
            utility=utility,
            utility_audit=utility_audit,
            target_state=target_state,
            target_audit=target_audit,
            state_before=state_before,
            state_after=state_after,
            delta=delta,
            rules_fired=tuple(rules),
            v2_7_enabled=self._config.v2_7_enabled,
            alpha=self._config.alpha,
        )

    def _apply_update(
        self,
        current: StateRegister,
        target: StateRegister,
    ) -> StateRegister:
        """
        Apply the v2.7 update equation.

        θ_{t+1} = clip((1 - α) × θ_t + α × θ*_t, bounds)

        Deterministic, bounded, reversible.
        """
        alpha = self._config.alpha
        one_minus_alpha = 1.0 - alpha

        # Update tau_768
        new_tau_768 = self._bounds.clip_tau_768(
            one_minus_alpha * current.tau_768 + alpha * target.tau_768
        )

        # Update tau_175
        new_tau_175 = self._bounds.clip_tau_175(
            one_minus_alpha * current.tau_175 + alpha * target.tau_175
        )

        # Update w_tone (interpolate then normalize)
        new_w_tone_raw = (
            one_minus_alpha * current.w_tone[0] + alpha * target.w_tone[0],
            one_minus_alpha * current.w_tone[1] + alpha * target.w_tone[1],
            one_minus_alpha * current.w_tone[2] + alpha * target.w_tone[2],
        )
        new_w_tone = normalize_weights(new_w_tone_raw)

        # w_guna stays constant (only changes via config, not evolution)
        new_w_guna = current.w_guna

        # Update b_policy
        new_b_policy = self._bounds.clip_b_policy(
            one_minus_alpha * current.b_policy + alpha * target.b_policy
        )

        return StateRegister(
            tau_768=new_tau_768,
            tau_175=new_tau_175,
            w_tone=new_w_tone,
            w_guna=new_w_guna,
            b_policy=new_b_policy,
        )

    def _evaluate_rules(
        self,
        observables: Observables,
        utility: float,
    ) -> List[RuleFired]:
        """
        Evaluate diagnostic rules for audit trail.

        These rules don't affect computation, only explain what happened.
        """
        rules = []

        # High contradiction rule
        high_contr = observables.C_contr > 0.5
        rules.append(RuleFired(
            rule_id="RULE_HIGH_CONTRADICTION_TIGHTEN_175B",
            condition="C_contr > 0.5",
            action="Lower tau_175 threshold",
            fired=high_contr,
        ))

        # High entropy rule
        high_entropy = observables.H > 0.7
        rules.append(RuleFired(
            rule_id="RULE_HIGH_ENTROPY_CONSERVATIVE_SKIP",
            condition="H > 0.7",
            action="Lower tau_768 threshold",
            fired=high_entropy,
        ))

        # Low utility rule
        low_utility = utility < 0.0
        rules.append(RuleFired(
            rule_id="RULE_LOW_UTILITY_TIGHTEN_ESCALATION",
            condition="U < 0",
            action="Lower tau_175, adjust tone",
            fired=low_utility,
        ))

        # High Sattva rule
        high_sattva = observables.s > 0.6
        rules.append(RuleFired(
            rule_id="RULE_HIGH_SATTVA_SWEET_TONE",
            condition="s > 0.6",
            action="Increase sweet tone weight",
            fired=high_sattva,
        ))

        # High Rajas rule
        high_rajas = observables.r > 0.5
        rules.append(RuleFired(
            rule_id="RULE_HIGH_RAJAS_JOLT_METAPHOR",
            condition="r > 0.5",
            action="Increase jolt and metaphor weights",
            fired=high_rajas,
        ))

        return rules

    def reset(self, initial_state: Optional[StateRegister] = None) -> None:
        """
        Reset state to initial values.

        Args:
            initial_state: State to reset to (defaults to DEFAULT_STATE)
        """
        self._state = initial_state or DEFAULT_STATE
        self._update_count = 0


# =============================================================================
# Factory Functions
# =============================================================================

def create_evolution_engine(
    enabled: bool = False,
    alpha: float = DEFAULT_ALPHA,
    initial_state: Optional[StateRegister] = None,
) -> StateEvolutionEngine:
    """
    Create a state evolution engine.

    Args:
        enabled: Whether v2.7 is enabled
        alpha: Learning rate
        initial_state: Initial state (defaults to DEFAULT_STATE)

    Returns:
        Configured StateEvolutionEngine
    """
    config = V27Config(v2_7_enabled=enabled, alpha=alpha)
    return StateEvolutionEngine(config=config, initial_state=initial_state)


def create_v26_engine() -> StateEvolutionEngine:
    """Create engine that behaves like v2.6 (no evolution)."""
    return create_evolution_engine(enabled=False)


def create_v27_engine(
    alpha: float = DEFAULT_ALPHA,
    initial_state: Optional[StateRegister] = None,
) -> StateEvolutionEngine:
    """Create engine with v2.7 evolution enabled."""
    return create_evolution_engine(enabled=True, alpha=alpha, initial_state=initial_state)


# =============================================================================
# Standalone Update Function
# =============================================================================

def update_state(
    state: StateRegister,
    observables: Observables,
    config: V27Config = DEFAULT_V27_CONFIG,
    bounds: StateBounds = DEFAULT_BOUNDS,
) -> Tuple[StateRegister, StateUpdateAudit]:
    """
    Perform a single state update (functional interface).

    This is a pure function: same inputs → same outputs.

    Args:
        state: Current state θ_t
        observables: Observable signals
        config: v2.7 configuration
        bounds: State bounds

    Returns:
        (new_state, audit) tuple
    """
    engine = StateEvolutionEngine(config=config, bounds=bounds, initial_state=state)
    audit = engine.update(observables)
    return engine.state, audit
