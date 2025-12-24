"""
Integration Tests: Signal Wiring and Guna Entropy Modulation
=============================================================

Symbol-U v2.6.1 - Integration Tests

These tests verify the complete integration between:
    1. Signal Wiring Layer (compute_H, compute_M)
    2. Guna Derivation (S, R, T computation)
    3. Entropy Modulation Engine (E = G * P * T)
    4. Pipeline Integration (PipelineModulationEngine)

Test Categories:
    1. Entropy Mode Integration - All 3 modes through full pipeline
    2. Motion Mode Integration - All 4 modes through full pipeline
    3. Combined Configuration Integration
    4. Tier x Mode Cross-Product Testing
    5. Audit Trail Chain Verification
    6. Determinism Across Full Integration
    7. Edge Cases and Boundary Conditions

EXPLICIT NON-CAPABILITIES VERIFIED:
    - No learning across invocations
    - No state memory between calls
    - No adaptation to patterns
    - Deterministic outputs only
"""

import math
import pytest
from typing import Dict, Tuple

from symbolu.guna_modulation import (
    # Constants
    LN_3,
    LN_5,
    LN_10,
    H_MID,
    EPSILON,
    # Enums
    EntropyMode,
    MotionMode,
    ModulationTier,
    # Configuration
    SignalWiringConfig,
    DEFAULT_WIRING_CONFIG,
    TIER_1_MODULATION_CONFIG,
    TIER_2_MODULATION_CONFIG,
    TIER_3_MODULATION_CONFIG,
    GunaWeights,
    PolicyConfig,
    # Core types
    GunaVector,
    ModulationResult,
    IntegratedModulationResult,
    # Engine
    EntropyModulationEngine,
    PipelineModulationEngine,
    # Functions
    compute_H,
    compute_M,
    wire_signals,
    modulate_intensity,
    modulate_from_pipeline,
    create_pipeline_engine,
    create_default_pipeline_engine,
    # Guna derivation
    derive_guna_from_values,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def standard_pipeline_inputs() -> Dict:
    """Standard pipeline inputs for consistent testing."""
    return {
        "H_G": 0.5,
        "H_D": 1.2,
        "H_K": 0.8,
        "candidate_aspect_vector": {"clarity": 0.8, "depth": 0.6, "precision": 0.7},
        "context_aspect_vector": {"clarity": 0.6, "depth": 0.5, "precision": 0.8},
        "domain_jump_count": 2,
        "intent": "informative",
    }


@pytest.fixture
def high_entropy_inputs() -> Dict:
    """High entropy scenario inputs."""
    return {
        "H_G": LN_3 * 0.9,  # 90% of max
        "H_D": LN_10 * 0.9,
        "H_K": LN_5 * 0.9,
        "candidate_aspect_vector": {"a": 0.1, "b": 0.9},
        "context_aspect_vector": {"a": 0.9, "b": 0.1},  # Orthogonal
        "domain_jump_count": 5,
        "intent": "directive",
    }


@pytest.fixture
def low_entropy_inputs() -> Dict:
    """Low entropy scenario inputs."""
    return {
        "H_G": LN_3 * 0.1,  # 10% of max
        "H_D": LN_10 * 0.1,
        "H_K": LN_5 * 0.1,
        "candidate_aspect_vector": {"a": 0.8},
        "context_aspect_vector": {"a": 0.79},  # Very similar
        "domain_jump_count": 0,
        "intent": "neutral",
    }


# =============================================================================
# Entropy Mode Integration Tests
# =============================================================================

class TestEntropyModeIntegration:
    """Test all entropy modes through the full pipeline."""

    def test_guna_mode_produces_expected_H(self, standard_pipeline_inputs):
        """Test GUNA mode produces correctly normalized H."""
        engine = create_pipeline_engine(entropy_mode=EntropyMode.GUNA)

        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Verify H was computed using GUNA formula
        expected_H = standard_pipeline_inputs["H_G"] / LN_3
        assert abs(result.H - expected_H) < 1e-10
        assert result.wired_signals.audit.entropy_audit.entropy_mode == "guna"

    def test_dimensional_mode_produces_expected_H(self, standard_pipeline_inputs):
        """Test DIMENSIONAL mode produces correctly normalized H."""
        engine = create_pipeline_engine(entropy_mode=EntropyMode.DIMENSIONAL)

        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Verify H was computed using DIMENSIONAL formula
        expected_H = standard_pipeline_inputs["H_D"] / LN_10
        assert abs(result.H - expected_H) < 1e-10
        assert result.wired_signals.audit.entropy_audit.entropy_mode == "dimensional"

    def test_kosha_mode_produces_expected_H(self, standard_pipeline_inputs):
        """Test KOSHA mode produces correctly normalized H."""
        engine = create_pipeline_engine(entropy_mode=EntropyMode.KOSHA)

        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Verify H was computed using KOSHA formula
        expected_H = standard_pipeline_inputs["H_K"] / LN_5
        assert abs(result.H - expected_H) < 1e-10
        assert result.wired_signals.audit.entropy_audit.entropy_mode == "kosha"

    def test_entropy_modes_produce_different_outputs(self, standard_pipeline_inputs):
        """Test that different entropy modes produce different modulation results."""
        results = {}

        for mode in EntropyMode:
            engine = create_pipeline_engine(entropy_mode=mode)
            result = engine.modulate_from_pipeline(
                base_intensity=1.0,
                C_s=0.7,
                **standard_pipeline_inputs,
            )
            results[mode] = result.output_intensity

        # All three modes should produce different outputs (given different raw values)
        assert results[EntropyMode.GUNA] != results[EntropyMode.DIMENSIONAL]
        assert results[EntropyMode.DIMENSIONAL] != results[EntropyMode.KOSHA]
        assert results[EntropyMode.GUNA] != results[EntropyMode.KOSHA]

    def test_entropy_mode_affects_guna_vector(self, standard_pipeline_inputs):
        """Test that entropy mode affects the derived Guna vector."""
        guna_results = {}

        for mode in EntropyMode:
            engine = create_pipeline_engine(entropy_mode=mode)
            result = engine.modulate_from_pipeline(
                base_intensity=1.0,
                C_s=0.7,
                **standard_pipeline_inputs,
            )
            gv = result.modulation_result.guna_vector
            guna_results[mode] = (gv.sattva, gv.rajas, gv.tamas)

        # Guna vectors should differ based on H value
        assert guna_results[EntropyMode.GUNA] != guna_results[EntropyMode.DIMENSIONAL]


# =============================================================================
# Motion Mode Integration Tests
# =============================================================================

class TestMotionModeIntegration:
    """Test all motion modes through the full pipeline."""

    def test_semantic_mode_uses_cosine_distance(self, standard_pipeline_inputs):
        """Test SEMANTIC mode computes M from aspect vector similarity."""
        engine = create_pipeline_engine(motion_mode=MotionMode.SEMANTIC)

        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Verify M was computed using semantic formula
        audit = result.wired_signals.audit.motion_audit
        assert audit.motion_mode == "semantic"
        assert abs(result.M - audit.delta_sem) < 1e-10

    def test_structural_mode_uses_jump_count(self, standard_pipeline_inputs):
        """Test STRUCTURAL mode computes M from domain jump count."""
        engine = create_pipeline_engine(motion_mode=MotionMode.STRUCTURAL)

        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Verify M was computed using structural formula
        audit = result.wired_signals.audit.motion_audit
        assert audit.motion_mode == "structural"
        assert abs(result.M - audit.delta_str_norm) < 1e-10

        # Expected: 2 jumps / 5 max = 0.4
        expected_M = 2 / 5
        assert abs(result.M - expected_M) < 1e-10

    def test_experiential_mode_uses_intent(self, standard_pipeline_inputs):
        """Test EXPERIENTIAL mode computes M from intent classification."""
        engine = create_pipeline_engine(motion_mode=MotionMode.EXPERIENTIAL)

        # Informative intent should give M = 0
        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **standard_pipeline_inputs,
        )
        assert result.M == 0.0

        # Directive intent should give M = 1
        directive_inputs = {**standard_pipeline_inputs, "intent": "directive"}
        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **directive_inputs,
        )
        assert result.M == 1.0

    def test_composite_mode_uses_weighted_average(self, standard_pipeline_inputs):
        """Test COMPOSITE mode computes M as weighted average of all deltas."""
        weights = (1.0, 2.0, 0.5)  # w1=1, w2=2, w3=0.5
        engine = create_pipeline_engine(
            motion_mode=MotionMode.COMPOSITE,
            composite_weights=weights,
        )

        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        audit = result.wired_signals.audit.motion_audit
        assert audit.motion_mode == "composite"
        assert audit.weights == weights

        # Verify weighted average formula
        d_sem = audit.delta_sem
        d_str = audit.delta_str_norm
        d_exp = audit.delta_exp
        expected_M = (1.0 * d_sem + 2.0 * d_str + 0.5 * d_exp) / 3.5
        assert abs(result.M - expected_M) < 1e-10

    def test_motion_modes_produce_different_outputs(self, standard_pipeline_inputs):
        """Test that different motion modes produce different modulation results."""
        results = {}

        for mode in MotionMode:
            weights = (1.0, 1.0, 1.0) if mode == MotionMode.COMPOSITE else None
            engine = create_pipeline_engine(motion_mode=mode, composite_weights=weights)
            result = engine.modulate_from_pipeline(
                base_intensity=1.0,
                C_s=0.7,
                **standard_pipeline_inputs,
            )
            results[mode] = result.M

        # Modes should produce different M values
        unique_values = set(results.values())
        assert len(unique_values) >= 2  # At least some modes differ


