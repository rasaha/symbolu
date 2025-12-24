"""
Cross-Domain Entropy Engine Tests
==================================

Comprehensive tests for determinism, tier safety, and correctness.

Test Categories:
    1. Determinism Tests - Same input → same output
    2. Tier Safety Tests - Gate constraints by tier
    3. Guna Entropy Tests - Balance measurement
    4. Kosha Entropy Tests - Layer distance
    5. Cross-Domain Entropy Tests - Structural distance
    6. Integration Tests - Full engine evaluation
"""

import pytest
from symbolu.entropy import (
    # Types
    EntropyMode,
    EntropyGate,
    EntropyResult,
    TierConfig,
    GunaProfile,
    KoshaProfile,
    DomainProfile,
    # Engine
    EntropyEngine,
    create_engine_for_tier,
    explain_entropy_result,
    # Configurations
    TIER_1_CONFIG,
    TIER_2_CONFIG,
    TIER_3_CONFIG,
    get_tier_config,
    # Individual computations
    compute_guna_entropy,
    compute_kosha_entropy,
    compute_cross_domain_entropy,
    # Constants
    KOSHA_ORDER,
    DIMENSION_NAMES,
)


# =============================================================================
# Determinism Tests
# =============================================================================

class TestDeterminism:
    """Test that entropy computations are fully deterministic."""

    def test_guna_entropy_determinism(self):
        """Same guna input always produces same output."""
        profile = GunaProfile(sattva=0.4, rajas=0.3, tamas=0.3)

        result1, _ = compute_guna_entropy(profile)
        result2, _ = compute_guna_entropy(profile)

        assert result1 == result2, "Guna entropy must be deterministic"

    def test_kosha_entropy_determinism(self):
        """Same kosha input always produces same output."""
        source = KoshaProfile(
            annamaya=0.1, pranamaya=0.2, manomaya=0.6,
            vijnanamaya=0.1, anandamaya=0.0
        )
        target = KoshaProfile(
            annamaya=0.0, pranamaya=0.1, manomaya=0.3,
            vijnanamaya=0.6, anandamaya=0.0
        )

        result1, _ = compute_kosha_entropy(source, target)
        result2, _ = compute_kosha_entropy(source, target)

        assert result1 == result2, "Kosha entropy must be deterministic"

    def test_cross_domain_entropy_determinism(self):
        """Same cross-domain input always produces same output."""
        source = DomainProfile(
            dimensions=tuple((dim, 0.5) for dim in DIMENSION_NAMES),
            domain_name="source"
        )
        target = DomainProfile(
            dimensions=tuple((dim, 0.7) for dim in DIMENSION_NAMES),
            domain_name="target"
        )

        result1, _ = compute_cross_domain_entropy(source, target)
        result2, _ = compute_cross_domain_entropy(source, target)

        assert result1 == result2, "Cross-domain entropy must be deterministic"

    def test_engine_evaluate_determinism(self):
        """Same engine evaluation always produces same result."""
        engine = EntropyEngine(TIER_3_CONFIG)

        guna = GunaProfile(sattva=0.4, rajas=0.3, tamas=0.3)
        source_kosha = KoshaProfile(
            annamaya=0.1, pranamaya=0.2, manomaya=0.6,
            vijnanamaya=0.1, anandamaya=0.0
        )
        target_kosha = KoshaProfile(
            annamaya=0.0, pranamaya=0.1, manomaya=0.3,
            vijnanamaya=0.6, anandamaya=0.0
        )

        result1 = engine.evaluate(
            guna_profile=guna,
            kosha_source=source_kosha,
            kosha_target=target_kosha,
        )
        result2 = engine.evaluate(
            guna_profile=guna,
            kosha_source=source_kosha,
            kosha_target=target_kosha,
        )

        assert result1.guna_entropy == result2.guna_entropy
        assert result1.kosha_entropy == result2.kosha_entropy
        assert result1.combined_entropy == result2.combined_entropy
        assert result1.gate == result2.gate

    def test_determinism_multiple_runs(self):
        """Engine produces same results across 100 runs."""
        engine = EntropyEngine(TIER_2_CONFIG)
        guna = GunaProfile(sattva=0.5, rajas=0.25, tamas=0.25)

        first_result = engine.evaluate(guna_profile=guna)
        for _ in range(100):
            result = engine.evaluate(guna_profile=guna)
            assert result.combined_entropy == first_result.combined_entropy


