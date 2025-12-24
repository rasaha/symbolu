"""
Guna Entropy Modulation - Comprehensive Test Suite
===================================================

Symbol-U v2.6 - Deterministic, Zero-Parameter, Non-Learning System

This test suite verifies:
    1. Determinism: Same inputs → same outputs
    2. Disable Proof: w_S=w_R=w_T=1, P=T=1 → E=1, output unchanged
    3. Formula Correctness: All formulas match specification
    4. Audit Trace: Complete traceability
    5. Tier Behavior: Correct tier scalar application

Version: 2.6.0
Date: 2025-12-22
"""

import pytest
import math

from symbolu.guna_modulation import (
    # Constants
    H_MID,
    EPSILON,
    # Types
    ModulationTier,
    GunaVector,
    PipelineInputs,
    GunaWeights,
    PolicyConfig,
    TierModulationConfig,
    ModulationResult,
    # Derivation functions
    compute_sattva_raw,
    compute_rajas_raw,
    compute_tamas_raw,
    normalize_guna_components,
    derive_guna_vector,
    derive_guna_from_values,
    # Computation functions
    compute_guna_coefficient,
    compute_policy_scalar,
    compute_entropy_modulation_factor,
    compute_output_intensity,
    # Engine
    EntropyModulationEngine,
    create_engine_for_tier,
    modulate_intensity,
    # Configs
    TIER_1_MODULATION_CONFIG,
    TIER_2_MODULATION_CONFIG,
    TIER_3_MODULATION_CONFIG,
    NEUTRAL_GUNA_WEIGHTS,
    DEFAULT_GUNA_WEIGHTS,
    create_disabled_config,
)


# =============================================================================
# Constants Tests
# =============================================================================

class TestConstants:
    """Test module constants."""

    def test_h_mid_value(self):
        """H_mid must be 0.5."""
        assert H_MID == 0.5

    def test_epsilon_value(self):
        """Epsilon must be 10^-9."""
        assert EPSILON == 1e-9


# =============================================================================
# Raw Guna Component Tests
# =============================================================================

class TestRawGunaComponents:
    """Test raw Guna component computation."""

    def test_sattva_raw_formula(self):
        """S_raw = C_s * (1 - H)"""
        # High coherence, low entropy → high Sattva
        assert compute_sattva_raw(C_s=1.0, H=0.0) == 1.0
        # Low coherence → low Sattva
        assert compute_sattva_raw(C_s=0.0, H=0.0) == 0.0
        # High entropy → low Sattva
        assert compute_sattva_raw(C_s=1.0, H=1.0) == 0.0
        # Middle values
        assert compute_sattva_raw(C_s=0.5, H=0.5) == 0.25

    def test_rajas_raw_formula(self):
        """R_raw = M * (1 - |H - H_mid|)"""
        # High motion at midpoint entropy → maximum Rajas
        assert compute_rajas_raw(M=1.0, H=0.5) == 1.0
        # No motion → no Rajas
        assert compute_rajas_raw(M=0.0, H=0.5) == 0.0
        # Extreme entropy → reduced Rajas
        assert compute_rajas_raw(M=1.0, H=0.0) == 0.5
        assert compute_rajas_raw(M=1.0, H=1.0) == 0.5

    def test_tamas_raw_formula(self):
        """T_raw = H * (1 - C_s)"""
        # High entropy, low coherence → high Tamas
        assert compute_tamas_raw(H=1.0, C_s=0.0) == 1.0
        # Low entropy → low Tamas
        assert compute_tamas_raw(H=0.0, C_s=0.0) == 0.0
        # High coherence → low Tamas
        assert compute_tamas_raw(H=1.0, C_s=1.0) == 0.0
        # Middle values
        assert compute_tamas_raw(H=0.5, C_s=0.5) == 0.25


# =============================================================================
# Normalization Tests
# =============================================================================