# =============================================================================
# Combined Configuration Integration Tests
# =============================================================================

class TestCombinedConfigurationIntegration:
    """Test combined entropy and motion mode configurations."""

    @pytest.mark.parametrize("entropy_mode", list(EntropyMode))
    @pytest.mark.parametrize("motion_mode", [
        MotionMode.SEMANTIC,
        MotionMode.STRUCTURAL,
        MotionMode.EXPERIENTIAL,
    ])
    def test_all_mode_combinations(
        self,
        entropy_mode,
        motion_mode,
        standard_pipeline_inputs,
    ):
        """Test all entropy x motion mode combinations produce valid results."""
        engine = create_pipeline_engine(
            entropy_mode=entropy_mode,
            motion_mode=motion_mode,
        )

        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Verify valid outputs
        assert 0.0 <= result.H <= 1.0
        assert 0.0 <= result.M <= 1.0
        assert result.output_intensity >= 0.0
        assert result.E >= 0.0

        # Verify audit trail reflects configuration
        assert result.wired_signals.audit.entropy_audit.entropy_mode == entropy_mode.value
        assert result.wired_signals.audit.motion_audit.motion_mode == motion_mode.value

    def test_composite_with_all_entropy_modes(self, standard_pipeline_inputs):
        """Test COMPOSITE motion with each entropy mode."""
        weights = (0.5, 1.5, 1.0)

        for entropy_mode in EntropyMode:
            engine = create_pipeline_engine(
                entropy_mode=entropy_mode,
                motion_mode=MotionMode.COMPOSITE,
                composite_weights=weights,
            )

            result = engine.modulate_from_pipeline(
                base_intensity=1.0,
                C_s=0.7,
                **standard_pipeline_inputs,
            )

            assert 0.0 <= result.H <= 1.0
            assert 0.0 <= result.M <= 1.0
            assert result.wired_signals.audit.motion_audit.weights == weights


