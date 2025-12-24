"""
DHA Engine Tests
================

Comprehensive tests for the DHA (Delivery Harmonization Algorithm) engine.

All tests are deterministic - same inputs must produce same outputs.
"""

import pytest
import math
from symbolu.dha import (
    DHAEngine,
    DHAConfig,
    DHAInputs,
    DHAResult,
    DHANoOpResult,
    EntropySource,
    ToneLogitConfig,
    IntensityConfig,
    RestraintConfig,
    NumericsConfig,
    Tier,
    ToneWeights,
    apply_dha,
    compute_dha,
)


class TestDHAEngineDeterminism:
    """Test 1: Determinism - same inputs produce same outputs."""

    def test_determinism_basic(self):
        """Same inputs must produce exactly same outputs."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(
            C_s=0.7,
            M=0.3,
            H_G=0.5,
            C_contr=0.1,
            s=0.5,
            r=0.3,
            t=0.2,
            tier=Tier.CONSUMER,
        )

        # Run twice
        _, result1 = engine.apply("test", signals)
        _, result2 = engine.apply("test", signals)

        # Results must be identical
        assert isinstance(result1, DHAResult)
        assert isinstance(result2, DHAResult)
        assert result1.D == result2.D
        assert result1.I == result2.I
        assert result1.R == result2.R
        assert result1.tone_weights.sweet == result2.tone_weights.sweet
        assert result1.tone_weights.jolt == result2.tone_weights.jolt
        assert result1.tone_weights.metaphor == result2.tone_weights.metaphor

    def test_determinism_multiple_calls(self):
        """Multiple calls with same inputs produce same outputs."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(
            C_s=0.8,
            M=0.2,
            H_G=0.4,
            C_contr=0.0,
            s=0.6,
            r=0.2,
            t=0.2,
        )

        results = []
        for _ in range(10):
            _, result = engine.apply("test", signals)
            results.append(result)

        # All results must be identical
        first = results[0]
        for r in results[1:]:
            assert r.D == first.D
            assert r.I == first.I
            assert r.R == first.R

    def test_determinism_exact_floats(self):
        """Float values must match exactly (or to fixed decimals)."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(
            C_s=0.75,
            M=0.25,
            H_G=0.5,
            C_contr=0.15,
            s=0.45,
            r=0.35,
            t=0.20,
        )

        _, result1 = engine.apply("test", signals)
        _, result2 = engine.apply("test", signals)

        # Compare with rounding to 6 decimals (as per spec)
        assert round(result1.D, 6) == round(result2.D, 6)
        assert round(result1.I, 6) == round(result2.I, 6)
        assert round(result1.R, 6) == round(result2.R, 6)


class TestDHAEngineDisabled:
    """Test 2: Disable Test - enabled=False returns no-op."""

    def test_disabled_by_default(self):
        """DHA is disabled by default."""
        config = DHAConfig()
        assert config.enabled is False

    def test_disabled_returns_noop(self):
        """Disabled DHA returns DHANoOpResult."""
        config = DHAConfig(enabled=False)
        engine = DHAEngine(config)

        signals = DHAInputs(C_s=0.8, M=0.3, H_G=0.5)
        _, result = engine.apply("test", signals)

        assert isinstance(result, DHANoOpResult)
        assert result.enabled is False
        assert "disabled" in result.reason.lower()

    def test_disabled_noop_dict(self):
        """No-op result to_dict indicates not applied."""
        result = DHANoOpResult(enabled=False, reason="DHA disabled via config")
        d = result.to_dict()

        assert d["enabled"] is False
        assert d["dha_applied"] is False

    def test_disabled_does_not_compute(self):
        """Disabled DHA does not compute D, I, R."""
        config = DHAConfig(enabled=False)
        engine = DHAEngine(config)

        signals = DHAInputs(C_s=0.8, M=0.3, H_G=0.5)
        _, result = engine.apply("test", signals)

        assert isinstance(result, DHANoOpResult)
        # No D, I, R attributes on no-op result
        assert not hasattr(result, 'D')
        assert not hasattr(result, 'I')
        assert not hasattr(result, 'R')


class TestEntropyOptions:
    """Test 3: Entropy Option Tests - correct H normalization."""

    def test_option_a_guna_entropy(self):
        """Option A: H = H_G / ln(3)."""
        from symbolu.dha.math import normalize_entropy_guna, LN_3

        H_G = 0.5
        H = normalize_entropy_guna(H_G)

        expected = H_G / LN_3
        assert abs(H - expected) < 1e-9
        assert 0.0 <= H <= 1.0

    def test_option_b_dimensional_entropy(self):
        """Option B: H = H_D / ln(10)."""
        from symbolu.dha.math import normalize_entropy_dimensional, LN_10

        H_D = 1.5
        H = normalize_entropy_dimensional(H_D)

        expected = H_D / LN_10
        assert abs(H - expected) < 1e-9
        assert 0.0 <= H <= 1.0

    def test_option_c_kosha_entropy(self):
        """Option C: H = H_K / ln(5)."""
        from symbolu.dha.math import normalize_entropy_kosha, LN_5

        H_K = 0.8
        H = normalize_entropy_kosha(H_K)

        expected = H_K / LN_5
        assert abs(H - expected) < 1e-9
        assert 0.0 <= H <= 1.0

    def test_default_is_option_a(self):
        """Default entropy source is Option A (Guna)."""
        config = DHAConfig(enabled=True)
        assert config.entropy_source == EntropySource.GUNA

    def test_entropy_source_configurable(self):
        """Entropy source is configurable per config."""
        config_a = DHAConfig(enabled=True, entropy_source=EntropySource.GUNA)
        config_b = DHAConfig(enabled=True, entropy_source=EntropySource.DIMENSIONAL)
        config_c = DHAConfig(enabled=True, entropy_source=EntropySource.KOSHA)

        assert config_a.entropy_source == EntropySource.GUNA
        assert config_b.entropy_source == EntropySource.DIMENSIONAL
        assert config_c.entropy_source == EntropySource.KOSHA

    def test_entropy_fallback_when_missing(self):
        """Falls back to available entropy when requested source is missing."""
        from symbolu.dha.math import get_normalized_entropy

        # Request guna but only dimensional available
        H, source, raw = get_normalized_entropy(
            H_G=None,
            H_D=1.0,
            H_K=None,
            source="guna"
        )

        assert source == "dimensional"  # Fell back to dimensional
        assert raw == 1.0

    def test_entropy_audit_includes_source(self):
        """Audit includes which entropy source was used."""
        config = DHAConfig(enabled=True, entropy_source=EntropySource.GUNA)
        engine = DHAEngine(config)

        signals = DHAInputs(C_s=0.8, H_G=0.5)
        _, result = engine.apply("test", signals)

        assert "entropy_source_used" in result.audit
        assert "normalized_H" in result.audit
        assert "raw_entropy" in result.audit


class TestSoftmaxValidity:
    """Test 4: Softmax Validity - weights sum to 1, no NaNs, bounded."""

    def test_softmax_sum_to_one(self):
        """Softmax weights must sum to 1.0."""
        from symbolu.dha.math import softmax3

        w1, w2, w3 = softmax3(1.0, 2.0, 3.0)
        total = w1 + w2 + w3

        assert abs(total - 1.0) < 1e-6

    def test_softmax_no_nans(self):
        """Softmax never produces NaN."""
        from symbolu.dha.math import softmax

        # Test edge cases
        test_cases = [
            (0.0, 0.0, 0.0),
            (1e10, 1e10, 1e10),
            (-1e10, -1e10, -1e10),
            (1e10, -1e10, 0.0),
        ]

        for logits in test_cases:
            result = softmax(logits)
            for w in result:
                assert not math.isnan(w), f"NaN for logits {logits}"
                assert not math.isinf(w), f"Inf for logits {logits}"

    def test_softmax_bounded(self):
        """Softmax outputs are in [0, 1]."""
        from symbolu.dha.math import softmax

        test_cases = [
            (0.0, 0.0, 0.0),
            (1.0, 2.0, 3.0),
            (-1.0, 0.0, 1.0),
            (10.0, 0.0, -10.0),
        ]

        for logits in test_cases:
            result = softmax(logits)
            for w in result:
                assert 0.0 <= w <= 1.0, f"Out of bounds for logits {logits}"

    def test_tone_weights_valid(self):
        """ToneWeights validates sum to 1."""
        # Valid weights
        tw = ToneWeights(sweet=0.5, jolt=0.3, metaphor=0.2)
        assert abs(tw.sweet + tw.jolt + tw.metaphor - 1.0) < 1e-6

        # Invalid weights should raise
        with pytest.raises(ValueError):
            ToneWeights(sweet=0.5, jolt=0.5, metaphor=0.5)  # Sum > 1

    def test_softmax_temperature(self):
        """Softmax temperature affects peakedness."""
        from symbolu.dha.math import softmax

        logits = (1.0, 2.0, 3.0)

        # Low temperature = more peaked
        low_temp = softmax(logits, temperature=0.5)
        # High temperature = more uniform
        high_temp = softmax(logits, temperature=2.0)

        # Low temp should have higher max
        assert max(low_temp) > max(high_temp)


class TestMissingSignalDefaults:
    """Test 5: Missing Signal Defaults - defaults used, audit marks missing."""

    def test_missing_coherence_uses_default(self):
        """Missing C_s uses default 0.5."""
        signals = DHAInputs.from_pipeline_signals(
            coherence_score=None,
            motion_magnitude=0.3,
        )

        assert signals.C_s == 0.5
        assert "C_s" in signals.missing_signals

    def test_missing_motion_uses_default(self):
        """Missing M uses default 0.0."""
        signals = DHAInputs.from_pipeline_signals(
            coherence_score=0.8,
            motion_magnitude=None,
        )

        assert signals.M == 0.0
        assert "M" in signals.missing_signals

    def test_missing_entropy_uses_default(self):
        """Missing all entropy sources marks H as missing."""
        signals = DHAInputs.from_pipeline_signals(
            coherence_score=0.8,
            guna_entropy=None,
            dimensional_entropy=None,
            kosha_entropy=None,
        )

        assert "H" in signals.missing_signals

    def test_missing_contradiction_uses_default(self):
        """Missing C_contr uses default 0.0."""
        signals = DHAInputs.from_pipeline_signals(
            coherence_score=0.8,
            contradiction=None,
        )

        assert signals.C_contr == 0.0
        assert "C_contr" in signals.missing_signals

    def test_missing_guna_distribution_uses_default(self):
        """Missing Guna distribution uses balanced default."""
        signals = DHAInputs.from_pipeline_signals(
            coherence_score=0.8,
            sattva=None,
            rajas=None,
            tamas=None,
        )

        # Should be approximately balanced
        assert abs(signals.s - 0.333333) < 0.001
        assert abs(signals.r - 0.333333) < 0.001
        assert abs(signals.t - 0.333334) < 0.001
        assert "guna_distribution" in signals.missing_signals

    def test_audit_marks_missing_signals(self):
        """Audit includes missing_signals flag."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs.from_pipeline_signals(
            coherence_score=None,
            motion_magnitude=None,
        )
        _, result = engine.apply("test", signals)

        assert "missing_signals" in result.audit
        assert "has_missing_signals" in result.audit
        assert result.audit["has_missing_signals"] is True


