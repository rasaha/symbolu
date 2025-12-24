"""
DHA Configuration Tests
=======================

Tests for DHA configuration dataclasses.
"""

import pytest
from symbolu.dha import (
    DHAConfig,
    EntropySource,
    ToneLogitConfig,
    IntensityConfig,
    RestraintConfig,
    NumericsConfig,
)


class TestDHAConfig:
    """Test main DHAConfig."""

    def test_disabled_by_default(self):
        """DHA is disabled by default."""
        config = DHAConfig()
        assert config.enabled is False

    def test_default_entropy_source(self):
        """Default entropy source is GUNA."""
        config = DHAConfig()
        assert config.entropy_source == EntropySource.GUNA

    def test_to_dict(self):
        """Config serializes to dict."""
        config = DHAConfig(enabled=True)
        d = config.to_dict()

        assert d["enabled"] is True
        assert d["entropy_source"] == "guna"
        assert "tone_logits" in d
        assert "intensity" in d
        assert "restraint" in d
        assert "numerics" in d

    def test_for_tier_enterprise_1(self):
        """for_tier creates enterprise tier 1 config."""
        config = DHAConfig.for_tier("enterprise_tier_1")

        assert config.enabled is True
        assert config.intensity.I_min == 0.5

    def test_for_tier_enterprise_2(self):
        """for_tier creates enterprise tier 2 config."""
        config = DHAConfig.for_tier("enterprise_tier_2")

        assert config.enabled is True
        assert config.intensity.I_min == 0.4

    def test_for_tier_consumer(self):
        """for_tier creates consumer config."""
        config = DHAConfig.for_tier("consumer")

        assert config.enabled is True
        assert config.intensity.I_min == 0.3

    def test_for_tier_unknown(self):
        """for_tier returns disabled for unknown tier."""
        config = DHAConfig.for_tier("unknown")

        assert config.enabled is False

    def test_disabled_class_method(self):
        """disabled() returns disabled config."""
        config = DHAConfig.disabled()

        assert config.enabled is False

    def test_frozen(self):
        """Config is frozen (immutable)."""
        config = DHAConfig()

        with pytest.raises(Exception):  # FrozenInstanceError
            config.enabled = True


class TestToneLogitConfig:
    """Test ToneLogitConfig."""

    def test_default_values(self):
        """Default coefficient values."""
        config = ToneLogitConfig()

        assert config.k1 == 2.0
        assert config.k2 == 1.5
        assert config.k3 == 1.8
        assert config.k4 == 2.2
        assert config.k5 == 1.5
        assert config.k6 == 1.0

    def test_bounds_validation(self):
        """Coefficients must be within bounds."""
        # Valid
        ToneLogitConfig(k1=0.5)

        # Invalid - below min
        with pytest.raises(ValueError):
            ToneLogitConfig(k1=0.05)

        # Invalid - above max
        with pytest.raises(ValueError):
            ToneLogitConfig(k1=10.0)

    def test_to_dict(self):
        """Serializes to dict."""
        config = ToneLogitConfig()
        d = config.to_dict()

        assert "k1" in d
        assert "k2" in d
        assert "k3" in d
        assert "k4" in d
        assert "k5" in d
        assert "k6" in d


class TestIntensityConfig:
    """Test IntensityConfig."""

    def test_default_values(self):
        """Default intensity values."""
        config = IntensityConfig()

        assert config.alpha1 == 0.4
        assert config.alpha2 == 0.3
        assert config.alpha3 == 0.2
        assert config.I_min == 0.3
        assert config.I_max == 1.0

    def test_alpha_bounds_validation(self):
        """Alpha values must be within bounds."""
        # Valid
        IntensityConfig(alpha1=0.5)

        # Invalid - below min
        with pytest.raises(ValueError):
            IntensityConfig(alpha1=-0.1)

        # Invalid - above max
        with pytest.raises(ValueError):
            IntensityConfig(alpha1=1.5)

    def test_intensity_bounds_validation(self):
        """I_min and I_max must be valid."""
        # Valid
        IntensityConfig(I_min=0.5, I_max=0.9)

        # Invalid - I_min out of range
        with pytest.raises(ValueError):
            IntensityConfig(I_min=-0.1)

        # Invalid - I_max out of range
        with pytest.raises(ValueError):
            IntensityConfig(I_max=1.5)

        # Invalid - I_min > I_max
        with pytest.raises(ValueError):
            IntensityConfig(I_min=0.8, I_max=0.5)

    def test_to_dict(self):
        """Serializes to dict."""
        config = IntensityConfig()
        d = config.to_dict()

        assert "alpha1" in d
        assert "alpha2" in d
        assert "alpha3" in d
        assert "I_min" in d
        assert "I_max" in d


class TestRestraintConfig:
    """Test RestraintConfig."""

    def test_default_values(self):
        """Default restraint values."""
        config = RestraintConfig()

        assert config.risk_bias == 0.0
        assert config.escalation_bias == 0.0

    def test_bias_bounds_validation(self):
        """Bias values must be within bounds."""
        # Valid
        RestraintConfig(risk_bias=0.5)

        # Invalid - below min
        with pytest.raises(ValueError):
            RestraintConfig(risk_bias=-0.1)

        # Invalid - above max
        with pytest.raises(ValueError):
            RestraintConfig(risk_bias=1.5)

    def test_total_bias_can_exceed_one(self):
        """Total bias can exceed 1 (clamps R to 0)."""
        # This is valid - results in R = 0
        config = RestraintConfig(risk_bias=0.8, escalation_bias=0.5)
        assert config.risk_bias + config.escalation_bias > 1.0

    def test_to_dict(self):
        """Serializes to dict."""
        config = RestraintConfig()
        d = config.to_dict()

        assert "risk_bias" in d
        assert "escalation_bias" in d


class TestNumericsConfig:
    """Test NumericsConfig."""

    def test_default_values(self):
        """Default numerics values."""
        config = NumericsConfig()

        assert config.epsilon == 1e-9
        assert config.float_precision == 6
        assert config.softmax_temperature == 1.0

    def test_epsilon_must_be_positive(self):
        """Epsilon must be positive."""
        with pytest.raises(ValueError):
            NumericsConfig(epsilon=0.0)

        with pytest.raises(ValueError):
            NumericsConfig(epsilon=-1e-9)

    def test_precision_must_be_non_negative(self):
        """Float precision must be non-negative."""
        # Valid
        NumericsConfig(float_precision=0)
        NumericsConfig(float_precision=10)

        # Invalid
        with pytest.raises(ValueError):
            NumericsConfig(float_precision=-1)

    def test_temperature_must_be_positive(self):
        """Softmax temperature must be positive."""
        with pytest.raises(ValueError):
            NumericsConfig(softmax_temperature=0.0)

        with pytest.raises(ValueError):
            NumericsConfig(softmax_temperature=-1.0)

    def test_to_dict(self):
        """Serializes to dict."""
        config = NumericsConfig()
        d = config.to_dict()

        assert "epsilon" in d
        assert "float_precision" in d
        assert "softmax_temperature" in d


class TestEntropySource:
    """Test EntropySource enum."""

    def test_values(self):
        """Enum values are correct."""
        assert EntropySource.GUNA.value == "guna"
        assert EntropySource.DIMENSIONAL.value == "dimensional"
        assert EntropySource.KOSHA.value == "kosha"

    def test_all_options(self):
        """All three options are available."""
        sources = list(EntropySource)
        assert len(sources) == 3
        assert EntropySource.GUNA in sources
        assert EntropySource.DIMENSIONAL in sources
        assert EntropySource.KOSHA in sources