# =============================================================================
# Tier x Mode Cross-Product Testing
# =============================================================================

class TestTierModeIntegration:
    """Test tier configurations with different modes."""

    @pytest.mark.parametrize("tier", list(ModulationTier))
    def test_each_tier_with_guna_semantic(self, tier, standard_pipeline_inputs):
        """Test default mode configuration across all tiers."""
        engine = PipelineModulationEngine(
            tier=tier,
            wiring_config=SignalWiringConfig(
                entropy_mode=EntropyMode.GUNA,
                motion_mode=MotionMode.SEMANTIC,
            ),
        )

        result = engine.modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Verify tier scalar is applied
        expected_tier_scalars = {
            ModulationTier.ENTERPRISE_TIER_1: 1.0,
            ModulationTier.ENTERPRISE_TIER_2: 0.9,
            ModulationTier.CONSUMER: 0.85,
        }

        assert abs(result.modulation_result.T - expected_tier_scalars[tier]) < 1e-10

    def test_tier_ordering_preserved_across_modes(self, standard_pipeline_inputs):
        """Test that tier ordering (T1 > T2 > Consumer) is preserved."""
        results = {}

        for tier in ModulationTier:
            for entropy_mode in [EntropyMode.GUNA, EntropyMode.DIMENSIONAL]:
                engine = PipelineModulationEngine(
                    tier=tier,
                    wiring_config=SignalWiringConfig(entropy_mode=entropy_mode),
                )
                result = engine.modulate_from_pipeline(
                    base_intensity=1.0,
                    C_s=0.7,
                    **standard_pipeline_inputs,
                )
                results[(tier, entropy_mode)] = result.output_intensity

        # For same entropy mode, T1 >= T2 >= Consumer (higher tier = higher output)
        for mode in [EntropyMode.GUNA, EntropyMode.DIMENSIONAL]:
            t1 = results[(ModulationTier.ENTERPRISE_TIER_1, mode)]
            t2 = results[(ModulationTier.ENTERPRISE_TIER_2, mode)]
            consumer = results[(ModulationTier.CONSUMER, mode)]

            assert t1 >= t2 >= consumer


