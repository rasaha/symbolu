"""
P10 Prosody Mapper Tests
========================

Tests for mapping coherence state and P10 acoustic parameters
to TTS provider settings.
"""

import pytest
from unittest.mock import Mock
from dataclasses import dataclass

from symbolu.voice.prosody.mapper import (
    AcousticRegime,
    ProsodyModulation,
    P10ProsodyConfig,
    P10ProsodyMapper,
)
from symbolu.voice.providers.base import TTSParams


# Mock coherence metrics
@dataclass
class MockCoherenceMetrics:
    """Mock coherence metrics for testing."""
    overall_coherence: float = 0.8
    prediction_reversal_risk: float = 0.2
    internal_consistency: float = 0.8
    goal_alignment: float = 0.8
    drift_direction: str = "stable"


@dataclass
class MockCoherenceState:
    """Mock coherence state for testing."""
    current_metrics: MockCoherenceMetrics = None

    def __post_init__(self):
        if self.current_metrics is None:
            self.current_metrics = MockCoherenceMetrics()


@dataclass
class MockSafetyContract:
    """Mock safety contract for testing."""
    eligible: bool = True
    violated_preconditions: list = None

    def __post_init__(self):
        if self.violated_preconditions is None:
            self.violated_preconditions = []


class TestAcousticRegime:
    """Tests for AcousticRegime enum."""

    def test_all_regimes_defined(self):
        """Verify all expected regimes are defined."""
        assert AcousticRegime.NEUTRAL is not None
        assert AcousticRegime.SOFT is not None
        assert AcousticRegime.FLAT is not None
        assert AcousticRegime.RESTRAINED is not None

    def test_regime_values(self):
        """Verify regime string values."""
        assert AcousticRegime.NEUTRAL.value == "neutral"
        assert AcousticRegime.SOFT.value == "soft"
        assert AcousticRegime.FLAT.value == "flat"
        assert AcousticRegime.RESTRAINED.value == "restrained"


class TestProsodyModulation:
    """Tests for ProsodyModulation dataclass."""

    def test_default_values(self):
        """Verify default modulation values are neutral."""
        mod = ProsodyModulation()

        assert mod.speed_modifier == 1.0
        assert mod.stability_modifier == 1.0
        assert mod.pitch_modifier == 0.0
        assert mod.style_modifier == 1.0
        assert mod.pause_multiplier == 1.0

    def test_custom_values(self):
        """Verify custom modulation values."""
        mod = ProsodyModulation(
            speed_modifier=0.8,
            stability_modifier=1.2,
            pitch_modifier=-2.0
        )

        assert mod.speed_modifier == 0.8
        assert mod.stability_modifier == 1.2
        assert mod.pitch_modifier == -2.0


class TestP10ProsodyConfig:
    """Tests for P10ProsodyConfig dataclass."""

    def test_default_config(self):
        """Verify default configuration values."""
        config = P10ProsodyConfig()

        assert config.default_voice_id == "sonic-english-male"
        assert config.default_speed == 1.0
        assert config.default_stability == 0.7
        assert config.low_coherence_threshold == 0.5
        assert config.high_uncertainty_threshold == 0.6

    def test_custom_config(self):
        """Verify custom configuration."""
        config = P10ProsodyConfig(
            default_voice_id="custom-voice",
            default_speed=0.9,
            low_coherence_threshold=0.4
        )

        assert config.default_voice_id == "custom-voice"
        assert config.default_speed == 0.9
        assert config.low_coherence_threshold == 0.4