# =============================================================================
# Tier Safety Tests
# =============================================================================

class TestTierSafety:
    """Test that tiers enforce correct gate constraints."""

    def test_tier1_never_blocks(self):
        """Tier 1 (Enterprise Search) entropy never blocks."""
        engine = EntropyEngine(TIER_1_CONFIG)

        # Test with extreme entropy values
        extreme_guna = GunaProfile(sattva=1.0, rajas=0.0, tamas=0.0)
        extreme_kosha_source = KoshaProfile(
            annamaya=1.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=0.0
        )
        extreme_kosha_target = KoshaProfile(
            annamaya=0.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=1.0
        )

        result = engine.evaluate(
            guna_profile=extreme_guna,
            kosha_source=extreme_kosha_source,
            kosha_target=extreme_kosha_target,
        )

        assert result.gate == EntropyGate.ALLOW
        assert result.mode == EntropyMode.DIAGNOSTIC_ONLY

    def test_tier2_never_blocks(self):
        """Tier 2 (Enterprise Chat) entropy never blocks."""
        engine = EntropyEngine(TIER_2_CONFIG)

        # Test with extreme entropy values
        extreme_guna = GunaProfile(sattva=1.0, rajas=0.0, tamas=0.0)
        extreme_kosha_source = KoshaProfile(
            annamaya=1.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=0.0
        )
        extreme_kosha_target = KoshaProfile(
            annamaya=0.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=1.0
        )

        result = engine.evaluate(
            guna_profile=extreme_guna,
            kosha_source=extreme_kosha_source,
            kosha_target=extreme_kosha_target,
        )

        assert result.gate != EntropyGate.BLOCK
        assert result.gate in (EntropyGate.ALLOW, EntropyGate.ALLOW_WITH_MODULATION)
        assert result.mode == EntropyMode.MODULATION_ONLY

    def test_tier3_can_block_on_extreme_entropy(self):
        """Tier 3 (Consumer) may block on extreme structural incoherence."""
        # Create custom config with low block threshold for testing
        config = TierConfig(
            tier_name="consumer_test",
            mode=EntropyMode.FULL_GATING,
            modulation_threshold=0.3,
            block_threshold=0.6,  # Lower threshold for testing
            guna_weight=0.30,
            kosha_weight=0.30,
            cross_domain_weight=0.40,
        )
        engine = EntropyEngine(config)

        # Extreme entropy scenario
        extreme_guna = GunaProfile(sattva=1.0, rajas=0.0, tamas=0.0)
        extreme_kosha_source = KoshaProfile(
            annamaya=1.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=0.0
        )
        extreme_kosha_target = KoshaProfile(
            annamaya=0.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=1.0
        )

        # Extreme domain profiles
        source_domain = DomainProfile(
            dimensions=tuple((dim, 0.0) for dim in DIMENSION_NAMES),
            domain_name="source"
        )
        target_domain = DomainProfile(
            dimensions=tuple((dim, 1.0) for dim in DIMENSION_NAMES),
            domain_name="target"
        )

        result = engine.evaluate(
            guna_profile=extreme_guna,
            kosha_source=extreme_kosha_source,
            kosha_target=extreme_kosha_target,
            domain_source=source_domain,
            domain_target=target_domain,
        )

        assert result.mode == EntropyMode.FULL_GATING
        # With extreme inputs, combined entropy should be high
        assert result.combined_entropy > 0.5

    def test_tier1_is_diagnostic_only(self):
        """Tier 1 results indicate diagnostic-only mode."""
        engine = EntropyEngine(TIER_1_CONFIG)
        guna = GunaProfile(sattva=0.4, rajas=0.3, tamas=0.3)

        result = engine.evaluate(guna_profile=guna)

        assert result.mode == EntropyMode.DIAGNOSTIC_ONLY
        assert result.is_diagnostic_only

    def test_tier2_mode_is_modulation_only(self):
        """Tier 2 results indicate modulation-only mode."""
        engine = EntropyEngine(TIER_2_CONFIG)
        guna = GunaProfile(sattva=0.4, rajas=0.3, tamas=0.3)

        result = engine.evaluate(guna_profile=guna)

        assert result.mode == EntropyMode.MODULATION_ONLY

    def test_tier3_mode_is_full_gating(self):
        """Tier 3 results indicate full gating mode."""
        engine = EntropyEngine(TIER_3_CONFIG)
        guna = GunaProfile(sattva=0.4, rajas=0.3, tamas=0.3)

        result = engine.evaluate(guna_profile=guna)

        assert result.mode == EntropyMode.FULL_GATING