# =============================================================================
# Audit Trail Chain Verification
# =============================================================================

class TestAuditTrailChain:
    """Test complete audit trail from signal wiring through modulation."""

    def test_complete_audit_chain(self, standard_pipeline_inputs):
        """Test that audit trail captures all computation steps."""
        result = modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Signal wiring audit
        wiring_audit = result.wired_signals.audit
        assert wiring_audit.entropy_audit.entropy_mode is not None
        assert wiring_audit.entropy_audit.H_raw is not None
        assert wiring_audit.entropy_audit.H_normalized is not None
        assert wiring_audit.motion_audit.delta_sem is not None
        assert wiring_audit.motion_audit.delta_str_norm is not None
        assert wiring_audit.motion_audit.delta_exp is not None
        assert wiring_audit.motion_audit.M is not None

        # Modulation audit
        mod_result = result.modulation_result
        assert mod_result.guna_vector is not None
        assert mod_result.G is not None
        assert mod_result.P is not None
        assert mod_result.T is not None
        assert mod_result.E is not None
        assert len(mod_result.trace) > 0

    def test_audit_values_are_consistent(self, standard_pipeline_inputs):
        """Test that audit values match actual computed values."""
        result = modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Wiring values match result
        assert result.H == result.wired_signals.audit.entropy_audit.H_normalized
        assert result.M == result.wired_signals.audit.motion_audit.M

        # E = G * P * T
        mod = result.modulation_result
        expected_E = mod.G * mod.P * mod.T
        assert abs(mod.E - expected_E) < 1e-10

        # Output = Base * E
        expected_output = 0.8 * mod.E
        assert abs(mod.output_intensity - expected_output) < 1e-10

    def test_serialization_preserves_audit(self, standard_pipeline_inputs):
        """Test that to_dict() preserves complete audit trail."""
        result = modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        d = result.to_dict()

        # Wiring audit in serialization
        assert "wired_signals" in d
        assert "audit" in d["wired_signals"]
        audit = d["wired_signals"]["audit"]
        assert "entropy_mode" in audit
        assert "H_raw" in audit
        assert "H_normalized" in audit
        assert "motion_mode" in audit
        assert "delta_sem" in audit
        assert "M" in audit

        # Modulation audit in serialization
        assert "modulation_result" in d
        mod = d["modulation_result"]
        assert "guna_vector" in mod
        assert "G" in mod
        assert "E" in mod
        assert "trace" in mod


# =============================================================================
# Determinism Across Full Integration
# =============================================================================