class TestNormalization:
    """Test Guna component normalization."""

    def test_normalized_sum_equals_one(self):
        """S + R + T must equal 1.0 after normalization."""
        S, R, T, Z = normalize_guna_components(0.3, 0.5, 0.2)
        # Use 1e-8 tolerance due to epsilon in normalization formula
        assert abs((S + R + T) - 1.0) < 1e-8

    def test_normalization_with_zeros(self):
        """Normalization handles all-zero case via epsilon."""
        S, R, T, Z = normalize_guna_components(0.0, 0.0, 0.0)
        # All components should be near zero (only epsilon in denominator)
        assert S < 0.1
        assert R < 0.1
        assert T < 0.1
        # Z should be epsilon
        assert Z == EPSILON

    def test_normalization_preserves_ratios(self):
        """Normalization preserves relative ratios."""
        S, R, T, Z = normalize_guna_components(0.6, 0.3, 0.1)
        # S should be roughly twice R
        assert abs(S / R - 2.0) < 0.01
        # R should be roughly three times T
        assert abs(R / T - 3.0) < 0.01


# =============================================================================
# Guna Vector Derivation Tests
# =============================================================================

class TestGunaVectorDerivation:
    """Test Guna vector derivation."""

    def test_derive_guna_vector_determinism(self):
        """Same inputs produce same outputs (determinism proof)."""
        inputs = PipelineInputs(C_s=0.7, M=0.5, H=0.3)

        result1, trace1 = derive_guna_vector(inputs)
        result2, trace2 = derive_guna_vector(inputs)

        assert result1.sattva == result2.sattva
        assert result1.rajas == result2.rajas
        assert result1.tamas == result2.tamas

    def test_derive_guna_vector_sum_constraint(self):
        """Guna vector components must sum to 1.0."""
        inputs = PipelineInputs(C_s=0.7, M=0.5, H=0.3)
        guna_vector, _ = derive_guna_vector(inputs)

        # Use 1e-8 tolerance due to epsilon in normalization formula
        assert abs(guna_vector.sum - 1.0) < 1e-8

    def test_derive_guna_vector_generates_trace(self):
        """Derivation generates complete audit trace."""
        inputs = PipelineInputs(C_s=0.7, M=0.5, H=0.3)
        guna_vector, trace = derive_guna_vector(inputs)

        # Should have trace entries for: S_raw, R_raw, T_raw, normalization, guna_vector
        assert len(trace) == 5

        # Check step names
        step_names = [entry.step_name for entry in trace]
        assert "sattva_raw" in step_names
        assert "rajas_raw" in step_names
        assert "tamas_raw" in step_names
        assert "normalization" in step_names
        assert "guna_vector" in step_names

    def test_derive_guna_from_values_convenience(self):
        """Convenience function produces same result."""
        guna1 = derive_guna_from_values(C_s=0.7, M=0.5, H=0.3)

        inputs = PipelineInputs(C_s=0.7, M=0.5, H=0.3)
        guna2, _ = derive_guna_vector(inputs)

        assert guna1.sattva == guna2.sattva
        assert guna1.rajas == guna2.rajas
        assert guna1.tamas == guna2.tamas


# =============================================================================
# Guna Coefficient Tests
# =============================================================================

class TestGunaCoefficient:
    """Test Guna coefficient computation."""

    def test_guna_coefficient_formula(self):
        """G = w_S * S + w_R * R + w_T * T"""
        guna_vector = GunaVector(sattva=0.4, rajas=0.35, tamas=0.25)
        weights = GunaWeights(w_S=0.9, w_R=1.05, w_T=0.6)

        G, trace = compute_guna_coefficient(guna_vector, weights)

        expected = 0.9 * 0.4 + 1.05 * 0.35 + 0.6 * 0.25
        assert abs(G - expected) < 1e-9

    def test_neutral_weights_preserve_unity(self):
        """With neutral weights (all 1.0), G = S + R + T = 1.0."""
        # Create normalized vector (sum = 1.0)
        guna_vector = GunaVector(sattva=0.4, rajas=0.35, tamas=0.25)
        weights = NEUTRAL_GUNA_WEIGHTS

        G, _ = compute_guna_coefficient(guna_vector, weights)

        # With all weights = 1.0, G = S + R + T = 1.0 (normalized)
        assert abs(G - 1.0) < 1e-9


