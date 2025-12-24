"""
Guna Entropy Modulation - Specification Verification Tests
===========================================================

Symbol-U v2.6 - Deterministic, Zero-Parameter, Non-Learning System

This test module provides explicit verification that the implementation
matches the formal specification exactly.

Each test uses hand-calculated expected values from the specification formulas.

Version: 2.6.0
Date: 2025-12-22
"""

import pytest
import math

from symbolu.guna_modulation import (
    H_MID,
    EPSILON,
    ModulationTier,
    GunaVector,
    PipelineInputs,
    GunaWeights,
    PolicyConfig,
    EntropyModulationEngine,
    TIER_1_MODULATION_CONFIG,
    TIER_2_MODULATION_CONFIG,
    TIER_3_MODULATION_CONFIG,
    compute_sattva_raw,
    compute_rajas_raw,
    compute_tamas_raw,
    normalize_guna_components,
    derive_guna_from_values,
    compute_guna_coefficient,
    compute_policy_scalar,
    compute_entropy_modulation_factor,
    compute_output_intensity,
    create_custom_config,
    modulate_intensity,
)


# =============================================================================
# Specification Formula Verification
# =============================================================================

class TestSpecificationFormulas:
    """
    Verify each formula matches the specification exactly.

    Reference: SPEC.md Section 5-9
    """

    def test_sattva_raw_specification(self):
        """
        SPEC Formula: S_raw = C_s × (1 - H)

        Test cases from specification:
        - C_s=1.0, H=0.0 → S_raw = 1.0 × 1.0 = 1.0
        - C_s=0.7, H=0.3 → S_raw = 0.7 × 0.7 = 0.49
        - C_s=0.5, H=0.5 → S_raw = 0.5 × 0.5 = 0.25
        """
        # Test case 1
        assert compute_sattva_raw(1.0, 0.0) == 1.0

        # Test case 2
        expected = 0.7 * (1 - 0.3)
        assert abs(compute_sattva_raw(0.7, 0.3) - expected) < 1e-10

        # Test case 3
        expected = 0.5 * (1 - 0.5)
        assert abs(compute_sattva_raw(0.5, 0.5) - expected) < 1e-10

    def test_rajas_raw_specification(self):
        """
        SPEC Formula: R_raw = M × (1 - |H - H_mid|)

        Where H_mid = 0.5

        Test cases:
        - M=1.0, H=0.5 → R_raw = 1.0 × (1 - 0) = 1.0
        - M=0.5, H=0.3 → R_raw = 0.5 × (1 - 0.2) = 0.4
        - M=1.0, H=0.0 → R_raw = 1.0 × (1 - 0.5) = 0.5
        """
        # At midpoint entropy, Rajas is maximum
        assert compute_rajas_raw(1.0, 0.5) == 1.0

        # Test case with H=0.3
        expected = 0.5 * (1 - abs(0.3 - 0.5))
        assert abs(compute_rajas_raw(0.5, 0.3) - expected) < 1e-10

        # At extreme entropy
        expected = 1.0 * (1 - abs(0.0 - 0.5))
        assert abs(compute_rajas_raw(1.0, 0.0) - expected) < 1e-10

    def test_tamas_raw_specification(self):
        """
        SPEC Formula: T_raw = H × (1 - C_s)

        Test cases:
        - H=1.0, C_s=0.0 → T_raw = 1.0 × 1.0 = 1.0
        - H=0.3, C_s=0.7 → T_raw = 0.3 × 0.3 = 0.09
        - H=0.5, C_s=0.5 → T_raw = 0.5 × 0.5 = 0.25
        """
        # Maximum Tamas
        assert compute_tamas_raw(1.0, 0.0) == 1.0

        # Test case with H=0.3, C_s=0.7
        expected = 0.3 * (1 - 0.7)
        assert abs(compute_tamas_raw(0.3, 0.7) - expected) < 1e-10

        # Middle values
        expected = 0.5 * (1 - 0.5)
        assert abs(compute_tamas_raw(0.5, 0.5) - expected) < 1e-10

    def test_normalization_specification(self):
        """
        SPEC Formula:
            Z = S_raw + R_raw + T_raw + ε
            S = S_raw / Z
            R = R_raw / Z
            T = T_raw / Z

        Constraint: S + R + T = 1
        """
        S_raw, R_raw, T_raw = 0.49, 0.40, 0.09

        S, R, T, Z = normalize_guna_components(S_raw, R_raw, T_raw)

        # Verify Z formula
        expected_Z = S_raw + R_raw + T_raw + EPSILON
        assert abs(Z - expected_Z) < 1e-15

        # Verify normalization
        assert abs(S - S_raw / Z) < 1e-15
        assert abs(R - R_raw / Z) < 1e-15
        assert abs(T - T_raw / Z) < 1e-15

        # Verify constraint
        assert abs((S + R + T) - 1.0) < 1e-8

    def test_guna_coefficient_specification(self):
        """
        SPEC Formula: G = w_S × S + w_R × R + w_T × T

        With default weights: w_S=0.9, w_R=1.05, w_T=0.6
        """
        guna = GunaVector(sattva=0.5, rajas=0.4, tamas=0.1)
        weights = GunaWeights(w_S=0.9, w_R=1.05, w_T=0.6)

        G, _ = compute_guna_coefficient(guna, weights)

        expected = 0.9 * 0.5 + 1.05 * 0.4 + 0.6 * 0.1
        assert abs(G - expected) < 1e-10

    def test_policy_scalar_specification(self):
        """
        SPEC Formula: P = clamp(1 - r_risk - r_escalation, 0, 1)

        Test cases:
        - r_risk=0, r_escalation=0 → P = 1.0
        - r_risk=0.2, r_escalation=0.1 → P = 0.7
        - r_risk=0.8, r_escalation=0.5 → P = 0 (clamped)
        """
        # No risk
        policy = PolicyConfig(r_risk=0, r_escalation=0)
        P, _ = compute_policy_scalar(policy)
        assert P == 1.0

        # Moderate risk
        policy = PolicyConfig(r_risk=0.2, r_escalation=0.1)
        P, _ = compute_policy_scalar(policy)
        assert abs(P - 0.7) < 1e-10

        # High risk (clamped)
        policy = PolicyConfig(r_risk=0.8, r_escalation=0.5)
        P, _ = compute_policy_scalar(policy)
        assert P == 0.0

    def test_tier_scalars_specification(self):
        """
        SPEC Fixed Constants:
            - Enterprise Tier 1: T = 1.0
            - Enterprise Tier 2: T = 0.9
            - Consumer Tier: T = 0.85
        """
        assert TIER_1_MODULATION_CONFIG.tier_scalar == 1.0
        assert TIER_2_MODULATION_CONFIG.tier_scalar == 0.9
        assert TIER_3_MODULATION_CONFIG.tier_scalar == 0.85

    def test_entropy_modulation_factor_specification(self):
        """
        SPEC Formula: E = G × P × T
        """
        G, P, T = 0.93, 1.0, 1.0
        E, _ = compute_entropy_modulation_factor(G, P, T)

        expected = G * P * T
        assert abs(E - expected) < 1e-10

    def test_output_intensity_specification(self):
        """
        SPEC Formula: OUTPUT_intensity = BASE_intensity × E
        """
        base = 0.8
        E = 0.93

        output, _ = compute_output_intensity(base, E)

        expected = base * E
        assert abs(output - expected) < 1e-10


