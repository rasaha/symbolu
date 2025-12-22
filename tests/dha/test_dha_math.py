"""
DHA Math Utilities Tests
========================

Tests for the deterministic math functions in symbolu.dha.math.
"""

import pytest
import math
from symbolu.dha.math import (
    LN_3,
    LN_5,
    LN_10,
    EPSILON,
    clip,
    clamp,
    softmax,
    softmax3,
    normalize_entropy_guna,
    normalize_entropy_dimensional,
    normalize_entropy_kosha,
    get_normalized_entropy,
    compute_tone_logits,
    compute_intensity,
    compute_restraint,
    compute_delivery_factor,
    compute_delivery_factor_simple,
    round_for_audit,
    round_dict_for_audit,
)


class TestConstants:
    """Test constant values."""

    def test_ln_3(self):
        """LN_3 is correct."""
        assert abs(LN_3 - math.log(3)) < 1e-10

    def test_ln_5(self):
        """LN_5 is correct."""
        assert abs(LN_5 - math.log(5)) < 1e-10

    def test_ln_10(self):
        """LN_10 is correct."""
        assert abs(LN_10 - math.log(10)) < 1e-10

    def test_epsilon(self):
        """EPSILON is small but positive."""
        assert EPSILON > 0
        assert EPSILON < 1e-6


class TestClipClamp:
    """Test clip and clamp functions."""

    def test_clip_within_bounds(self):
        """clip returns value when within bounds."""
        assert clip(0.5, 0.0, 1.0) == 0.5

    def test_clip_below_min(self):
        """clip returns min when below."""
        assert clip(-0.5, 0.0, 1.0) == 0.0

    def test_clip_above_max(self):
        """clip returns max when above."""
        assert clip(1.5, 0.0, 1.0) == 1.0

    def test_clip_invalid_bounds(self):
        """clip raises on invalid bounds."""
        with pytest.raises(ValueError):
            clip(0.5, 1.0, 0.0)  # min > max

    def test_clamp_default_bounds(self):
        """clamp uses [0, 1] by default."""
        assert clamp(0.5) == 0.5
        assert clamp(-0.5) == 0.0
        assert clamp(1.5) == 1.0


class TestSoftmax:
    """Test softmax functions."""

    def test_softmax_sum_to_one(self):
        """softmax outputs sum to 1."""
        result = softmax((1.0, 2.0, 3.0))
        assert abs(sum(result) - 1.0) < 1e-6

    def test_softmax_positive(self):
        """softmax outputs are positive."""
        result = softmax((1.0, 2.0, 3.0))
        for w in result:
            assert w > 0

    def test_softmax_monotonic(self):
        """Higher logit produces higher probability."""
        result = softmax((1.0, 2.0, 3.0))
        assert result[0] < result[1] < result[2]

    def test_softmax_empty(self):
        """softmax handles empty input."""
        result = softmax(())
        assert result == ()

    def test_softmax_single(self):
        """softmax with single element returns 1.0."""
        result = softmax((5.0,))
        assert len(result) == 1
        assert abs(result[0] - 1.0) < 1e-6

    def test_softmax_equal_logits(self):
        """Equal logits produce uniform distribution."""
        result = softmax((1.0, 1.0, 1.0))
        for w in result:
            assert abs(w - 1/3) < 1e-6

    def test_softmax_large_logits(self):
        """softmax handles large logits without overflow."""
        result = softmax((100.0, 200.0, 300.0))
        assert not any(math.isnan(w) for w in result)
        assert not any(math.isinf(w) for w in result)
        assert abs(sum(result) - 1.0) < 1e-6

    def test_softmax_negative_logits(self):
        """softmax handles negative logits."""
        result = softmax((-1.0, -2.0, -3.0))
        assert abs(sum(result) - 1.0) < 1e-6
        # Order should be reversed
        assert result[0] > result[1] > result[2]

    def test_softmax3_convenience(self):
        """softmax3 works for 3 elements."""
        w1, w2, w3 = softmax3(1.0, 2.0, 3.0)
        assert abs(w1 + w2 + w3 - 1.0) < 1e-6

    def test_softmax_temperature_low(self):
        """Low temperature makes distribution more peaked."""
        low_temp = softmax((1.0, 2.0, 3.0), temperature=0.1)
        high_temp = softmax((1.0, 2.0, 3.0), temperature=10.0)

        # Low temperature should have higher max
        assert max(low_temp) > max(high_temp)

    def test_softmax_temperature_invalid(self):
        """Temperature must be positive."""
        with pytest.raises(ValueError):
            softmax((1.0, 2.0, 3.0), temperature=0.0)
        with pytest.raises(ValueError):
            softmax((1.0, 2.0, 3.0), temperature=-1.0)