# =============================================================================
# Policy Scalar Tests
# =============================================================================

class TestPolicyScalar:
    """Test Policy scalar computation."""

    def test_policy_scalar_formula(self):
        """P = clamp(1 - r_risk - r_escalation, 0, 1)"""
        policy = PolicyConfig(r_risk=0.2, r_escalation=0.1)
        P, trace = compute_policy_scalar(policy)

        expected = 1.0 - 0.2 - 0.1  # = 0.7
        assert abs(P - expected) < 1e-9

    def test_policy_scalar_clamp_lower(self):
        """P is clamped to 0 when negative."""
        policy = PolicyConfig(r_risk=0.6, r_escalation=0.6)  # Sum > 1
        P, _ = compute_policy_scalar(policy)

        assert P == 0.0

    def test_policy_scalar_zero_risk(self):
        """With zero risk/escalation, P = 1.0."""
        policy = PolicyConfig(r_risk=0.0, r_escalation=0.0)
        P, _ = compute_policy_scalar(policy)

        assert P == 1.0


# =============================================================================
# Entropy Modulation Factor Tests
# =============================================================================

class TestEntropyModulationFactor:
    """Test Entropy Modulation Factor computation."""

    def test_entropy_modulation_factor_formula(self):
        """E = G * P * T"""
        G, P, T = 0.8, 0.9, 1.0
        E, trace = compute_entropy_modulation_factor(G, P, T)

        expected = 0.8 * 0.9 * 1.0
        assert abs(E - expected) < 1e-9

    def test_entropy_modulation_factor_trace(self):
        """Trace includes all inputs."""
        G, P, T = 0.8, 0.9, 1.0
        E, trace = compute_entropy_modulation_factor(G, P, T)

        assert trace.step_name == "entropy_modulation_factor"
        assert trace.formula == "E = G * P * T"


# =============================================================================
# Output Intensity Tests
# =============================================================================

class TestOutputIntensity:
    """Test Output Intensity computation."""

    def test_output_intensity_formula(self):
        """OUTPUT_intensity = BASE_intensity * E"""
        base = 0.8
        E = 0.9
        output, trace = compute_output_intensity(base, E)

        expected = 0.8 * 0.9
        assert abs(output - expected) < 1e-9

    def test_output_unchanged_when_e_is_one(self):
        """When E = 1.0, output equals input."""
        base = 0.75
        E = 1.0
        output, _ = compute_output_intensity(base, E)

        assert output == base


# =============================================================================
# Engine Tests
# =============================================================================