class TestDeterminismIntegration:
    """Test determinism across the full integrated system."""

    def test_same_inputs_same_outputs_all_modes(self, standard_pipeline_inputs):
        """Test determinism for all mode combinations."""
        for entropy_mode in EntropyMode:
            for motion_mode in [MotionMode.SEMANTIC, MotionMode.STRUCTURAL]:
                engine = create_pipeline_engine(
                    entropy_mode=entropy_mode,
                    motion_mode=motion_mode,
                )

                result1 = engine.modulate_from_pipeline(
                    base_intensity=0.8,
                    C_s=0.7,
                    **standard_pipeline_inputs,
                )
                result2 = engine.modulate_from_pipeline(
                    base_intensity=0.8,
                    C_s=0.7,
                    **standard_pipeline_inputs,
                )

                assert result1.H == result2.H
                assert result1.M == result2.M
                assert result1.E == result2.E
                assert result1.output_intensity == result2.output_intensity

    def test_different_engines_same_config_same_output(self, standard_pipeline_inputs):
        """Test that different engine instances with same config produce same output."""
        config = SignalWiringConfig(
            entropy_mode=EntropyMode.DIMENSIONAL,
            motion_mode=MotionMode.STRUCTURAL,
        )

        engine1 = PipelineModulationEngine(wiring_config=config)
        engine2 = PipelineModulationEngine(wiring_config=config)

        result1 = engine1.modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            **standard_pipeline_inputs,
        )
        result2 = engine2.modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        assert result1.output_intensity == result2.output_intensity

    def test_no_state_memory_between_calls(self, standard_pipeline_inputs, high_entropy_inputs):
        """Test that previous calls don't affect subsequent calls."""
        engine = create_default_pipeline_engine()

        # First call with standard inputs
        result1_a = engine.modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        # Call with different inputs
        _ = engine.modulate_from_pipeline(
            base_intensity=0.5,
            C_s=0.3,
            **high_entropy_inputs,
        )

        # Call again with original inputs - should match first call exactly
        result1_b = engine.modulate_from_pipeline(
            base_intensity=0.8,
            C_s=0.7,
            **standard_pipeline_inputs,
        )

        assert result1_a.output_intensity == result1_b.output_intensity
        assert result1_a.H == result1_b.H
        assert result1_a.M == result1_b.M


# =============================================================================
# Edge Cases and Boundary Conditions
# =============================================================================

class TestEdgeCasesIntegration:
    """Test edge cases through the full integration."""

    def test_zero_entropy_all_modes(self):
        """Test zero entropy input through all modes."""
        inputs = {
            "H_G": 0.0,
            "H_D": 0.0,
            "H_K": 0.0,
            "candidate_aspect_vector": {"a": 0.5},
            "context_aspect_vector": {"a": 0.5},
            "domain_jump_count": 0,
            "intent": "neutral",
        }

        for entropy_mode in EntropyMode:
            result = modulate_from_pipeline(
                base_intensity=1.0,
                C_s=0.7,
                entropy_mode=entropy_mode,
                **inputs,
            )
            assert result.H == 0.0

    def test_max_entropy_all_modes(self):
        """Test maximum entropy input through all modes."""
        inputs = {
            "H_G": LN_3,
            "H_D": LN_10,
            "H_K": LN_5,
            "candidate_aspect_vector": {"a": 0.5},
            "context_aspect_vector": {"a": 0.5},
            "domain_jump_count": 0,
            "intent": "neutral",
        }

        for entropy_mode in EntropyMode:
            result = modulate_from_pipeline(
                base_intensity=1.0,
                C_s=0.7,
                entropy_mode=entropy_mode,
                **inputs,
            )
            assert abs(result.H - 1.0) < 1e-10

    def test_zero_motion_all_modes(self):
        """Test zero motion scenarios through all modes."""
        # Identical vectors = zero semantic motion
        # Zero jumps = zero structural motion
        # Neutral intent = zero experiential motion
        inputs = {
            "H_G": 0.5,
            "H_D": 1.0,
            "H_K": 0.5,
            "candidate_aspect_vector": {"a": 0.8, "b": 0.2},
            "context_aspect_vector": {"a": 0.8, "b": 0.2},  # Identical
            "domain_jump_count": 0,
            "intent": "neutral",
        }

        result_sem = modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            motion_mode=MotionMode.SEMANTIC,
            **inputs,
        )
        assert abs(result_sem.M) < 1e-10

        result_str = modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            motion_mode=MotionMode.STRUCTURAL,
            **inputs,
        )
        assert result_str.M == 0.0

        result_exp = modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            motion_mode=MotionMode.EXPERIENTIAL,
            **inputs,
        )
        assert result_exp.M == 0.0

    def test_max_motion_all_modes(self):
        """Test maximum motion scenarios through all modes."""
        inputs = {
            "H_G": 0.5,
            "H_D": 1.0,
            "H_K": 0.5,
            "candidate_aspect_vector": {"a": 1.0},
            "context_aspect_vector": {"b": 1.0},  # Orthogonal
            "domain_jump_count": 10,  # Beyond max
            "intent": "directive",  # Experiential trigger
        }

        result_sem = modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            motion_mode=MotionMode.SEMANTIC,
            **inputs,
        )
        assert abs(result_sem.M - 1.0) < 1e-10  # Orthogonal = max semantic motion

        result_str = modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            motion_mode=MotionMode.STRUCTURAL,
            **inputs,
        )
        assert result_str.M == 1.0  # Clamped at max

        result_exp = modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.7,
            motion_mode=MotionMode.EXPERIENTIAL,
            **inputs,
        )
        assert result_exp.M == 1.0  # Directive intent

    def test_high_entropy_high_motion_scenario(self, high_entropy_inputs):
        """Test high entropy + high motion through full pipeline."""
        result = modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.3,  # Low coherence
            entropy_mode=EntropyMode.GUNA,
            motion_mode=MotionMode.SEMANTIC,
            **high_entropy_inputs,
        )

        # High entropy should increase Tamas in Guna vector
        gv = result.modulation_result.guna_vector
        assert gv.tamas > 0.3  # Significant Tamas component

    def test_low_entropy_low_motion_scenario(self, low_entropy_inputs):
        """Test low entropy + low motion through full pipeline."""
        result = modulate_from_pipeline(
            base_intensity=1.0,
            C_s=0.9,  # High coherence
            entropy_mode=EntropyMode.GUNA,
            motion_mode=MotionMode.SEMANTIC,
            **low_entropy_inputs,
        )

        # Low entropy + high coherence should increase Sattva
        gv = result.modulation_result.guna_vector
        assert gv.sattva > 0.3  # Significant Sattva component