class TestBoundsEnforcement:
    """Test 6: Bounds Enforcement - I in [I_min, I_max], R in [0, 1]."""

    def test_intensity_within_bounds(self):
        """I is always within [I_min, I_max]."""
        config = DHAConfig(
            enabled=True,
            intensity=IntensityConfig(I_min=0.3, I_max=1.0),
        )
        engine = DHAEngine(config)

        # Test various inputs
        test_cases = [
            (0.0, 0.0, 0.0),  # Low coherence, motion, entropy
            (1.0, 1.0, 0.0),  # High coherence, motion, low entropy
            (0.0, 0.0, 1.0),  # Low coherence, motion, high entropy
            (1.0, 1.0, 1.0),  # All high
        ]

        for C_s, M, H_G in test_cases:
            signals = DHAInputs(C_s=C_s, M=M, H_G=H_G)
            _, result = engine.apply("test", signals)

            assert 0.3 <= result.I <= 1.0, f"I out of bounds for C_s={C_s}, M={M}, H_G={H_G}"

    def test_restraint_within_bounds(self):
        """R is always within [0, 1]."""
        # Test with various bias combinations
        test_configs = [
            RestraintConfig(risk_bias=0.0, escalation_bias=0.0),  # R = 1.0
            RestraintConfig(risk_bias=0.5, escalation_bias=0.0),  # R = 0.5
            RestraintConfig(risk_bias=0.5, escalation_bias=0.5),  # R = 0.0
            RestraintConfig(risk_bias=1.0, escalation_bias=1.0),  # R clamped to 0
        ]

        for restraint_cfg in test_configs:
            config = DHAConfig(enabled=True, restraint=restraint_cfg)
            engine = DHAEngine(config)

            signals = DHAInputs(C_s=0.5, M=0.3, H_G=0.4)
            _, result = engine.apply("test", signals)

            assert 0.0 <= result.R <= 1.0

    def test_intensity_bounds_configurable(self):
        """I_min and I_max are configurable."""
        config = DHAConfig(
            enabled=True,
            intensity=IntensityConfig(I_min=0.5, I_max=0.9),
        )
        engine = DHAEngine(config)

        signals = DHAInputs(C_s=0.0, M=0.0, H_G=1.0)  # Should minimize I
        _, result = engine.apply("test", signals)

        assert result.I >= 0.5  # Respects I_min

    def test_delivery_factor_non_negative(self):
        """D is always non-negative."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        # Test edge cases
        test_cases = [
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            (1.0, 1.0, 0.0),
            (0.5, 0.5, 0.5),
        ]

        for C_s, M, H_G in test_cases:
            signals = DHAInputs(C_s=C_s, M=M, H_G=H_G)
            _, result = engine.apply("test", signals)

            assert result.D >= 0.0


class TestAuditCompleteness:
    """Test 7: Audit Completeness - audit includes all required fields."""

    def test_audit_has_entropy_fields(self):
        """Audit includes entropy_source, raw entropy, normalized H."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(C_s=0.8, M=0.3, H_G=0.5)
        _, result = engine.apply("test", signals)

        assert "entropy_source_config" in result.audit
        assert "entropy_source_used" in result.audit
        assert "raw_entropy" in result.audit
        assert "normalized_H" in result.audit

    def test_audit_has_logits_and_weights(self):
        """Audit includes logits and weights."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(C_s=0.8, M=0.3, H_G=0.5, s=0.5, r=0.3, t=0.2)
        _, result = engine.apply("test", signals)

        assert "logits" in result.audit
        assert "l_sweet" in result.audit["logits"]
        assert "l_jolt" in result.audit["logits"]
        assert "l_meta" in result.audit["logits"]

        assert "weights" in result.audit
        assert "sweet" in result.audit["weights"]
        assert "jolt" in result.audit["weights"]
        assert "metaphor" in result.audit["weights"]

    def test_audit_has_scalar_values(self):
        """Audit includes I, R, D values."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(C_s=0.8, M=0.3, H_G=0.5)
        _, result = engine.apply("test", signals)

        assert "I" in result.audit
        assert "R" in result.audit
        assert "D" in result.audit

    def test_audit_has_tier_and_enabled(self):
        """Audit includes tier and enabled flag."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(C_s=0.8, tier=Tier.ENTERPRISE_TIER_1)
        _, result = engine.apply("test", signals)

        assert "tier" in result.audit
        assert result.audit["tier"] == "enterprise_tier_1"
        assert "enabled" in result.audit
        assert result.audit["enabled"] is True

    def test_audit_has_inputs(self):
        """Audit includes all input signals."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(
            C_s=0.8,
            M=0.3,
            H_G=0.5,
            H_D=0.6,
            H_K=0.4,
            C_contr=0.1,
            s=0.5,
            r=0.3,
            t=0.2,
        )
        _, result = engine.apply("test", signals)

        inputs = result.audit["inputs"]
        assert "C_s" in inputs
        assert "M" in inputs
        assert "H_G" in inputs
        assert "H_D" in inputs
        assert "H_K" in inputs
        assert "C_contr" in inputs
        assert "s" in inputs
        assert "r" in inputs
        assert "t" in inputs

    def test_audit_has_suppressed_flag(self):
        """Audit includes suppressed flag."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(C_s=0.8, M=0.3, H_G=0.5)
        _, result = engine.apply("test", signals)

        assert "suppressed" in result.audit


class TestTierConfiguration:
    """Test tier-specific configurations."""

    def test_tier_configs_are_different(self):
        """Different tiers produce different configs."""
        tier1 = DHAConfig.for_tier("enterprise_tier_1")
        tier2 = DHAConfig.for_tier("enterprise_tier_2")
        consumer = DHAConfig.for_tier("consumer")

        # All should be enabled
        assert tier1.enabled is True
        assert tier2.enabled is True
        assert consumer.enabled is True

        # Should have different intensity settings
        assert tier1.intensity.I_min != consumer.intensity.I_min

    def test_unknown_tier_returns_disabled(self):
        """Unknown tier returns disabled config."""
        config = DHAConfig.for_tier("unknown_tier")
        assert config.enabled is False

    def test_engine_from_tier(self):
        """DHAEngine.from_tier creates configured engine."""
        engine = DHAEngine.from_tier("enterprise_tier_1")
        assert engine.config.enabled is True


class TestFormulas:
    """Test core formula implementations."""

    def test_intensity_formula(self):
        """I = clip(alpha1*C_s + alpha2*M - alpha3*H, I_min, I_max)."""
        from symbolu.dha.math import compute_intensity

        # Test case: alpha1=0.4, alpha2=0.3, alpha3=0.2
        I = compute_intensity(
            C_s=1.0,
            M=1.0,
            H=0.0,
            alpha1=0.4,
            alpha2=0.3,
            alpha3=0.2,
            I_min=0.3,
            I_max=1.0,
        )

        # Expected: 0.4*1.0 + 0.3*1.0 - 0.2*0.0 = 0.7
        assert abs(I - 0.7) < 1e-6

    def test_restraint_formula(self):
        """R = clamp(1 - risk_bias - escalation_bias, 0, 1)."""
        from symbolu.dha.math import compute_restraint

        R = compute_restraint(risk_bias=0.2, escalation_bias=0.1)
        # Expected: 1 - 0.2 - 0.1 = 0.7
        assert abs(R - 0.7) < 1e-6

        # Test clamping
        R_clamped = compute_restraint(risk_bias=0.8, escalation_bias=0.8)
        assert R_clamped == 0.0  # Clamped to 0

    def test_delivery_factor_formula(self):
        """D = I × R (simplified)."""
        from symbolu.dha.math import compute_delivery_factor_simple

        D = compute_delivery_factor_simple(I=0.8, R=0.7)
        # Expected: 0.8 * 0.7 = 0.56
        assert abs(D - 0.56) < 1e-6

    def test_tone_logit_formulas(self):
        """Test tone logit computation."""
        from symbolu.dha.math import compute_tone_logits

        l_sweet, l_jolt, l_meta = compute_tone_logits(
            s=0.5, r=0.3, t=0.2,
            H=0.4, C_contr=0.1,
            k1=2.0, k2=1.5, k3=1.8, k4=2.2, k5=1.5, k6=1.0,
        )

        # l_sweet = k1*s - k2*t = 2.0*0.5 - 1.5*0.2 = 1.0 - 0.3 = 0.7
        assert abs(l_sweet - 0.7) < 1e-6

        # l_jolt = k3*r + k4*C_contr = 1.8*0.3 + 2.2*0.1 = 0.54 + 0.22 = 0.76
        assert abs(l_jolt - 0.76) < 1e-6

        # l_meta = k5*H + k6*r = 1.5*0.4 + 1.0*0.3 = 0.6 + 0.3 = 0.9
        assert abs(l_meta - 0.9) < 1e-6


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_apply_dha_function(self):
        """apply_dha convenience function works."""
        signals = DHAInputs(C_s=0.8, M=0.3, H_G=0.5)
        config = DHAConfig(enabled=True)

        _, result = apply_dha("test", signals, config)
        assert isinstance(result, DHAResult)

    def test_compute_dha_function(self):
        """compute_dha convenience function works."""
        result = compute_dha(
            coherence_score=0.8,
            motion_magnitude=0.3,
            guna_entropy=0.5,
            enabled=True,
        )

        assert isinstance(result, DHAResult)
        assert 0.0 <= result.D <= 1.0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_all_zeros_input(self):
        """Handle all-zero inputs gracefully."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(
            C_s=0.0,
            M=0.0,
            H_G=0.0,
            C_contr=0.0,
            s=0.333333,
            r=0.333333,
            t=0.333334,
        )
        _, result = engine.apply("test", signals)

        # Should not raise, should produce valid result
        assert isinstance(result, DHAResult)
        assert not math.isnan(result.D)
        assert not math.isinf(result.D)

    def test_all_ones_input(self):
        """Handle all-one inputs gracefully."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        signals = DHAInputs(
            C_s=1.0,
            M=1.0,
            H_G=1.0,
            C_contr=1.0,
            s=0.333333,
            r=0.333333,
            t=0.333334,
        )
        _, result = engine.apply("test", signals)

        assert isinstance(result, DHAResult)
        assert not math.isnan(result.D)

    def test_extreme_guna_distribution(self):
        """Handle extreme Guna distributions."""
        config = DHAConfig(enabled=True)
        engine = DHAEngine(config)

        # Pure Sattva
        signals = DHAInputs(C_s=0.5, s=1.0, r=0.0, t=0.0)
        _, result = engine.apply("test", signals)
        assert isinstance(result, DHAResult)

        # Pure Rajas
        signals = DHAInputs(C_s=0.5, s=0.0, r=1.0, t=0.0)
        _, result = engine.apply("test", signals)
        assert isinstance(result, DHAResult)

        # Pure Tamas
        signals = DHAInputs(C_s=0.5, s=0.0, r=0.0, t=1.0)
        _, result = engine.apply("test", signals)
        assert isinstance(result, DHAResult)

    def test_guna_normalization(self):
        """Guna distribution is normalized if not summing to 1."""
        # Create with values that don't sum to 1
        signals = DHAInputs(C_s=0.5, s=0.5, r=0.5, t=0.5)

        # Should be normalized
        total = signals.s + signals.r + signals.t
        assert abs(total - 1.0) < 1e-6