# =============================================================================
# End-to-End Audit Trail Verification
# =============================================================================

class TestAuditTrailVerification:
    """
    Verify the complete audit trail matches the specification example.

    Reference: SPEC.md Section 11.3
    """

    def test_complete_audit_example(self):
        """
        SPEC Audit Trace Example:

        Inputs: C_s=0.7, M=0.5, H=0.3, BASE_intensity=0.8

        Step 1: S_raw = 0.49, R_raw = 0.40, T_raw = 0.09
        Step 2: Z ≈ 0.98, S ≈ 0.500, R ≈ 0.408, T ≈ 0.092
        Step 3: G = 0.933 (with default weights)
        Step 4: P = 1.0
        Step 5: T = 1.0
        Step 6: E = 0.933
        Step 7: OUTPUT = 0.746
        """
        engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)

        result = engine.modulate(
            base_intensity=0.8,
            C_s=0.7,
            M=0.5,
            H=0.3,
        )

        # Verify Step 1: Raw components
        S_raw = result.trace[0].output
        R_raw = result.trace[1].output
        T_raw = result.trace[2].output

        assert abs(S_raw - 0.49) < 0.01
        assert abs(R_raw - 0.40) < 0.01
        assert abs(T_raw - 0.09) < 0.01

        # Verify Step 2: Normalization
        assert abs(result.guna_vector.sattva - 0.500) < 0.01
        assert abs(result.guna_vector.rajas - 0.408) < 0.01
        assert abs(result.guna_vector.tamas - 0.092) < 0.01

        # Verify Step 3: Guna coefficient
        assert abs(result.G - 0.933) < 0.01

        # Verify Step 4: Policy scalar
        assert result.P == 1.0

        # Verify Step 5: Tier scalar
        assert result.T == 1.0

        # Verify Step 6: Entropy modulation factor
        assert abs(result.E - 0.933) < 0.01

        # Verify Step 7: Output intensity
        assert abs(result.output_intensity - 0.746) < 0.01