class TestP10ProsodyMapper:
    """Tests for P10ProsodyMapper."""

    def test_compute_params_default(self):
        """Verify default parameter computation."""
        mapper = P10ProsodyMapper()
        params = mapper.compute_params()

        assert isinstance(params, TTSParams)
        assert params.speed == 1.0
        assert params.stability == 0.7

    def test_compute_params_with_voice_id(self):
        """Verify voice_id override."""
        mapper = P10ProsodyMapper()
        params = mapper.compute_params(voice_id="custom-voice")

        assert params.voice_id == "custom-voice"

    def test_compute_params_neutral_regime(self):
        """Verify NEUTRAL regime parameters."""
        mapper = P10ProsodyMapper()
        params = mapper.compute_params(p10_regime=AcousticRegime.NEUTRAL)

        assert params.speed == 1.0
        assert params.stability == 0.7

    def test_compute_params_soft_regime(self):
        """Verify SOFT regime parameters."""
        mapper = P10ProsodyMapper()
        params = mapper.compute_params(p10_regime=AcousticRegime.SOFT)

        assert params.speed < 1.0  # Slower
        assert params.stability > 0.7  # More stable
        assert params.pitch_shift < 0  # Lower pitch

    def test_compute_params_flat_regime(self):
        """Verify FLAT regime parameters."""
        mapper = P10ProsodyMapper()
        params = mapper.compute_params(p10_regime=AcousticRegime.FLAT)

        assert params.stability > 0.7  # More stable
        assert params.style < 0.5  # Less expressive

    def test_compute_params_restrained_regime(self):
        """Verify RESTRAINED regime parameters."""
        mapper = P10ProsodyMapper()
        params = mapper.compute_params(p10_regime=AcousticRegime.RESTRAINED)

        assert params.speed < 1.0  # Slower
        assert params.stability > 0.7  # More stable

    def test_low_coherence_modulation(self):
        """Verify low coherence modulates parameters."""
        mapper = P10ProsodyMapper()

        # Normal coherence
        normal_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(overall_coherence=0.8)
        )
        normal_params = mapper.compute_params(coherence_state=normal_state)

        # Low coherence
        low_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(overall_coherence=0.3)
        )
        low_params = mapper.compute_params(coherence_state=low_state)

        # Low coherence should be slower
        assert low_params.speed < normal_params.speed

    def test_high_uncertainty_modulation(self):
        """Verify high uncertainty modulates parameters."""
        mapper = P10ProsodyMapper()

        # Normal uncertainty
        normal_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(prediction_reversal_risk=0.2)
        )
        normal_params = mapper.compute_params(coherence_state=normal_state)

        # High uncertainty
        high_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(prediction_reversal_risk=0.8)
        )
        high_params = mapper.compute_params(coherence_state=high_state)

        # High uncertainty should be slower and less expressive
        assert high_params.speed <= normal_params.speed

    def test_degrading_coherence_modulation(self):
        """Verify degrading coherence modulates parameters."""
        mapper = P10ProsodyMapper()

        # Stable coherence
        stable_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(drift_direction="stable")
        )
        stable_params = mapper.compute_params(coherence_state=stable_state)

        # Degrading coherence
        degrading_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(drift_direction="degrading")
        )
        degrading_params = mapper.compute_params(coherence_state=degrading_state)

        # Degrading should be slower
        assert degrading_params.speed <= stable_params.speed

    def test_safety_concern_modulation(self):
        """Verify safety concerns modulate parameters."""
        mapper = P10ProsodyMapper()

        # Eligible contract
        eligible_contract = MockSafetyContract(eligible=True)
        eligible_params = mapper.compute_params(safety_contract=eligible_contract)

        # Not eligible contract
        blocked_contract = MockSafetyContract(eligible=False)
        blocked_params = mapper.compute_params(safety_contract=blocked_contract)

        # Safety concern should be slower and more stable
        assert blocked_params.speed <= eligible_params.speed

    def test_parameter_clamping(self):
        """Verify parameters are clamped to valid ranges."""
        mapper = P10ProsodyMapper(P10ProsodyConfig(
            min_speed=0.6,
            max_speed=1.4
        ))

        # Create extreme coherence state
        extreme_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(
                overall_coherence=0.1,
                prediction_reversal_risk=0.9,
                drift_direction="degrading"
            )
        )
        extreme_contract = MockSafetyContract(eligible=False)

        params = mapper.compute_params(
            coherence_state=extreme_state,
            safety_contract=extreme_contract
        )

        # Should be clamped
        assert params.speed >= 0.6
        assert params.speed <= 1.4
        assert params.stability >= 0.0
        assert params.stability <= 1.0

    def test_compute_ssml_adds_breaks(self):
        """Verify SSML adds breaks for uncertainty words."""
        mapper = P10ProsodyMapper()

        uncertain_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(prediction_reversal_risk=0.7)
        )

        text = "This might perhaps work"
        ssml = mapper.compute_ssml(text, coherence_state=uncertain_state)

        assert "break" in ssml

    def test_compute_ssml_low_coherence(self):
        """Verify SSML adds rate control for low coherence."""
        mapper = P10ProsodyMapper()

        low_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(overall_coherence=0.4)
        )

        text = "This is a test"
        ssml = mapper.compute_ssml(text, coherence_state=low_state)

        assert "prosody" in ssml
        assert 'rate="90%"' in ssml

    def test_get_regime_for_coherence_restrained(self):
        """Verify automatic regime selection for very low coherence."""
        mapper = P10ProsodyMapper()

        low_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(overall_coherence=0.3)
        )

        regime = mapper.get_regime_for_coherence(low_state)
        assert regime == AcousticRegime.RESTRAINED

    def test_get_regime_for_coherence_soft(self):
        """Verify automatic regime selection for high uncertainty."""
        mapper = P10ProsodyMapper()

        uncertain_state = MockCoherenceState(
            current_metrics=MockCoherenceMetrics(
                overall_coherence=0.7,
                prediction_reversal_risk=0.8
            )
        )

        regime = mapper.get_regime_for_coherence(uncertain_state)
        assert regime == AcousticRegime.SOFT

    def test_get_regime_for_coherence_neutral(self):
        """Verify automatic regime selection defaults to neutral."""
        mapper = P10ProsodyMapper()

        normal_state = MockCoherenceState()
        regime = mapper.get_regime_for_coherence(normal_state)
        assert regime == AcousticRegime.NEUTRAL

    def test_to_provider_params_cartesia(self):
        """Verify Cartesia-specific parameter conversion."""
        mapper = P10ProsodyMapper()
        params = TTSParams(
            voice_id="test-voice",
            speed=1.0,
            style=0.6
        )

        cartesia_params = mapper.to_provider_params(params, "cartesia")

        assert "voice_id" in cartesia_params
        assert "speed" in cartesia_params
        assert "emotion" in cartesia_params

    def test_to_provider_params_elevenlabs(self):
        """Verify ElevenLabs-specific parameter conversion."""
        mapper = P10ProsodyMapper()
        params = TTSParams(
            voice_id="test-voice",
            stability=0.8,
            style=0.5
        )

        el_params = mapper.to_provider_params(params, "elevenlabs")

        assert "voice_id" in el_params
        assert "stability" in el_params
        assert "style" in el_params

    def test_to_provider_params_deepgram(self):
        """Verify Deepgram-specific parameter conversion."""
        mapper = P10ProsodyMapper()
        params = TTSParams(voice_id="test-voice")

        dg_params = mapper.to_provider_params(params, "deepgram")

        assert "model" in dg_params

    def test_style_to_emotion_mapping(self):
        """Verify style value maps to appropriate emotion."""
        mapper = P10ProsodyMapper()

        # Low style = neutral
        assert mapper._style_to_emotion(0.2) == "neutral"

        # Medium style = friendly
        assert mapper._style_to_emotion(0.5) == "friendly"

        # High style = enthusiastic
        assert mapper._style_to_emotion(0.8) == "enthusiastic"