# =============================================================================
# Guna Entropy Tests
# =============================================================================

class TestGunaEntropy:
    """Test guna entropy computation."""

    def test_balanced_gunas_low_entropy(self):
        """Balanced guna distribution produces low entropy."""
        balanced = GunaProfile(sattva=0.33, rajas=0.33, tamas=0.34)
        entropy, trace = compute_guna_entropy(balanced)

        assert entropy < 0.1, "Balanced gunas should have very low entropy"
        assert trace.metric_name == "guna_entropy"

    def test_skewed_gunas_high_entropy(self):
        """Skewed guna distribution produces high entropy."""
        skewed = GunaProfile(sattva=1.0, rajas=0.0, tamas=0.0)
        entropy, trace = compute_guna_entropy(skewed)

        assert entropy > 0.8, "Completely skewed gunas should have high entropy"

    def test_moderate_imbalance_moderate_entropy(self):
        """Moderate imbalance produces moderate entropy."""
        moderate = GunaProfile(sattva=0.6, rajas=0.2, tamas=0.2)
        entropy, _ = compute_guna_entropy(moderate)

        # 0.6/0.2/0.2 is actually fairly balanced (not extreme skew)
        # so entropy should be low-to-moderate
        assert 0.1 < entropy < 0.5, "Moderate imbalance should have low-moderate entropy"

    def test_guna_entropy_range(self):
        """Guna entropy is always in [0.0, 1.0]."""
        test_cases = [
            GunaProfile(sattva=0.0, rajas=0.0, tamas=1.0),
            GunaProfile(sattva=1.0, rajas=0.0, tamas=0.0),
            GunaProfile(sattva=0.5, rajas=0.5, tamas=0.0),
            GunaProfile(sattva=0.33, rajas=0.33, tamas=0.34),
        ]

        for profile in test_cases:
            entropy, _ = compute_guna_entropy(profile)
            assert 0.0 <= entropy <= 1.0


# =============================================================================
# Kosha Entropy Tests
# =============================================================================

class TestKoshaEntropy:
    """Test kosha entropy computation."""

    def test_same_layer_low_entropy(self):
        """Same source and target layer produces low entropy."""
        manomaya_profile = KoshaProfile(
            annamaya=0.1, pranamaya=0.1, manomaya=0.8,
            vijnanamaya=0.0, anandamaya=0.0
        )

        entropy, trace = compute_kosha_entropy(manomaya_profile, manomaya_profile)

        assert entropy < 0.1, "Same layer should have very low entropy"
        assert trace.metric_name == "kosha_entropy"

    def test_adjacent_layers_low_entropy(self):
        """Adjacent layers produce low-moderate entropy."""
        source = KoshaProfile(
            annamaya=0.0, pranamaya=0.0, manomaya=0.8,
            vijnanamaya=0.2, anandamaya=0.0
        )
        target = KoshaProfile(
            annamaya=0.0, pranamaya=0.0, manomaya=0.2,
            vijnanamaya=0.8, anandamaya=0.0
        )

        entropy, _ = compute_kosha_entropy(source, target)

        assert entropy < 0.4, "Adjacent layers should have low-moderate entropy"

    def test_distant_layers_high_entropy(self):
        """Distant layers (annamaya → anandamaya) produce high entropy."""
        physical = KoshaProfile(
            annamaya=1.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=0.0
        )
        bliss = KoshaProfile(
            annamaya=0.0, pranamaya=0.0, manomaya=0.0,
            vijnanamaya=0.0, anandamaya=1.0
        )

        entropy, trace = compute_kosha_entropy(physical, bliss)

        assert entropy > 0.5, "Maximum layer distance should have high entropy"

    def test_kosha_entropy_range(self):
        """Kosha entropy is always in [0.0, 1.0]."""
        for i, source_kosha in enumerate(KOSHA_ORDER):
            for j, target_kosha in enumerate(KOSHA_ORDER):
                source = KoshaProfile(**{k: (1.0 if k == source_kosha else 0.0) for k in KOSHA_ORDER})
                target = KoshaProfile(**{k: (1.0 if k == target_kosha else 0.0) for k in KOSHA_ORDER})

                entropy, _ = compute_kosha_entropy(source, target)
                assert 0.0 <= entropy <= 1.0