# =============================================================================
# Determinism Verification
# =============================================================================

class TestDeterminismVerification:
    """
    SPEC Requirement: Same inputs → same outputs

    Reference: SPEC.md Section 11.1
    """

    def test_determinism_multiple_calls(self):
        """Verify identical results across multiple calls."""
        engine = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)

        # Run 10 times with same inputs
        results = []
        for _ in range(10):
            result = engine.modulate(
                base_intensity=0.8,
                C_s=0.7,
                M=0.5,
                H=0.3,
            )
            results.append(result)

        # All results must be identical
        first = results[0]
        for r in results[1:]:
            assert r.guna_vector.sattva == first.guna_vector.sattva
            assert r.guna_vector.rajas == first.guna_vector.rajas
            assert r.guna_vector.tamas == first.guna_vector.tamas
            assert r.G == first.G
            assert r.P == first.P
            assert r.T == first.T
            assert r.E == first.E
            assert r.output_intensity == first.output_intensity

    def test_determinism_different_engines(self):
        """Verify same config produces same results across engines."""
        engine1 = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)
        engine2 = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)

        result1 = engine1.modulate(base_intensity=0.5, C_s=0.6, M=0.4, H=0.2)
        result2 = engine2.modulate(base_intensity=0.5, C_s=0.6, M=0.4, H=0.2)

        assert result1.output_intensity == result2.output_intensity
        assert result1.E == result2.E


# =============================================================================
# Disable Proof Verification
# =============================================================================

class TestDisableProofVerification:
    """
    SPEC Requirement: If w_S=w_R=w_T=1 and P=T=1, output unchanged.

    Reference: SPEC.md Section 11.2
    """

    def test_disable_proof_mathematical(self):
        """
        Mathematical proof verification:

        1. With neutral weights: G = 1×S + 1×R + 1×T = S+R+T = 1
        2. With zero risk: P = clamp(1-0-0, 0, 1) = 1
        3. With T override: T = 1
        4. Therefore: E = 1 × 1 × 1 = 1
        5. Therefore: OUTPUT = BASE × 1 = BASE
        """
        # Create disabled config
        config = create_custom_config(
            tier=ModulationTier.ENTERPRISE_TIER_1,
            w_S=1.0,
            w_R=1.0,
            w_T=1.0,
            r_risk=0.0,
            r_escalation=0.0,
            tier_scalar_override=1.0,
        )

        engine = EntropyModulationEngine(config)

        # Test with various inputs (excluding all-zeros which is a degenerate case)
        test_cases = [
            (0.8, 0.7, 0.5, 0.3),
            (1.0, 0.5, 0.5, 0.5),  # Balanced inputs
            (0.5, 1.0, 1.0, 1.0),
            (0.333, 0.5, 0.5, 0.5),
        ]

        for base, c_s, m, h in test_cases:
            result = engine.modulate(
                base_intensity=base,
                C_s=c_s,
                M=m,
                H=h,
            )

            # G should be ~1.0 (sum of normalized vector)
            assert abs(result.G - 1.0) < 1e-8, f"G={result.G} for inputs ({c_s}, {m}, {h})"

            # E should be ~1.0
            assert abs(result.E - 1.0) < 1e-8, f"E={result.E}"

            # Output should equal input
            assert abs(result.output_intensity - base) < 1e-7, \
                f"Output={result.output_intensity}, Base={base}"


