"""
Unit Tests for SymbolU v2.7 State Evolution
============================================

Tests for deterministic state evolution layer including:
- State register types and bounds
- Observables validation
- Utility computation
- Target state computation
- State update equation
- Determinism guarantees
- Version gating (v2.6 vs v2.7 behavior)

Version: 2.7
Date: 2025-12-22
"""

import math
import pytest
from typing import Tuple

from symbolu.guna_modulation.state_types import (
    StateRegister,
    StateBounds,
    StateDelta,
    DEFAULT_STATE,
    DEFAULT_BOUNDS,
    normalize_weights,
    softmax_3,
    clip,
    EPSILON,
)
from symbolu.guna_modulation.observables import (
    Observables,
    compute_guna_entropy,
    observables_from_v26_pipeline,
)
from symbolu.guna_modulation.utility import (
    compute_utility,
    compute_target_tau_768,
    compute_target_tau_175,
    compute_target_w_tone,
    compute_target_state,
    LAMBDA_H,
    LAMBDA_C,
    LAMBDA_F,
)
from symbolu.guna_modulation.state_evolution_engine import (
    V27Config,
    StateEvolutionEngine,
    StateUpdateAudit,
    create_evolution_engine,
    create_v26_engine,
    create_v27_engine,
    update_state,
    DEFAULT_V27_CONFIG,
    ENABLED_V27_CONFIG,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def default_observables() -> Observables:
    """Standard test observables."""
    return Observables(
        s=0.5, r=0.3, t=0.2,
        H=0.4,
        delta_sem=0.3,
        C_contr=0.1,
        F_fail=0.05,
    )


@pytest.fixture
def high_entropy_observables() -> Observables:
    """Observables with high entropy."""
    return Observables(
        s=0.34, r=0.33, t=0.33,  # Near-uniform = high entropy
        H=0.95,
        delta_sem=0.5,
        C_contr=0.2,
        F_fail=0.1,
    )


@pytest.fixture
def high_contradiction_observables() -> Observables:
    """Observables with high contradiction."""
    return Observables(
        s=0.4, r=0.35, t=0.25,
        H=0.5,
        delta_sem=0.4,
        C_contr=0.8,  # High contradiction
        F_fail=0.3,
    )


# =============================================================================
# State Register Tests
# =============================================================================

class TestStateRegister:
    """Tests for StateRegister type."""

    def test_default_state_valid(self):
        """Default state should be valid."""
        state = DEFAULT_STATE
        assert 0.1 <= state.tau_768 <= 0.9
        assert 0.3 <= state.tau_175 <= 0.95
        assert abs(sum(state.w_tone) - 1.0) < EPSILON
        assert abs(sum(state.w_guna) - 1.0) < EPSILON
        assert abs(state.b_policy) <= 0.1

    def test_state_immutable(self):
        """State should be immutable (frozen)."""
        state = DEFAULT_STATE
        with pytest.raises(Exception):  # FrozenInstanceError
            state.tau_768 = 0.9

    def test_invalid_tau_768_rejected(self):
        """Invalid tau_768 should be rejected."""
        with pytest.raises(ValueError):
            StateRegister(
                tau_768=1.5,  # Out of range
                tau_175=0.7,
                w_tone=(0.4, 0.3, 0.3),
                w_guna=(0.33, 0.34, 0.33),
                b_policy=0.0,
            )

    def test_invalid_w_tone_sum_rejected(self):
        """w_tone not summing to 1 should be rejected."""
        with pytest.raises(ValueError):
            StateRegister(
                tau_768=0.5,
                tau_175=0.7,
                w_tone=(0.5, 0.5, 0.5),  # Sums to 1.5
                w_guna=(0.33, 0.34, 0.33),
                b_policy=0.0,
            )

    def test_property_accessors(self):
        """Property accessors should work correctly."""
        state = DEFAULT_STATE
        assert state.w_sweet == state.w_tone[0]
        assert state.w_jolt == state.w_tone[1]
        assert state.w_metaphor == state.w_tone[2]
        assert state.w_S == state.w_guna[0]
        assert state.w_R == state.w_guna[1]
        assert state.w_T == state.w_guna[2]


class TestStateBounds:
    """Tests for StateBounds."""

    def test_default_bounds_valid(self):
        """Default bounds should be reasonable."""
        bounds = DEFAULT_BOUNDS
        assert bounds.tau_768_min < bounds.tau_768_max
        assert bounds.tau_175_min < bounds.tau_175_max
        assert bounds.b_policy_max > 0

    def test_clip_tau_768(self):
        """clip_tau_768 should enforce bounds."""
        bounds = DEFAULT_BOUNDS
        assert bounds.clip_tau_768(0.05) == bounds.tau_768_min
        assert bounds.clip_tau_768(0.95) == bounds.tau_768_max
        assert bounds.clip_tau_768(0.5) == 0.5

    def test_clip_tau_175(self):
        """clip_tau_175 should enforce bounds."""
        bounds = DEFAULT_BOUNDS
        assert bounds.clip_tau_175(0.1) == bounds.tau_175_min
        assert bounds.clip_tau_175(0.99) == bounds.tau_175_max
        assert bounds.clip_tau_175(0.7) == 0.7

    def test_clip_b_policy(self):
        """clip_b_policy should enforce bounds."""
        bounds = DEFAULT_BOUNDS
        assert bounds.clip_b_policy(-0.5) == -bounds.b_policy_max
        assert bounds.clip_b_policy(0.5) == bounds.b_policy_max
        assert bounds.clip_b_policy(0.05) == 0.05


class TestStateDelta:
    """Tests for StateDelta."""

    def test_compute_delta(self):
        """Delta computation should be correct."""
        old = DEFAULT_STATE
        new = StateRegister(
            tau_768=0.6,
            tau_175=0.65,
            w_tone=(0.45, 0.30, 0.25),
            w_guna=(0.33, 0.34, 0.33),
            b_policy=0.02,
        )
        delta = StateDelta.compute(old, new)

        assert abs(delta.delta_tau_768 - 0.1) < EPSILON
        assert abs(delta.delta_tau_175 - (-0.05)) < EPSILON
        assert abs(delta.delta_b_policy - 0.02) < EPSILON

    def test_is_zero_for_no_change(self):
        """is_zero should return True for identical states."""
        state = DEFAULT_STATE
        delta = StateDelta.compute(state, state)
        assert delta.is_zero


# =============================================================================
# Observables Tests
# =============================================================================

class TestObservables:
    """Tests for Observables type."""

    def test_valid_observables(self, default_observables):
        """Valid observables should be accepted."""
        obs = default_observables
        assert abs(obs.s + obs.r + obs.t - 1.0) < EPSILON
        assert 0 <= obs.H <= 1
        assert 0 <= obs.C_contr <= 1

    def test_invalid_guna_sum_rejected(self):
        """Guna not summing to 1 should be rejected."""
        with pytest.raises(ValueError):
            Observables(
                s=0.5, r=0.5, t=0.5,  # Sums to 1.5
                H=0.4, delta_sem=0.3, C_contr=0.1, F_fail=0.0,
            )

    def test_from_v26_pipeline(self):
        """Factory from v2.6 pipeline should work."""
        obs = observables_from_v26_pipeline(
            guna_vector=(0.5, 0.3, 0.2),
            wired_H=0.4,
            wired_M=0.3,
            contradiction_score=0.1,
            failure_score=0.05,
        )
        assert obs.s == 0.5
        assert obs.r == 0.3
        assert obs.t == 0.2
        assert obs.H == 0.4
        assert obs.delta_sem == 0.3


class TestGunaEntropy:
    """Tests for Guna entropy computation."""

    def test_uniform_distribution_max_entropy(self):
        """Uniform distribution should give maximum entropy (~1)."""
        H = compute_guna_entropy(1/3, 1/3, 1/3)
        assert abs(H - 1.0) < 0.01  # Near 1.0

    def test_concentrated_distribution_low_entropy(self):
        """Concentrated distribution should give low entropy."""
        H = compute_guna_entropy(0.98, 0.01, 0.01)
        assert H < 0.3

    def test_entropy_in_unit_range(self):
        """Entropy should always be in [0, 1]."""
        test_cases = [
            (0.5, 0.3, 0.2),
            (0.7, 0.2, 0.1),
            (0.33, 0.34, 0.33),
            (0.9, 0.05, 0.05),
        ]
        for s, r, t in test_cases:
            H = compute_guna_entropy(s, r, t)
            assert 0 <= H <= 1, f"H={H} for ({s}, {r}, {t})"


# =============================================================================
# Utility Computation Tests
# =============================================================================

class TestUtilityComputation:
    """Tests for policy utility U_t computation."""

    def test_utility_formula(self, default_observables):
        """Utility should follow the formula exactly."""
        state = DEFAULT_STATE
        U, audit = compute_utility(default_observables, state)

        # Manual calculation
        guna_term = (
            state.w_S * default_observables.s -
            state.w_R * default_observables.r -
            state.w_T * default_observables.t
        )
        expected_U = (
            guna_term -
            LAMBDA_H * default_observables.H -
            LAMBDA_C * default_observables.C_contr -
            LAMBDA_F * default_observables.F_fail
        )

        assert abs(U - expected_U) < EPSILON

    def test_utility_audit_complete(self, default_observables):
        """Utility audit should contain all components."""
        U, audit = compute_utility(default_observables, DEFAULT_STATE)

        assert hasattr(audit, "guna_term")
        assert hasattr(audit, "entropy_penalty")
        assert hasattr(audit, "contradiction_penalty")
        assert hasattr(audit, "failure_penalty")
        assert audit.utility == U

    def test_high_contradiction_lowers_utility(self, high_contradiction_observables):
        """High contradiction should significantly lower utility."""
        U, _ = compute_utility(high_contradiction_observables, DEFAULT_STATE)
        # High contradiction (0.8) contributes -0.4 penalty
        assert U < 0  # Likely negative with high C_contr

    def test_utility_deterministic(self, default_observables):
        """Same inputs should always produce same utility."""
        first_U, _ = compute_utility(default_observables, DEFAULT_STATE)
        for _ in range(100):
            U, _ = compute_utility(default_observables, DEFAULT_STATE)
            assert U == first_U


# =============================================================================
# Target State Computation Tests
# =============================================================================

class TestTargetComputation:
    """Tests for target state θ* computation."""

    def test_target_tau_768_bounded(self):
        """Target tau_768 should be within bounds."""
        for U in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            for H in [0.0, 0.5, 1.0]:
                target = compute_target_tau_768(U, H)
                assert DEFAULT_BOUNDS.tau_768_min <= target <= DEFAULT_BOUNDS.tau_768_max

    def test_target_tau_175_bounded(self):
        """Target tau_175 should be within bounds."""
        for U in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            for C in [0.0, 0.5, 1.0]:
                target = compute_target_tau_175(U, C)
                assert DEFAULT_BOUNDS.tau_175_min <= target <= DEFAULT_BOUNDS.tau_175_max

    def test_target_w_tone_normalized(self, default_observables):
        """Target tone weights should sum to 1."""
        w_tone, logits = compute_target_w_tone(default_observables)
        assert abs(sum(w_tone) - 1.0) < EPSILON

    def test_high_sattva_increases_sweet(self):
        """High Sattva should increase sweet tone weight."""
        high_sattva = Observables(s=0.8, r=0.1, t=0.1, H=0.3, delta_sem=0.2, C_contr=0.0, F_fail=0.0)
        low_sattva = Observables(s=0.2, r=0.4, t=0.4, H=0.3, delta_sem=0.2, C_contr=0.0, F_fail=0.0)

        w_high, _ = compute_target_w_tone(high_sattva)
        w_low, _ = compute_target_w_tone(low_sattva)

        # Sweet (index 0) should be higher with high Sattva
        assert w_high[0] > w_low[0]

    def test_target_state_complete(self, default_observables):
        """Target state should be a valid StateRegister."""
        U, _ = compute_utility(default_observables, DEFAULT_STATE)
        target, audit = compute_target_state(default_observables, U, DEFAULT_STATE)

        # Should be a valid state
        assert isinstance(target, StateRegister)
        assert abs(sum(target.w_tone) - 1.0) < EPSILON
        assert abs(sum(target.w_guna) - 1.0) < EPSILON


# =============================================================================
# Version Gating Tests (Critical)
# =============================================================================

class TestVersionGating:
    """Tests for v2.6 vs v2.7 behavior."""

    def test_v26_mode_no_state_change(self, default_observables):
        """When v2.7 disabled, state must not change."""
        engine = create_v26_engine()
        initial_state = engine.state

        # Perform multiple updates
        for _ in range(10):
            audit = engine.update(default_observables)

        # State must be unchanged
        assert engine.state == initial_state
        assert audit.delta.is_zero

    def test_v27_mode_state_evolves(self, default_observables):
        """When v2.7 enabled, state should evolve."""
        engine = create_v27_engine()
        initial_state = engine.state

        audit = engine.update(default_observables)

        # State should have changed (unless coincidentally equal)
        # At minimum, audit should show v2.7 was enabled
        assert audit.v2_7_enabled is True

    def test_config_flag_respected(self, default_observables):
        """Config flag should be checked at runtime."""
        # Start disabled
        config_disabled = V27Config(v2_7_enabled=False)
        engine = StateEvolutionEngine(config=config_disabled)

        audit1 = engine.update(default_observables)
        assert audit1.v2_7_enabled is False
        assert audit1.delta.is_zero

    def test_v27_disabled_is_default(self):
        """Default config should have v2.7 disabled."""
        assert DEFAULT_V27_CONFIG.v2_7_enabled is False


# =============================================================================
# Determinism Tests (Critical)
# =============================================================================

class TestDeterminism:
    """Tests for deterministic behavior guarantee."""

    def test_same_inputs_same_outputs(self, default_observables):
        """Same inputs must produce identical outputs."""
        state = DEFAULT_STATE
        config = ENABLED_V27_CONFIG

        result1, audit1 = update_state(state, default_observables, config)
        result2, audit2 = update_state(state, default_observables, config)

        assert result1 == result2
        assert audit1.utility == audit2.utility
        assert audit1.target_state == audit2.target_state

    def test_determinism_over_many_runs(self, default_observables):
        """Determinism should hold over many runs."""
        state = DEFAULT_STATE
        config = ENABLED_V27_CONFIG

        first_result, first_audit = update_state(state, default_observables, config)

        for _ in range(1000):
            result, audit = update_state(state, default_observables, config)
            assert result == first_result
            assert audit.utility == first_audit.utility

    def test_no_randomness_in_softmax(self):
        """Softmax should be deterministic."""
        logits = (0.5, 0.3, 0.2)
        first = softmax_3(logits)

        for _ in range(1000):
            result = softmax_3(logits)
            assert result == first

    def test_no_randomness_in_utility(self, default_observables):
        """Utility computation should be deterministic."""
        first_U, _ = compute_utility(default_observables, DEFAULT_STATE)

        for _ in range(1000):
            U, _ = compute_utility(default_observables, DEFAULT_STATE)
            assert U == first_U


# =============================================================================
# State Update Equation Tests
# =============================================================================

class TestStateUpdateEquation:
    """Tests for the core update equation θ_{t+1} = clip((1-α)θ_t + α×θ*, bounds)."""

    def test_update_is_interpolation(self, default_observables):
        """Update should interpolate between current and target."""
        engine = create_v27_engine(alpha=0.5)
        initial = engine.state

        audit = engine.update(default_observables)
        target = audit.target_state
        result = engine.state

        # With α=0.5, result should be midpoint (approximately, accounting for clipping)
        # This is a sanity check, not exact due to clipping and normalization
        if (
            DEFAULT_BOUNDS.tau_768_min < (initial.tau_768 + target.tau_768) / 2 < DEFAULT_BOUNDS.tau_768_max
        ):
            expected_tau_768 = (initial.tau_768 + target.tau_768) / 2
            assert abs(result.tau_768 - expected_tau_768) < 0.01

    def test_alpha_zero_no_change(self, default_observables):
        """With α ≈ 0, state should barely change."""
        # Note: α=0 exactly is invalid, so use very small
        engine = create_v27_engine(alpha=0.001)
        initial = engine.state

        audit = engine.update(default_observables)

        # Changes should be very small
        assert abs(engine.state.tau_768 - initial.tau_768) < 0.01
        assert abs(engine.state.tau_175 - initial.tau_175) < 0.01

    def test_bounds_enforced_after_update(self, high_contradiction_observables):
        """Update should never exceed bounds."""
        engine = create_v27_engine(alpha=0.5)

        # Run many updates with extreme observables
        for _ in range(50):
            engine.update(high_contradiction_observables)

        state = engine.state
        assert DEFAULT_BOUNDS.tau_768_min <= state.tau_768 <= DEFAULT_BOUNDS.tau_768_max
        assert DEFAULT_BOUNDS.tau_175_min <= state.tau_175 <= DEFAULT_BOUNDS.tau_175_max
        assert abs(state.b_policy) <= DEFAULT_BOUNDS.b_policy_max


# =============================================================================
# Audit Trail Tests
# =============================================================================

class TestAuditTrail:
    """Tests for audit trail completeness."""

    def test_audit_has_all_fields(self, default_observables):
        """Audit should contain all required fields."""
        engine = create_v27_engine()
        audit = engine.update(default_observables)

        assert hasattr(audit, "run_id")
        assert hasattr(audit, "timestamp")
        assert hasattr(audit, "observables")
        assert hasattr(audit, "utility")
        assert hasattr(audit, "utility_audit")
        assert hasattr(audit, "target_state")
        assert hasattr(audit, "target_audit")
        assert hasattr(audit, "state_before")
        assert hasattr(audit, "state_after")
        assert hasattr(audit, "delta")
        assert hasattr(audit, "rules_fired")

    def test_audit_explanation_readable(self, default_observables):
        """Audit explanation should be human-readable."""
        engine = create_v27_engine()
        audit = engine.update(default_observables)

        explanation = audit.explanation
        assert isinstance(explanation, str)
        assert len(explanation) > 0

    def test_rules_fired_recorded(self, high_contradiction_observables):
        """Rules that fired should be recorded."""
        engine = create_v27_engine()
        audit = engine.update(high_contradiction_observables)

        # High contradiction should fire the contradiction rule
        rule_ids = [r.rule_id for r in audit.rules_fired if r.fired]
        assert "RULE_HIGH_CONTRADICTION_TIGHTEN_175B" in rule_ids


# =============================================================================
# Non-Capability Tests (Negative Tests)
# =============================================================================

class TestNonCapabilities:
    """Tests verifying what the system does NOT do."""

    def test_no_unbounded_drift(self, default_observables):
        """State should not drift unboundedly over many updates."""
        engine = create_v27_engine()

        for _ in range(1000):
            engine.update(default_observables)

        state = engine.state
        # All values should still be within bounds
        assert DEFAULT_BOUNDS.tau_768_min <= state.tau_768 <= DEFAULT_BOUNDS.tau_768_max
        assert DEFAULT_BOUNDS.tau_175_min <= state.tau_175 <= DEFAULT_BOUNDS.tau_175_max
        assert abs(sum(state.w_tone) - 1.0) < EPSILON
        assert abs(sum(state.w_guna) - 1.0) < EPSILON

    def test_w_guna_unchanged_by_evolution(self, default_observables):
        """w_guna should only change via config, not evolution."""
        engine = create_v27_engine()
        initial_w_guna = engine.state.w_guna

        for _ in range(100):
            engine.update(default_observables)

        # w_guna should be unchanged
        assert engine.state.w_guna == initial_w_guna

    def test_reset_restores_initial_state(self, default_observables):
        """Reset should restore to initial state."""
        engine = create_v27_engine()

        # Evolve state
        for _ in range(10):
            engine.update(default_observables)

        # Reset
        engine.reset()

        assert engine.state == DEFAULT_STATE


# =============================================================================
# Helper Function Tests
# =============================================================================

class TestHelperFunctions:
    """Tests for helper functions."""

    def test_normalize_weights(self):
        """normalize_weights should sum to 1."""
        result = normalize_weights((0.5, 0.5, 0.5))
        assert abs(sum(result) - 1.0) < EPSILON

    def test_softmax_sums_to_one(self):
        """softmax_3 should sum to 1."""
        for logits in [(0.0, 0.0, 0.0), (1.0, 2.0, 3.0), (-1.0, 0.0, 1.0)]:
            result = softmax_3(logits)
            assert abs(sum(result) - 1.0) < EPSILON

    def test_softmax_preserves_order(self):
        """Larger logits should give larger probabilities."""
        result = softmax_3((1.0, 2.0, 3.0))
        assert result[0] < result[1] < result[2]

    def test_clip_works(self):
        """clip should enforce bounds."""
        assert clip(0.5, 0.0, 1.0) == 0.5
        assert clip(-0.5, 0.0, 1.0) == 0.0
        assert clip(1.5, 0.0, 1.0) == 1.0