# =============================================================================
# Cross-Domain Entropy Tests
# =============================================================================

class TestCrossDomainEntropy:
    """Test cross-domain entropy computation."""

    def test_identical_profiles_zero_entropy(self):
        """Identical domain profiles produce zero entropy."""
        profile = DomainProfile(
            dimensions=tuple((dim, 0.5) for dim in DIMENSION_NAMES),
            domain_name="test"
        )

        entropy, trace = compute_cross_domain_entropy(profile, profile)

        assert entropy == 0.0, "Identical profiles should have zero entropy"
        assert trace.metric_name == "cross_domain_entropy"

    def test_maximally_different_profiles_high_entropy(self):
        """Maximally different profiles produce high entropy."""
        source = DomainProfile(
            dimensions=tuple((dim, 0.0) for dim in DIMENSION_NAMES),
            domain_name="source"
        )
        target = DomainProfile(
            dimensions=tuple((dim, 1.0) for dim in DIMENSION_NAMES),
            domain_name="target"
        )

        entropy, _ = compute_cross_domain_entropy(source, target)

        assert entropy > 0.9, "Maximum difference should produce high entropy"

    def test_moderate_difference_moderate_entropy(self):
        """Moderate profile differences produce moderate entropy."""
        source = DomainProfile(
            dimensions=tuple((dim, 0.3) for dim in DIMENSION_NAMES),
            domain_name="source"
        )
        target = DomainProfile(
            dimensions=tuple((dim, 0.6) for dim in DIMENSION_NAMES),
            domain_name="target"
        )

        entropy, _ = compute_cross_domain_entropy(source, target)

        assert 0.2 < entropy < 0.8

    def test_cross_domain_entropy_range(self):
        """Cross-domain entropy is always in [0.0, 1.0]."""
        import random
        random.seed(42)  # For reproducibility

        for _ in range(20):
            source_dims = tuple((dim, random.random()) for dim in DIMENSION_NAMES)
            target_dims = tuple((dim, random.random()) for dim in DIMENSION_NAMES)

            source = DomainProfile(dimensions=source_dims)
            target = DomainProfile(dimensions=target_dims)

            entropy, _ = compute_cross_domain_entropy(source, target)
            assert 0.0 <= entropy <= 1.0


# =============================================================================
# Integration Tests
# =============================================================================