class TestEntropyModulationEngine:
    """Test the main Entropy Modulation Engine."""

    def test_engine_initialization(self):
        """Engine initializes with configuration."""
        engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)

        assert engine.tier == ModulationTier.ENTERPRISE_TIER_1
        assert engine.config == TIER_1_MODULATION_CONFIG

    def test_modulate_returns_result(self):
        """Engine modulate method returns ModulationResult."""
        engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)

        result = engine.modulate(
            base_intensity=0.8,
            C_s=0.7,
            M=0.5,
            H=0.3,
        )

        assert isinstance(result, ModulationResult)
        assert result.base_intensity == 0.8
        assert result.output_intensity > 0
        assert len(result.trace) > 0

    def test_modulate_determinism(self):
        """Same inputs produce same outputs (determinism proof)."""
        engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)

        result1 = engine.modulate(base_intensity=0.8, C_s=0.7, M=0.5, H=0.3)
        result2 = engine.modulate(base_intensity=0.8, C_s=0.7, M=0.5, H=0.3)

        assert result1.guna_vector.sattva == result2.guna_vector.sattva
        assert result1.guna_vector.rajas == result2.guna_vector.rajas
        assert result1.guna_vector.tamas == result2.guna_vector.tamas
        assert result1.G == result2.G
        assert result1.P == result2.P
        assert result1.T == result2.T
        assert result1.E == result2.E
        assert result1.output_intensity == result2.output_intensity

    def test_tier_scalar_application(self):
        """Different tiers apply different scalars."""
        engine_t1 = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)
        engine_t2 = EntropyModulationEngine(TIER_2_MODULATION_CONFIG)
        engine_t3 = EntropyModulationEngine(TIER_3_MODULATION_CONFIG)

        result_t1 = engine_t1.modulate(base_intensity=1.0, C_s=0.7, M=0.5, H=0.3)
        result_t2 = engine_t2.modulate(base_intensity=1.0, C_s=0.7, M=0.5, H=0.3)
        result_t3 = engine_t3.modulate(base_intensity=1.0, C_s=0.7, M=0.5, H=0.3)

        # Tier 1: T = 1.0
        assert result_t1.T == 1.0
        # Tier 2: T = 0.9
        assert result_t2.T == 0.9
        # Tier 3 (Consumer): T = 0.85
        assert result_t3.T == 0.85

        # Output intensity should scale accordingly
        # (Guna and Policy components are same, only T differs)
        assert result_t1.output_intensity > result_t2.output_intensity
        assert result_t2.output_intensity > result_t3.output_intensity


# =============================================================================
# Disable Proof Tests
# =============================================================================

class TestDisableProof:
    """
    Test the disable proof requirement.

    If w_S = w_R = w_T = 1 and P = T = 1, then E = 1
    and OUTPUT_intensity = BASE_intensity (unchanged).
    """

    def test_disable_with_neutral_weights(self):
        """With neutral weights, G = 1.0 for normalized vector."""
        config = create_disabled_config(ModulationTier.ENTERPRISE_TIER_1)
        engine = EntropyModulationEngine(config)

        result = engine.modulate(
            base_intensity=0.8,
            C_s=0.7,
            M=0.5,
            H=0.3,
        )

        # With neutral weights, G should be ~1.0 (1e-8 tolerance due to epsilon)
        assert abs(result.G - 1.0) < 1e-8
        # P should be 1.0
        assert result.P == 1.0
        # T should be 1.0 (overridden in disabled config)
        assert result.T == 1.0
        # E = G * P * T = ~1.0
        assert abs(result.E - 1.0) < 1e-8
        # Output should equal input (within tolerance)
        assert abs(result.output_intensity - result.base_intensity) < 1e-7

    def test_is_unchanged_property(self):
        """Result.is_unchanged is True when modulation disabled."""
        config = create_disabled_config(ModulationTier.ENTERPRISE_TIER_1)
        engine = EntropyModulationEngine(config)

        result = engine.modulate(
            base_intensity=0.8,
            C_s=0.7,
            M=0.5,
            H=0.3,
        )

        assert result.is_unchanged is True
        assert result.is_disabled is True


# =============================================================================
# Audit Trace Tests
# =============================================================================