# =============================================================================
# Formula Chain Verification
# =============================================================================

class TestFormulaChainIntegration:
    """Verify complete formula chain from wiring through modulation."""

    def test_complete_formula_chain(self, standard_pipeline_inputs):
        """Verify each step in the formula chain matches specification."""
        C_s = 0.7
        base_intensity = 0.8

        result = modulate_from_pipeline(
            base_intensity=base_intensity,
            C_s=C_s,
            entropy_mode=EntropyMode.GUNA,
            motion_mode=MotionMode.SEMANTIC,
            **standard_pipeline_inputs,
        )

        # Step 1: H wiring
        H = result.H
        expected_H = standard_pipeline_inputs["H_G"] / LN_3
        assert abs(H - expected_H) < 1e-10

        # Step 2: M wiring (semantic delta from aspect vectors)
        M = result.M
        # Verified via audit
        assert M == result.wired_signals.audit.motion_audit.delta_sem

        # Step 3: Guna derivation formulas
        # S_raw = C_s * (1 - H)
        S_raw = C_s * (1 - H)
        # R_raw = M * (1 - |H - H_mid|)
        R_raw = M * (1 - abs(H - H_MID))
        # T_raw = H * (1 - C_s)
        T_raw = H * (1 - C_s)

        # Normalized
        Z = S_raw + R_raw + T_raw + EPSILON
        S = S_raw / Z
        R = R_raw / Z
        T = T_raw / Z

        gv = result.modulation_result.guna_vector
        assert abs(gv.sattva - S) < 1e-8
        assert abs(gv.rajas - R) < 1e-8
        assert abs(gv.tamas - T) < 1e-8

        # Step 4: G = w_S * S + w_R * R + w_T * T
        # Using default weights (0.9, 1.05, 0.6)
        G = 0.9 * S + 1.05 * R + 0.6 * T
        assert abs(result.modulation_result.G - G) < 1e-8

        # Step 5: P = clamp(1 - r_risk - r_escalation, 0, 1)
        # Default policy: r_risk=0, r_escalation=0 -> P=1
        assert abs(result.modulation_result.P - 1.0) < 1e-10

        # Step 6: T = tier_scalar (default = 1.0)
        assert abs(result.modulation_result.T - 1.0) < 1e-10

        # Step 7: E = G * P * T
        E = G * 1.0 * 1.0
        assert abs(result.modulation_result.E - E) < 1e-8

        # Step 8: OUTPUT = BASE * E
        expected_output = base_intensity * E
        assert abs(result.output_intensity - expected_output) < 1e-8