# =============================================================================
# Boundary Condition Tests
# =============================================================================

class TestBoundaryConditions:
    """Test behavior at boundary values."""

    def test_extreme_sattva_dominance(self):
        """
        When C_s=1.0, H=0.0, M=0.0:
        - S_raw = 1.0 × 1.0 = 1.0
        - R_raw = 0.0 × anything = 0.0
        - T_raw = 0.0 × anything = 0.0
        - Therefore S ≈ 1.0, R ≈ 0.0, T ≈ 0.0
        """
        guna = derive_guna_from_values(C_s=1.0, M=0.0, H=0.0)

        assert guna.sattva > 0.99
        assert guna.rajas < 0.01
        assert guna.tamas < 0.01

    def test_extreme_rajas_dominance(self):
        """
        When C_s=0.0, H=0.5, M=1.0:
        - S_raw = 0.0
        - R_raw = 1.0 × (1 - 0) = 1.0 (maximum)
        - T_raw = 0.5 × 1.0 = 0.5
        """
        guna = derive_guna_from_values(C_s=0.0, M=1.0, H=0.5)

        # Rajas should dominate
        assert guna.rajas > guna.sattva
        assert guna.rajas > guna.tamas

    def test_extreme_tamas_dominance(self):
        """
        When C_s=0.0, H=1.0, M=0.0:
        - S_raw = 0.0
        - R_raw = 0.0
        - T_raw = 1.0 × 1.0 = 1.0
        - Therefore T ≈ 1.0
        """
        guna = derive_guna_from_values(C_s=0.0, M=0.0, H=1.0)

        assert guna.tamas > 0.99
        assert guna.sattva < 0.01
        assert guna.rajas < 0.01


# =============================================================================
# Tier Behavior Verification
# =============================================================================

class TestTierBehavior:
    """Verify tier scalars affect output correctly."""

    def test_tier_scaling_order(self):
        """
        Tier 1 output > Tier 2 output > Tier 3 output
        (assuming same G and P)
        """
        inputs = {"base_intensity": 1.0, "C_s": 0.5, "M": 0.5, "H": 0.5}

        result_t1 = modulate_intensity(**inputs, tier=ModulationTier.ENTERPRISE_TIER_1)
        result_t2 = modulate_intensity(**inputs, tier=ModulationTier.ENTERPRISE_TIER_2)
        result_t3 = modulate_intensity(**inputs, tier=ModulationTier.CONSUMER)

        # Verify ordering
        assert result_t1.output_intensity > result_t2.output_intensity
        assert result_t2.output_intensity > result_t3.output_intensity

        # Verify ratios match tier scalars
        ratio_t1_t2 = result_t1.output_intensity / result_t2.output_intensity
        expected_ratio = 1.0 / 0.9
        assert abs(ratio_t1_t2 - expected_ratio) < 0.01

    def test_tier_scalar_exact_values(self):
        """Verify tier scalars are exactly as specified."""
        engine_t1 = EntropyModulationEngine(TIER_1_MODULATION_CONFIG)
        engine_t2 = EntropyModulationEngine(TIER_2_MODULATION_CONFIG)
        engine_t3 = EntropyModulationEngine(TIER_3_MODULATION_CONFIG)

        result_t1 = engine_t1.modulate(base_intensity=1.0, C_s=0.5, M=0.5, H=0.5)
        result_t2 = engine_t2.modulate(base_intensity=1.0, C_s=0.5, M=0.5, H=0.5)
        result_t3 = engine_t3.modulate(base_intensity=1.0, C_s=0.5, M=0.5, H=0.5)

        assert result_t1.T == 1.0
        assert result_t2.T == 0.9
        assert result_t3.T == 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