class TestAuditTrace:
    """Test audit trace completeness."""

    def test_trace_includes_all_steps(self):
        """Audit trace includes all computation steps."""
        engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)

        result = engine.modulate(
            base_intensity=0.8,
            C_s=0.7,
            M=0.5,
            H=0.3,
        )

        step_names = [entry.step_name for entry in result.trace]

        # Guna derivation steps
        assert "sattva_raw" in step_names
        assert "rajas_raw" in step_names
        assert "tamas_raw" in step_names
        assert "normalization" in step_names
        assert "guna_vector" in step_names

        # Modulation steps
        assert "guna_coefficient" in step_names
        assert "policy_scalar" in step_names
        assert "tier_scalar" in step_names
        assert "entropy_modulation_factor" in step_names
        assert "output_intensity" in step_names

    def test_trace_audit_example(self):
        """
        Audit trace example showing complete computation.

        Inputs: C_s=0.7, M=0.5, H=0.3
        """
        engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)

        result = engine.modulate(
            base_intensity=0.8,
            C_s=0.7,
            M=0.5,
            H=0.3,
        )

        # Print audit trace (for documentation)
        print("\n=== AUDIT TRACE EXAMPLE ===")
        print(f"Inputs: C_s=0.7, M=0.5, H=0.3")
        print(f"Base Intensity: 0.8")
        print()

        for entry in result.trace:
            print(f"Step: {entry.step_name}")
            print(f"  Formula: {entry.formula}")
            print(f"  Inputs: {dict(entry.inputs)}")
            print(f"  Output: {entry.output}")
            print()

        print(f"Final Results:")
        print(f"  Guna Vector: S={result.guna_vector.sattva:.4f}, "
              f"R={result.guna_vector.rajas:.4f}, T={result.guna_vector.tamas:.4f}")
        print(f"  G (Guna Coefficient): {result.G:.4f}")
        print(f"  P (Policy Scalar): {result.P:.4f}")
        print(f"  T (Tier Scalar): {result.T:.4f}")
        print(f"  E (Modulation Factor): {result.E:.4f}")
        print(f"  Output Intensity: {result.output_intensity:.4f}")
        print("=== END AUDIT TRACE ===\n")


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunctions:
    """Test factory functions."""

    def test_create_engine_for_tier(self):
        """Factory creates engine for tier."""
        engine = create_engine_for_tier(ModulationTier.ENTERPRISE_TIER_1)

        assert engine.tier == ModulationTier.ENTERPRISE_TIER_1

    def test_modulate_intensity_standalone(self):
        """Standalone function works correctly."""
        result = modulate_intensity(
            base_intensity=0.8,
            C_s=0.7,
            M=0.5,
            H=0.3,
        )

        assert isinstance(result, ModulationResult)
        assert result.base_intensity == 0.8
        assert result.output_intensity > 0


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_all_zeros_input(self):
        """Handle all-zero inputs gracefully."""
        result = modulate_intensity(
            base_intensity=0.5,
            C_s=0.0,
            M=0.0,
            H=0.0,
        )

        # Should not crash, output should be positive
        assert result.output_intensity >= 0

    def test_all_ones_input(self):
        """Handle all-one inputs gracefully."""
        result = modulate_intensity(
            base_intensity=1.0,
            C_s=1.0,
            M=1.0,
            H=1.0,
        )

        assert result.output_intensity >= 0

    def test_clamping_negative_values(self):
        """Negative values are clamped to 0."""
        inputs = PipelineInputs(C_s=-0.5, M=-0.5, H=-0.5)

        # Values should be clamped
        assert inputs.C_s == 0.0
        assert inputs.M == 0.0
        assert inputs.H == 0.0

    def test_clamping_values_above_one(self):
        """Values > 1.0 are clamped to 1.0."""
        inputs = PipelineInputs(C_s=1.5, M=1.5, H=1.5)

        # Values should be clamped
        assert inputs.C_s == 1.0
        assert inputs.M == 1.0
        assert inputs.H == 1.0


# =============================================================================
# Serialization Tests
# =============================================================================

class TestSerialization:
    """Test serialization methods."""

    def test_guna_vector_to_dict(self):
        """GunaVector serializes to dict."""
        guna = GunaVector(sattva=0.4, rajas=0.35, tamas=0.25)
        d = guna.to_dict()

        assert d == {"sattva": 0.4, "rajas": 0.35, "tamas": 0.25}

    def test_result_to_dict(self):
        """ModulationResult serializes to dict."""
        result = modulate_intensity(
            base_intensity=0.8,
            C_s=0.7,
            M=0.5,
            H=0.3,
        )

        d = result.to_dict()

        assert "guna_vector" in d
        assert "G" in d
        assert "P" in d
        assert "T" in d
        assert "E" in d
        assert "base_intensity" in d
        assert "output_intensity" in d
        assert "trace" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