class TestEngineIntegration:
    """Test full engine integration."""

    def test_engine_with_all_profiles(self):
        """Engine correctly combines all entropy sources."""
        engine = EntropyEngine(TIER_3_CONFIG)

        guna = GunaProfile(sattva=0.4, rajas=0.3, tamas=0.3)
        source_kosha = KoshaProfile(
            annamaya=0.1, pranamaya=0.2, manomaya=0.6,
            vijnanamaya=0.1, anandamaya=0.0
        )
        target_kosha = KoshaProfile(
            annamaya=0.0, pranamaya=0.1, manomaya=0.3,
            vijnanamaya=0.6, anandamaya=0.0
        )
        source_domain = DomainProfile(
            dimensions=tuple((dim, 0.4) for dim in DIMENSION_NAMES),
            domain_name="source"
        )
        target_domain = DomainProfile(
            dimensions=tuple((dim, 0.6) for dim in DIMENSION_NAMES),
            domain_name="target"
        )

        result = engine.evaluate(
            guna_profile=guna,
            kosha_source=source_kosha,
            kosha_target=target_kosha,
            domain_source=source_domain,
            domain_target=target_domain,
        )

        assert isinstance(result, EntropyResult)
        assert 0.0 <= result.guna_entropy <= 1.0
        assert 0.0 <= result.kosha_entropy <= 1.0
        assert 0.0 <= result.cross_domain_entropy <= 1.0
        assert 0.0 <= result.combined_entropy <= 1.0
        assert result.gate in EntropyGate
        assert result.mode == EntropyMode.FULL_GATING
        assert len(result.trace) >= 3

    def test_engine_with_missing_profiles(self):
        """Engine handles missing profiles gracefully."""
        engine = EntropyEngine(TIER_1_CONFIG)

        # Only provide guna profile
        result = engine.evaluate(guna_profile=GunaProfile(0.4, 0.3, 0.3))

        assert result.kosha_entropy == 0.0
        assert result.cross_domain_entropy == 0.0
        assert result.gate == EntropyGate.ALLOW

    def test_engine_factory_function(self):
        """Factory function creates correct engine."""
        engine = create_engine_for_tier("enterprise_search")
        assert engine.mode == EntropyMode.DIAGNOSTIC_ONLY

        engine = create_engine_for_tier("enterprise_chat")
        assert engine.mode == EntropyMode.MODULATION_ONLY

        engine = create_engine_for_tier("consumer")
        assert engine.mode == EntropyMode.FULL_GATING

    def test_get_tier_config(self):
        """Tier config retrieval works correctly."""
        config = get_tier_config("tier_1")
        assert config.mode == EntropyMode.DIAGNOSTIC_ONLY

        config = get_tier_config("tier_2")
        assert config.mode == EntropyMode.MODULATION_ONLY

        config = get_tier_config("tier_3")
        assert config.mode == EntropyMode.FULL_GATING

    def test_explain_entropy_result(self):
        """Explanation helper provides useful output."""
        engine = EntropyEngine(TIER_3_CONFIG)
        guna = GunaProfile(sattva=0.7, rajas=0.2, tamas=0.1)

        result = engine.evaluate(guna_profile=guna)
        explanation = explain_entropy_result(result)

        assert "summary" in explanation
        assert "metrics" in explanation
        assert "gate" in explanation
        assert "mode" in explanation
        assert "action" in explanation


# =============================================================================
# Configuration Tests
# =============================================================================

class TestConfiguration:
    """Test configuration validation."""

    def test_weights_must_sum_to_one(self):
        """TierConfig validates that weights sum to 1.0."""
        with pytest.raises(ValueError, match="weights must sum to 1.0"):
            TierConfig(
                tier_name="invalid",
                mode=EntropyMode.DIAGNOSTIC_ONLY,
                guna_weight=0.5,
                kosha_weight=0.5,
                cross_domain_weight=0.5,  # Sum = 1.5
            )

    def test_thresholds_must_be_valid(self):
        """TierConfig validates threshold ranges."""
        with pytest.raises(ValueError):
            TierConfig(
                tier_name="invalid",
                mode=EntropyMode.DIAGNOSTIC_ONLY,
                modulation_threshold=1.5,  # Invalid
            )

    def test_tier_config_properties(self):
        """TierConfig properties work correctly."""
        t1 = TIER_1_CONFIG
        assert t1.is_diagnostic_only
        assert not t1.allow_modulation
        assert not t1.allow_block

        t2 = TIER_2_CONFIG
        assert not t2.is_diagnostic_only
        assert t2.allow_modulation
        assert not t2.allow_block

        t3 = TIER_3_CONFIG
        assert not t3.is_diagnostic_only
        assert t3.allow_modulation
        assert t3.allow_block


# =============================================================================
# Result Properties Tests
# =============================================================================

class TestEntropyResultProperties:
    """Test EntropyResult properties."""

    def test_result_to_dict(self):
        """Result can be serialized to dict."""
        engine = EntropyEngine(TIER_1_CONFIG)
        guna = GunaProfile(sattva=0.4, rajas=0.3, tamas=0.3)

        result = engine.evaluate(guna_profile=guna)
        result_dict = result.to_dict()

        assert "guna_entropy" in result_dict
        assert "kosha_entropy" in result_dict
        assert "cross_domain_entropy" in result_dict
        assert "combined_entropy" in result_dict
        assert "gate" in result_dict
        assert "mode" in result_dict
        assert "trace" in result_dict

    def test_result_properties(self):
        """Result properties work correctly."""
        engine = EntropyEngine(TIER_1_CONFIG)
        result = engine.evaluate(guna_profile=GunaProfile(0.4, 0.3, 0.3))

        assert result.is_diagnostic_only
        assert not result.is_blocked
        assert not result.allows_modulation
