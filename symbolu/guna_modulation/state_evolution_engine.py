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

**Architectural Note: Temporal State (Fix #5)**

v2.7 introduces bounded temporal memory via the state register θ_t.
This is a deliberate departure from v2.6's stateless model.

What it IS:
- A low-pass filter over observable signals
- Bounded by hard limits (cannot drift arbitrarily)
- Reversible by decay toward θ_0
- Deterministic given the same history

What it is NOT:
- Stochastic learning (no gradient updates)
- Preference formation (no evaluation of "good" outcomes)
- Memory of specific queries (only aggregate statistics)

Enterprise Implication: If v2_7_enabled=True, the system's behavior at
time t depends on prior observations. Audit trails include full state
history for reproducibility.

Version: 2.7.1
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
    VALIDATION_EPSILON,
)
from symbolu.guna_modulation.observables import Observables
from symbolu.guna_modulation.utility import (
    compute_utility,
    compute_target_state,
    UtilityAudit,
    TargetStateAudit,
)

# Import new configuration from v27_config
from symbolu.guna_modulation.v27_config import (
    V27Config,
    UtilityCoefficients,
    ToneLogitConfig,
    AlphaConfig,
    StatePersistenceConfig,
    DEFAULT_V27_CONFIG,
    ENABLED_V27_CONFIG,
    ENTERPRISE_T1_CONFIG,
    ENTERPRISE_T2_CONFIG,
    CONSUMER_CONFIG,
    DEFAULT_UTILITY_COEFFICIENTS,
    DEFAULT_TONE_CONFIG,
    DEFAULT_ALPHA_CONFIG,
    DEFAULT_PERSISTENCE_CONFIG,
    TIER_ENTERPRISE_1,
    TIER_ENTERPRISE_2,
    TIER_CONSUMER,
    get_alpha_for_tier,
    # Alpha 2.7: Bayesian imports
    UpdateMode,
    BayesianConfig,
    BayesianPosterior,
    BayesianStateRegister,
    DEFAULT_BAYESIAN_CONFIG,
    BAYESIAN_V27_CONFIG,
    BAYESIAN_ENTERPRISE_T1,
    BAYESIAN_ENTERPRISE_T2,
    BAYESIAN_CONSUMER,
)


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

    # Tier info
    tier: str = "enterprise_tier_2"
    half_life_updates: float = 14.0

    # Alpha 2.7: Update mode info
    update_mode: str = "ema"  # "ema" or "bayesian"
    bayesian_confidence: Optional[float] = None  # Overall confidence (Bayesian mode)
    bayesian_uncertainty: Optional[dict] = None  # Per-param uncertainty (Bayesian mode)

    @property
    def explanation(self) -> str:
        """Human-readable explanation of the update."""
        if not self.v2_7_enabled:
            return "v2.7 disabled: state unchanged (v2.6 stateless mode)"

        if self.delta.is_zero:
            return "State unchanged (delta within epsilon)"

        lines = []

        if abs(self.delta.delta_tau_768) > VALIDATION_EPSILON:
            direction = "increased" if self.delta.delta_tau_768 > 0 else "decreased"
            lines.append(
                f"tau_768 {direction} by {abs(self.delta.delta_tau_768):.4f} "
                f"(U={self.utility:.3f}, H={self.observables.H:.3f})"
            )

        if abs(self.delta.delta_tau_175) > VALIDATION_EPSILON:
            direction = "increased" if self.delta.delta_tau_175 > 0 else "decreased"
            lines.append(
                f"tau_175 {direction} by {abs(self.delta.delta_tau_175):.4f} "
                f"(U={self.utility:.3f}, C_contr={self.observables.C_contr:.3f})"
            )

        if any(abs(d) > VALIDATION_EPSILON for d in self.delta.delta_w_tone):
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

    Supports two update modes (Alpha 2.7):

    EMA Mode (default):
        θ_{t+1} = clip((1 - α) × θ_t + α × θ*_t, bounds)
        - Bounded by design
        - Fixed learning rate
        - No uncertainty quantification

    Bayesian Mode (Alpha 2.7):
        P(θ | data) ∝ P(data | θ) × P(θ)
        - Natural bounds via priors
        - Adaptive learning rate (automatic)
        - Full uncertainty quantification

    Properties:
        - Deterministic: same inputs → same outputs
        - Bounded: all values stay within hard bounds
        - Reversible: by decay toward θ_0
        - Auditable: every update logged

    Tier-specific behavior (Fix #2):
        - Enterprise T1: α=0.02, half-life≈35 updates (ultra-stable)
        - Enterprise T2: α=0.05, half-life≈14 updates (moderate)
        - Consumer: α=0.10, half-life≈7 updates (faster response)
    """

    def __init__(
        self,
        config: V27Config = None,
        bounds: StateBounds = DEFAULT_BOUNDS,
        initial_state: Optional[StateRegister] = None,
    ):
        """
        Initialize the state evolution engine.

        Args:
            config: v2.7 configuration (includes all settings)
            bounds: Hard bounds for state values
            initial_state: Starting state (defaults to DEFAULT_STATE)
        """
        self._config = config or DEFAULT_V27_CONFIG
        self._bounds = bounds
        self._state = initial_state or DEFAULT_STATE
        self._update_count = 0

        # Alpha 2.7: Initialize Bayesian state if in Bayesian mode
        if self._config.is_bayesian:
            self._bayesian_state = BayesianStateRegister.from_config(
                self._config.bayesian_config
            )
        else:
            self._bayesian_state = None

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

    @property
    def alpha(self) -> float:
        """Current learning rate α."""
        return self._config.alpha

    @property
    def tier(self) -> str:
        """Current tier name."""
        return self._config.tier

    @property
    def half_life(self) -> float:
        """Half-life in updates."""
        return self._config.half_life

    # Alpha 2.7: Bayesian properties
    @property
    def is_bayesian(self) -> bool:
        """Whether using Bayesian update mode."""
        return self._config.is_bayesian

    @property
    def bayesian_state(self) -> Optional[BayesianStateRegister]:
        """Bayesian state with posteriors (None if in EMA mode)."""
        return self._bayesian_state

    @property
    def bayesian_confidence(self) -> Optional[float]:
        """Overall confidence from Bayesian posteriors (None if in EMA mode)."""
        if self._bayesian_state:
            return self._bayesian_state.overall_confidence
        return None

    @property
    def update_mode(self) -> str:
        """Current update mode as string."""
        return self._config.update_mode.value

    def update(self, observables: Observables) -> StateUpdateAudit:
        """
        Perform one state update step.

        If v2.7 is disabled, returns audit showing no change (v2.6 stateless mode).
        If v2.7 is enabled:
            - EMA mode: applies deterministic EMA update equation
            - Bayesian mode (Alpha 2.7): applies Bayesian posterior update

        Args:
            observables: Observable signals from pipeline

        Returns:
            StateUpdateAudit with complete audit trail
        """
        run_id = str(uuid.uuid4())[:8]
        timestamp = datetime.utcnow().isoformat()

        # Compute utility with configurable coefficients
        utility, utility_audit = compute_utility(
            observables,
            self._state,
            coefficients=self._config.utility_coefficients,
        )

        # Compute target state with configurable tone coefficients
        target_state, target_audit = compute_target_state(
            observables,
            utility,
            self._state,
            self._bounds,
            tone_config=self._config.tone_config,
        )

        # Evaluate rules
        rules = self._evaluate_rules(observables, utility)

        state_before = self._state

        # Alpha 2.7: Bayesian state tracking
        bayesian_confidence = None
        bayesian_uncertainty = None

        if not self._config.v2_7_enabled:
            # v2.6 behavior: state remains constant (stateless)
            state_after = state_before
        elif self._config.is_bayesian:
            # Alpha 2.7 Bayesian mode: apply Bayesian update
            state_after = self._apply_bayesian_update(state_before, target_state, observables)
            self._state = state_after
            self._update_count += 1

            # Record Bayesian-specific metrics
            if self._bayesian_state:
                bayesian_confidence = self._bayesian_state.overall_confidence
                bayesian_uncertainty = self._bayesian_state.uncertainty_summary
        else:
            # v2.7 EMA mode: apply EMA update equation (bounded temporal memory)
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
            tier=self._config.tier,
            half_life_updates=self._config.half_life,
            update_mode=self._config.update_mode.value,
            bayesian_confidence=bayesian_confidence,
            bayesian_uncertainty=bayesian_uncertainty,
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

    def _apply_bayesian_update(
        self,
        current: StateRegister,
        target: StateRegister,
        observables: Observables,
    ) -> StateRegister:
        """
        Apply Bayesian posterior update (Alpha 2.7).

        Instead of EMA blending, updates Beta posteriors with observations.
        The posterior mean is used as the point estimate.

        P(θ | data) ∝ P(data | θ) × P(θ)

        Key differences from EMA:
        - Learning rate is adaptive (based on posterior variance)
        - Uncertainty is quantified
        - Prior knowledge is incorporated
        """
        if self._bayesian_state is None:
            # Fallback to EMA if Bayesian state not initialized
            return self._apply_update(current, target)

        # Observation weight based on utility (higher utility = more weight)
        # This creates an adaptive learning rate
        base_weight = 1.0
        utility_factor = 0.5 + 0.5 * max(-1, min(1, observables.s - observables.t))
        observation_weight = base_weight * utility_factor

        # Update posteriors with target values as observations
        self._bayesian_state.tau_768_posterior = (
            self._bayesian_state.tau_768_posterior.update(
                target.tau_768, observation_weight
            )
        )
        self._bayesian_state.tau_175_posterior = (
            self._bayesian_state.tau_175_posterior.update(
                target.tau_175, observation_weight
            )
        )

        # Update w_tone posteriors
        self._bayesian_state.w_tone_sweet_posterior = (
            self._bayesian_state.w_tone_sweet_posterior.update(
                target.w_tone[0], observation_weight
            )
        )
        self._bayesian_state.w_tone_jolt_posterior = (
            self._bayesian_state.w_tone_jolt_posterior.update(
                target.w_tone[1], observation_weight
            )
        )
        self._bayesian_state.w_tone_metaphor_posterior = (
            self._bayesian_state.w_tone_metaphor_posterior.update(
                target.w_tone[2], observation_weight
            )
        )

        # Update b_policy posterior
        self._bayesian_state.b_policy_posterior = (
            self._bayesian_state.b_policy_posterior.update(
                target.b_policy, observation_weight
            )
        )

        # Extract point estimates (posterior means) with bounds
        new_tau_768 = self._bounds.clip_tau_768(
            self._bayesian_state.tau_768
        )
        new_tau_175 = self._bounds.clip_tau_175(
            self._bayesian_state.tau_175
        )
        new_w_tone = normalize_weights(self._bayesian_state.w_tone)
        new_b_policy = self._bounds.clip_b_policy(
            self._bayesian_state.b_policy
        )

        return StateRegister(
            tau_768=new_tau_768,
            tau_175=new_tau_175,
            w_tone=new_w_tone,
            w_guna=current.w_guna,  # Unchanged
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

    def apply_restart_decay(self) -> StateRegister:
        """
        Apply restart decay based on persistence config.

        Formula: θ_restart = factor × θ_saved + (1 - factor) × θ_0

        Returns:
            Decayed state
        """
        if not self._config.persistence_config.decay_on_restart:
            return self._state

        factor = self._config.persistence_config.restart_decay_factor
        one_minus_factor = 1.0 - factor
        default = DEFAULT_STATE

        decayed_tau_768 = factor * self._state.tau_768 + one_minus_factor * default.tau_768
        decayed_tau_175 = factor * self._state.tau_175 + one_minus_factor * default.tau_175
        decayed_w_tone = normalize_weights((
            factor * self._state.w_tone[0] + one_minus_factor * default.w_tone[0],
            factor * self._state.w_tone[1] + one_minus_factor * default.w_tone[1],
            factor * self._state.w_tone[2] + one_minus_factor * default.w_tone[2],
        ))
        decayed_b_policy = factor * self._state.b_policy + one_minus_factor * default.b_policy

        self._state = StateRegister(
            tau_768=self._bounds.clip_tau_768(decayed_tau_768),
            tau_175=self._bounds.clip_tau_175(decayed_tau_175),
            w_tone=decayed_w_tone,
            w_guna=self._state.w_guna,  # w_guna unchanged
            b_policy=self._bounds.clip_b_policy(decayed_b_policy),
        )
        return self._state


# =============================================================================
# Factory Functions
# =============================================================================

def create_evolution_engine(
    enabled: bool = False,
    alpha: float = DEFAULT_ALPHA,
    initial_state: Optional[StateRegister] = None,
) -> StateEvolutionEngine:
    """
    Create a state evolution engine (legacy interface).

    Args:
        enabled: Whether v2.7 is enabled
        alpha: Learning rate
        initial_state: Initial state (defaults to DEFAULT_STATE)

    Returns:
        Configured StateEvolutionEngine
    """
    # Use new V27Config but with legacy alpha parameter
    from symbolu.guna_modulation.v27_config import AlphaConfig
    config = V27Config(
        v2_7_enabled=enabled,
        alpha_config=AlphaConfig(alpha=alpha, tier="custom"),
    )
    return StateEvolutionEngine(config=config, initial_state=initial_state)


def create_v26_engine() -> StateEvolutionEngine:
    """Create engine that behaves like v2.6 (no evolution, stateless)."""
    return StateEvolutionEngine(config=V27Config.disabled())


def create_v27_engine(
    alpha: float = DEFAULT_ALPHA,
    initial_state: Optional[StateRegister] = None,
) -> StateEvolutionEngine:
    """Create engine with v2.7 evolution enabled (default tier)."""
    return create_evolution_engine(enabled=True, alpha=alpha, initial_state=initial_state)


def create_state_engine_for_tier(
    tier: str,
    enabled: bool = True,
    initial_state: Optional[StateRegister] = None,
    bayesian: bool = False,
) -> StateEvolutionEngine:
    """
    Create state evolution engine for a specific tier with appropriate alpha.

    Args:
        tier: "enterprise_tier_1", "enterprise_tier_2", or "consumer"
        enabled: Whether v2.7 is enabled
        initial_state: Initial state
        bayesian: Whether to use Bayesian mode (Alpha 2.7)

    Returns:
        Configured StateEvolutionEngine with tier-specific settings
    """
    config = V27Config.for_tier(tier, enabled=enabled, bayesian=bayesian)
    return StateEvolutionEngine(config=config, initial_state=initial_state)


# =============================================================================
# Alpha 2.7: Bayesian Factory Functions
# =============================================================================

def create_bayesian_engine(
    tier: str = TIER_ENTERPRISE_2,
    prior_strength: float = 10.0,
    initial_state: Optional[StateRegister] = None,
) -> StateEvolutionEngine:
    """
    Create state evolution engine with Bayesian update mode (Alpha 2.7).

    Args:
        tier: Tier for fallback settings
        prior_strength: Prior strength for Bayesian updates
        initial_state: Initial state (defaults to DEFAULT_STATE)

    Returns:
        StateEvolutionEngine with Bayesian mode enabled
    """
    config = V27Config.bayesian(tier=tier, prior_strength=prior_strength)
    return StateEvolutionEngine(config=config, initial_state=initial_state)


def create_bayesian_engine_for_tier(
    tier: str,
    prior_strength: float = 10.0,
    initial_state: Optional[StateRegister] = None,
) -> StateEvolutionEngine:
    """
    Create Bayesian engine for a specific tier.

    Args:
        tier: "enterprise_tier_1", "enterprise_tier_2", or "consumer"
        prior_strength: Prior strength (higher = more resistant to change)
        initial_state: Initial state

    Returns:
        StateEvolutionEngine with Bayesian mode and tier-specific settings
    """
    return create_bayesian_engine(
        tier=tier,
        prior_strength=prior_strength,
        initial_state=initial_state,
    )


# =============================================================================
# Standalone Update Function
# =============================================================================

def update_state(
    state: StateRegister,
    observables: Observables,
    config: V27Config = None,
    bounds: StateBounds = DEFAULT_BOUNDS,
) -> Tuple[StateRegister, StateUpdateAudit]:
    """
    Perform a single state update (functional interface).

    This is a pure function: same inputs → same outputs.

    Args:
        state: Current state θ_t
        observables: Observable signals
        config: v2.7 configuration (default: disabled)
        bounds: State bounds

    Returns:
        (new_state, audit) tuple
    """
    if config is None:
        config = DEFAULT_V27_CONFIG
    engine = StateEvolutionEngine(config=config, bounds=bounds, initial_state=state)
    audit = engine.update(observables)
    return engine.state, audit
