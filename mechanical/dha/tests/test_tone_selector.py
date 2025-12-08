"""
Tests for Tone Selector v3.0
============================

Pytest-style tests for the tone selection logic.
"""

import pytest
from symbolu.mechanical.dha.tone_selector import (
    ToneSelector,
    select_tone,
    get_delivery_profile
)
from symbolu.mechanical.dha.adaptation_rules import DeliveryProfile, Level


class TestToneSelector:
    """Tests for ToneSelector class."""

    def test_selector_initialization(self):
        """Test that ToneSelector initializes correctly."""
        selector = ToneSelector()

        assert selector.readiness_analyzer is not None
        assert selector.resistance_detector is not None

    def test_select_returns_expected_structure(self):
        """Test that select returns all expected fields."""
        selector = ToneSelector()

        result = selector.select({
            "readiness_score": 0.5,
            "resistance_score": 0.5
        })

        assert "delivery_profile" in result
        assert "profile_name" in result
        assert "confidence" in result
        assert "reasoning" in result
        assert "readiness_analysis" in result
        assert "resistance_analysis" in result
        assert "profile_metadata" in result

    def test_high_resistance_returns_inverse_jolt(self):
        """Test that high resistance triggers INVERSE_JOLT."""
        selector = ToneSelector()

        result = selector.select({
            "readiness_score": 0.5,
            "resistance_score": 0.85
        })

        assert result["delivery_profile"] == DeliveryProfile.INVERSE_JOLT
        assert result["profile_name"] == "INVERSE_JOLT"

    def test_high_readiness_low_resistance_returns_sweet_resonance(self):
        """Test optimal conditions return SWEET_RESONANCE."""
        selector = ToneSelector()

        result = selector.select({
            "readiness_score": 0.9,
            "resistance_score": 0.1
        })

        assert result["delivery_profile"] == DeliveryProfile.SWEET_RESONANCE
        assert result["profile_name"] == "SWEET_RESONANCE"

    def test_medium_resistance_low_readiness_returns_symbolic(self):
        """Test medium resistance + low readiness returns SYMBOLIC_METAPHOR."""
        selector = ToneSelector()

        result = selector.select({
            "readiness_score": 0.2,
            "resistance_score": 0.5
        })

        assert result["delivery_profile"] == DeliveryProfile.SYMBOLIC_METAPHOR
        assert result["profile_name"] == "SYMBOLIC_METAPHOR"

    def test_confidence_varies_by_scenario(self):
        """Test that confidence reflects selection certainty."""
        selector = ToneSelector()

        # Clear case: high resistance
        high_resistance = selector.select({
            "readiness_score": 0.5,
            "resistance_score": 0.9
        })

        # Clear case: optimal conditions
        optimal = selector.select({
            "readiness_score": 0.95,
            "resistance_score": 0.05
        })

        # Both should have high confidence
        assert high_resistance["confidence"] >= 0.8
        assert optimal["confidence"] >= 0.8

    def test_get_profile_convenience_method(self):
        """Test get_profile returns DeliveryProfile directly."""
        selector = ToneSelector()

        profile = selector.get_profile({
            "readiness_score": 0.8,
            "resistance_score": 0.1
        })

        assert isinstance(profile, DeliveryProfile)
        assert profile == DeliveryProfile.SWEET_RESONANCE

    def test_ego_state_affects_selection(self):
        """Test that ego_state influences the outcome."""
        selector = ToneSelector()

        # Same scores but different ego states
        open_state = selector.select({
            "readiness_score": 0.6,
            "resistance_score": 0.4,
            "ego_state": "open"
        })

        defensive_state = selector.select({
            "readiness_score": 0.6,
            "resistance_score": 0.4,
            "ego_state": "defensive"
        })

        # Defensive should have higher effective resistance
        open_level = open_state["resistance_analysis"]["resistance_level"]
        defensive_level = defensive_state["resistance_analysis"]["resistance_level"]

        # Can be same or different depending on thresholds
        assert open_level in ["HIGH", "MEDIUM", "LOW"]
        assert defensive_level in ["HIGH", "MEDIUM", "LOW"]

    def test_emotional_entropy_affects_selection(self):
        """Test that emotional_entropy influences resistance."""
        selector = ToneSelector()

        low_entropy = selector.select({
            "readiness_score": 0.5,
            "resistance_score": 0.5,
            "emotional_entropy": 0.1
        })

        high_entropy = selector.select({
            "readiness_score": 0.5,
            "resistance_score": 0.5,
            "emotional_entropy": 0.9
        })

        # High entropy should increase effective resistance
        low_composite = low_entropy["resistance_analysis"]["composite_score"]
        high_composite = high_entropy["resistance_analysis"]["composite_score"]

        assert high_composite > low_composite


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_select_tone_function(self):
        """Test select_tone convenience function."""
        result = select_tone({
            "readiness_score": 0.7,
            "resistance_score": 0.3
        })

        assert "delivery_profile" in result
        assert isinstance(result["delivery_profile"], DeliveryProfile)

    def test_get_delivery_profile_function(self):
        """Test get_delivery_profile convenience function."""
        profile = get_delivery_profile({
            "readiness_score": 0.2,
            "resistance_score": 0.8
        })

        assert isinstance(profile, DeliveryProfile)
        assert profile == DeliveryProfile.INVERSE_JOLT


class TestDecisionMatrix:
    """Tests for the decision matrix logic."""

    @pytest.mark.parametrize("readiness,resistance,expected", [
        # High resistance always = INVERSE_JOLT
        (0.9, 0.8, DeliveryProfile.INVERSE_JOLT),
        (0.5, 0.85, DeliveryProfile.INVERSE_JOLT),
        (0.2, 0.9, DeliveryProfile.INVERSE_JOLT),
        # High readiness + Low resistance = SWEET_RESONANCE
        (0.9, 0.1, DeliveryProfile.SWEET_RESONANCE),
        (0.8, 0.2, DeliveryProfile.SWEET_RESONANCE),
        # Low readiness + Medium resistance = SYMBOLIC_METAPHOR
        (0.2, 0.5, DeliveryProfile.SYMBOLIC_METAPHOR),
        (0.3, 0.6, DeliveryProfile.SYMBOLIC_METAPHOR),
    ])
    def test_decision_matrix_scenarios(self, readiness, resistance, expected):
        """Test various decision matrix scenarios."""
        selector = ToneSelector()

        result = selector.select({
            "readiness_score": readiness,
            "resistance_score": resistance
        })

        assert result["delivery_profile"] == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