class TestEntropyNormalization:
    """Test entropy normalization functions."""

    def test_normalize_entropy_guna(self):
        """Guna entropy normalized by ln(3)."""
        # Maximum raw guna entropy is ln(3) for uniform distribution
        H_max = normalize_entropy_guna(LN_3)
        assert abs(H_max - 1.0) < 1e-6

        H_half = normalize_entropy_guna(LN_3 / 2)
        assert abs(H_half - 0.5) < 1e-6

    def test_normalize_entropy_dimensional(self):
        """Dimensional entropy normalized by ln(10)."""
        H_max = normalize_entropy_dimensional(LN_10)
        assert abs(H_max - 1.0) < 1e-6

    def test_normalize_entropy_kosha(self):
        """Kosha entropy normalized by ln(5)."""
        H_max = normalize_entropy_kosha(LN_5)
        assert abs(H_max - 1.0) < 1e-6

    def test_normalize_entropy_none(self):
        """None entropy returns 0.0."""
        assert normalize_entropy_guna(None) == 0.0
        assert normalize_entropy_dimensional(None) == 0.0
        assert normalize_entropy_kosha(None) == 0.0

    def test_normalize_entropy_clamped(self):
        """Normalized entropy is clamped to [0, 1]."""
        # Value that would exceed 1.0
        assert normalize_entropy_guna(LN_3 * 2) == 1.0
        # Negative value
        assert normalize_entropy_guna(-1.0) == 0.0

    def test_get_normalized_entropy_guna(self):
        """get_normalized_entropy with guna source."""
        H, source, raw = get_normalized_entropy(
            H_G=0.5, H_D=None, H_K=None, source="guna"
        )
        assert source == "guna"
        assert raw == 0.5
        assert H == normalize_entropy_guna(0.5)

    def test_get_normalized_entropy_fallback(self):
        """get_normalized_entropy falls back to available."""
        # Request guna, but only dimensional available
        H, source, raw = get_normalized_entropy(
            H_G=None, H_D=1.0, H_K=None, source="guna"
        )
        assert source == "dimensional"
        assert raw == 1.0

    def test_get_normalized_entropy_none(self):
        """get_normalized_entropy returns 0 when none available."""
        H, source, raw = get_normalized_entropy(
            H_G=None, H_D=None, H_K=None, source="guna"
        )
        assert source == "none"
        assert H == 0.0
        assert raw == 0.0


class TestToneLogits:
    """Test tone logit computation."""

    def test_compute_tone_logits_basic(self):
        """Basic tone logit computation."""
        l_sweet, l_jolt, l_meta = compute_tone_logits(
            s=0.5, r=0.3, t=0.2,
            H=0.0, C_contr=0.0,
            k1=1.0, k2=1.0, k3=1.0, k4=1.0, k5=1.0, k6=1.0,
        )

        # l_sweet = k1*s - k2*t = 1.0*0.5 - 1.0*0.2 = 0.3
        assert abs(l_sweet - 0.3) < 1e-6

        # l_jolt = k3*r + k4*C_contr = 1.0*0.3 + 1.0*0.0 = 0.3
        assert abs(l_jolt - 0.3) < 1e-6

        # l_meta = k5*H + k6*r = 1.0*0.0 + 1.0*0.3 = 0.3
        assert abs(l_meta - 0.3) < 1e-6

    def test_compute_tone_logits_entropy_effect(self):
        """Entropy increases metaphor logit."""
        l1_sweet, l1_jolt, l1_meta = compute_tone_logits(
            s=0.5, r=0.3, t=0.2,
            H=0.0, C_contr=0.0,
            k1=1.0, k2=1.0, k3=1.0, k4=1.0, k5=1.0, k6=1.0,
        )

        l2_sweet, l2_jolt, l2_meta = compute_tone_logits(
            s=0.5, r=0.3, t=0.2,
            H=1.0, C_contr=0.0,  # High entropy
            k1=1.0, k2=1.0, k3=1.0, k4=1.0, k5=1.0, k6=1.0,
        )

        # Higher entropy should increase l_meta
        assert l2_meta > l1_meta

    def test_compute_tone_logits_contradiction_effect(self):
        """Contradiction increases jolt logit."""
        l1_sweet, l1_jolt, l1_meta = compute_tone_logits(
            s=0.5, r=0.3, t=0.2,
            H=0.0, C_contr=0.0,
            k1=1.0, k2=1.0, k3=1.0, k4=1.0, k5=1.0, k6=1.0,
        )

        l2_sweet, l2_jolt, l2_meta = compute_tone_logits(
            s=0.5, r=0.3, t=0.2,
            H=0.0, C_contr=1.0,  # High contradiction
            k1=1.0, k2=1.0, k3=1.0, k4=1.0, k5=1.0, k6=1.0,
        )

        # Higher contradiction should increase l_jolt
        assert l2_jolt > l1_jolt


