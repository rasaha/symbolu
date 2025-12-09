"""
Tests for Resistance Detector v3.0
==================================

Pytest-style tests for the resistance detection logic.
"""

import pytest
from symbolu.mechanical.dha.resistance_detector import (
    ResistanceDetector,
    detect_resistance,
    get_resistance_level
)
from symbolu.mechanical.dha.adaptation_rules import Level


class TestResistanceDetector:
    """Tests for ResistanceDetector class."""

    def test_detector_initialization(self):
        """Test that ResistanceDetector initializes correctly."""
        detector = ResistanceDetector()

        assert detector.high_threshold == 0.7
        assert detector.medium_threshold == 0.4
        assert detector.entropy_weight == 0.3

    def test_custom_thresholds(self):
        """Test initialization with custom thresholds."""
        detector = ResistanceDetector(
            high_threshold=0.8,
            medium_threshold=0.5,
            entropy_weight=0.4
        )

        assert detector.high_threshold == 0.8
        assert detector.medium_threshold == 0.5
        assert detector.entropy_weight == 0.4

    def test_detect_returns_expected_structure(self):
        """Test that detect returns all expected fields."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.5,
            "emotional_entropy": 0.3
        })

        assert "resistance_level" in result
        assert "raw_resistance_score" in result
        assert "emotional_entropy" in result
        assert "composite_score" in result
        assert "detected_patterns" in result
        assert "ego_state" in result
        assert "diagnostics" in result

    def test_high_resistance_detection(self):
        """Test detection of high resistance."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.85
        })

        assert result["resistance_level"] == "HIGH"
        assert detector.get_level({"resistance_score": 0.85}) == Level.HIGH

    def test_medium_resistance_detection(self):
        """Test detection of medium resistance."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.5
        })

        assert result["resistance_level"] == "MEDIUM"
        assert detector.get_level({"resistance_score": 0.5}) == Level.MEDIUM

    def test_low_resistance_detection(self):
        """Test detection of low resistance."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.2
        })

        assert result["resistance_level"] == "LOW"
        assert detector.get_level({"resistance_score": 0.2}) == Level.LOW

    def test_emotional_entropy_increases_composite(self):
        """Test that emotional entropy increases composite score."""
        detector = ResistanceDetector()

        low_entropy = detector.detect({
            "resistance_score": 0.5,
            "emotional_entropy": 0.1
        })

        high_entropy = detector.detect({
            "resistance_score": 0.5,
            "emotional_entropy": 0.9
        })

        assert high_entropy["composite_score"] > low_entropy["composite_score"]

    def test_ego_state_affects_composite(self):
        """Test that ego state affects composite score."""
        detector = ResistanceDetector()

        open_state = detector.detect({
            "resistance_score": 0.5,
            "ego_state": "open"
        })

        defensive_state = detector.detect({
            "resistance_score": 0.5,
            "ego_state": "defensive"
        })

        assert defensive_state["composite_score"] > open_state["composite_score"]

    def test_is_high_resistance_method(self):
        """Test is_high_resistance convenience method."""
        detector = ResistanceDetector()

        assert detector.is_high_resistance({"resistance_score": 0.9}) is True
        assert detector.is_high_resistance({"resistance_score": 0.3}) is False

    def test_get_score_method(self):
        """Test get_score returns composite score."""
        detector = ResistanceDetector()

        score = detector.get_score({
            "resistance_score": 0.6,
            "emotional_entropy": 0.4
        })

        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_chaotic_defense_pattern_detection(self):
        """Test detection of CHAOTIC_DEFENSE pattern."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.7,
            "emotional_entropy": 0.8
        })

        assert "CHAOTIC_DEFENSE" in result["detected_patterns"]

    def test_rigid_defense_pattern_detection(self):
        """Test detection of RIGID_DEFENSE pattern."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.8,
            "emotional_entropy": 0.2
        })

        assert "RIGID_DEFENSE" in result["detected_patterns"]

    def test_ego_protection_pattern_detection(self):
        """Test detection of EGO_PROTECTION pattern."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.5,
            "ego_state": "defensive"
        })

        assert "EGO_PROTECTION" in result["detected_patterns"]

    def test_selective_acceptance_pattern_detection(self):
        """Test detection of SELECTIVE_ACCEPTANCE pattern."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.6,
            "folded_truths": ["truth1", "truth2", "truth3", "truth4"]
        })

        assert "SELECTIVE_ACCEPTANCE" in result["detected_patterns"]

    def test_default_values_when_missing(self):
        """Test that missing metadata uses defaults."""
        detector = ResistanceDetector()

        result = detector.detect({})

        # Should use default resistance_score of 0.3
        assert result["raw_resistance_score"] == 0.3
        # Should use default emotional_entropy of 0.3
        assert result["emotional_entropy"] == 0.3


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_detect_resistance_function(self):
        """Test detect_resistance convenience function."""
        result = detect_resistance({
            "resistance_score": 0.6,
            "emotional_entropy": 0.5
        })

        assert "resistance_level" in result
        assert "composite_score" in result

    def test_get_resistance_level_function(self):
        """Test get_resistance_level convenience function."""
        level = get_resistance_level({
            "resistance_score": 0.8
        })

        assert isinstance(level, Level)
        assert level == Level.HIGH


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_score_clamping_above_one(self):
        """Test that scores above 1.0 are handled."""
        detector = ResistanceDetector()

        # Even with extreme values, composite should be <= 1.0
        result = detector.detect({
            "resistance_score": 1.0,
            "emotional_entropy": 1.0,
            "ego_state": "hostile"
        })

        assert result["composite_score"] <= 1.0

    def test_score_clamping_below_zero(self):
        """Test that scores below 0.0 are handled."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.0,
            "emotional_entropy": 0.0,
            "ego_state": "open"
        })

        assert result["composite_score"] >= 0.0

    def test_invalid_ego_state_handling(self):
        """Test handling of unknown ego state."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.5,
            "ego_state": "unknown_state"
        })

        # Should still work, just no adjustment
        assert "resistance_level" in result

    def test_non_list_folded_truths(self):
        """Test handling of non-list folded_truths."""
        detector = ResistanceDetector()

        result = detector.detect({
            "resistance_score": 0.5,
            "folded_truths": "not a list"
        })

        # Should handle gracefully
        assert "resistance_level" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