class TestIntensityRestraint:
    """Test intensity and restraint computation."""

    def test_compute_intensity_basic(self):
        """Basic intensity computation."""
        I = compute_intensity(
            C_s=1.0, M=1.0, H=0.0,
            alpha1=0.4, alpha2=0.3, alpha3=0.2,
            I_min=0.3, I_max=1.0,
        )
        # I = 0.4*1.0 + 0.3*1.0 - 0.2*0.0 = 0.7
        assert abs(I - 0.7) < 1e-6

    def test_compute_intensity_entropy_reduces(self):
        """Entropy reduces intensity."""
        I_low_H = compute_intensity(
            C_s=1.0, M=1.0, H=0.0,
            alpha1=0.4, alpha2=0.3, alpha3=0.2,
            I_min=0.3, I_max=1.0,
        )

        I_high_H = compute_intensity(
            C_s=1.0, M=1.0, H=1.0,
            alpha1=0.4, alpha2=0.3, alpha3=0.2,
            I_min=0.3, I_max=1.0,
        )

        assert I_high_H < I_low_H

    def test_compute_intensity_clipped(self):
        """Intensity is clipped to [I_min, I_max]."""
        # Should be clipped to I_min
        I_low = compute_intensity(
            C_s=0.0, M=0.0, H=1.0,
            alpha1=0.4, alpha2=0.3, alpha3=0.2,
            I_min=0.3, I_max=1.0,
        )
        assert I_low == 0.3

    def test_compute_restraint_basic(self):
        """Basic restraint computation."""
        R = compute_restraint(risk_bias=0.2, escalation_bias=0.1)
        # R = 1 - 0.2 - 0.1 = 0.7
        assert abs(R - 0.7) < 1e-6

    def test_compute_restraint_clamped(self):
        """Restraint is clamped to [0, 1]."""
        # Large biases should clamp to 0
        R = compute_restraint(risk_bias=0.8, escalation_bias=0.8)
        assert R == 0.0

        # No biases should give 1
        R = compute_restraint(risk_bias=0.0, escalation_bias=0.0)
        assert R == 1.0


class TestDeliveryFactor:
    """Test delivery factor computation."""

    def test_compute_delivery_factor_basic(self):
        """Basic delivery factor with tone weights."""
        D = compute_delivery_factor(
            tone_weights=(0.5, 0.3, 0.2),
            I=0.8,
            R=0.7,
        )
        # D = T * I * R where T = max(weights) = 0.5
        expected = 0.5 * 0.8 * 0.7
        assert abs(D - expected) < 1e-6

    def test_compute_delivery_factor_simple(self):
        """Simple delivery factor (T=1)."""
        D = compute_delivery_factor_simple(I=0.8, R=0.7)
        # D = I * R = 0.8 * 0.7 = 0.56
        assert abs(D - 0.56) < 1e-6


class TestRounding:
    """Test rounding functions."""

    def test_round_for_audit(self):
        """round_for_audit rounds to specified precision."""
        assert round_for_audit(0.123456789, 6) == 0.123457
        assert round_for_audit(0.123456789, 3) == 0.123

    def test_round_dict_for_audit(self):
        """round_dict_for_audit rounds all floats in dict."""
        d = {
            "a": 0.123456789,
            "b": 1.987654321,
            "c": {
                "nested": 0.111111111,
            },
            "d": "string",
            "e": [0.222222222, 0.333333333],
        }

        result = round_dict_for_audit(d, 3)

        assert result["a"] == 0.123
        assert result["b"] == 1.988
        assert result["c"]["nested"] == 0.111
        assert result["d"] == "string"
        assert result["e"][0] == 0.222
        assert result["e"][1] == 0.333
