"""
Tests for DHA Engine v3.0
=========================

Pytest-style tests for the main DHA Engine orchestrator.
"""

import pytest
from symbolu.mechanical.dha.dha_engine import (
    DHAEngine,
    DHAInput,
    DHAOutput,
    run_dha,
    adapt_message
)
from symbolu.mechanical.dha.adaptation_rules import DeliveryProfile


class TestDHAEngine:
    """Tests for DHAEngine class."""

    def test_engine_initialization(self):
        """Test that DHAEngine initializes correctly."""
        engine = DHAEngine()

        assert engine.readiness_analyzer is not None
        assert engine.resistance_detector is not None
        assert engine.tone_selector is not None
        assert engine.delivery_modulator is not None
        assert engine.safety_filters is not None
        assert engine.stats["total_runs"] == 0

    def test_engine_run_basic(self):
        """Test basic pipeline execution."""
        engine = DHAEngine()

        result = engine.run(
            renderer_output={"text": "This is a test message."},
            metadata={
                "readiness_score": 0.7,
                "resistance_score": 0.2
            }
        )

        assert isinstance(result, DHAOutput)
        assert result.delivery_profile in [p.value for p in DeliveryProfile]
        assert result.adapted_message != ""
        assert result.original_message == "This is a test message."
        assert "process_time_ms" in result.diagnostics

    def test_engine_run_empty_text(self):
        """Test handling of empty text input."""
        engine = DHAEngine()

        result = engine.run(
            renderer_output={"text": ""},
            metadata={"readiness_score": 0.5}
        )

        assert result.adapted_message == ""
        assert "error" in result.diagnostics

    def test_engine_run_high_readiness_low_resistance(self):
        """Test SWEET_RESONANCE selection for optimal conditions."""
        engine = DHAEngine()

        result = engine.run(
            renderer_output={"text": "You need to change your approach."},
            metadata={
                "readiness_score": 0.9,
                "resistance_score": 0.1,
                "ego_state": "open"
            }
        )

        assert result.delivery_profile == DeliveryProfile.SWEET_RESONANCE.value

    def test_engine_run_high_resistance(self):
        """Test INVERSE_JOLT selection for high resistance."""
        engine = DHAEngine()

        result = engine.run(
            renderer_output={"text": "Consider this perspective."},
            metadata={
                "readiness_score": 0.5,
                "resistance_score": 0.9,
                "ego_state": "defensive"
            }
        )

        assert result.delivery_profile == DeliveryProfile.INVERSE_JOLT.value

    def test_engine_run_low_readiness(self):
        """Test SYMBOLIC_METAPHOR selection for low readiness."""
        engine = DHAEngine()

        result = engine.run(
            renderer_output={"text": "The truth is clear."},
            metadata={
                "readiness_score": 0.2,
                "resistance_score": 0.5,
                "ego_state": "guarded"
            }
        )

        assert result.delivery_profile == DeliveryProfile.SYMBOLIC_METAPHOR.value

    def test_engine_analyze_only(self):
        """Test analyze_only method."""
        engine = DHAEngine()

        analysis = engine.analyze_only({
            "readiness_score": 0.6,
            "resistance_score": 0.4,
            "emotional_entropy": 0.3
        })

        assert "readiness" in analysis
        assert "resistance" in analysis
        assert "recommended_profile" in analysis
        assert "confidence" in analysis
        assert "reasoning" in analysis

    def test_engine_statistics_tracking(self):
        """Test that statistics are tracked correctly."""
        engine = DHAEngine()

        # Run multiple times
        for _ in range(3):
            engine.run(
                renderer_output={"text": "Test message."},
                metadata={"readiness_score": 0.5, "resistance_score": 0.5}
            )

        stats = engine.get_stats()
        assert stats["total_runs"] == 3
        assert stats["avg_process_time_ms"] > 0

    def test_engine_stats_reset(self):
        """Test statistics reset."""
        engine = DHAEngine()

        engine.run(
            renderer_output={"text": "Test."},
            metadata={"readiness_score": 0.5}
        )

        engine.reset_stats()
        stats = engine.get_stats()
        assert stats["total_runs"] == 0

    def test_dha_output_to_dict(self):
        """Test DHAOutput serialization."""
        output = DHAOutput(
            delivery_profile="SWEET_RESONANCE",
            adapted_message="Adapted text",
            original_message="Original text",
            diagnostics={"test": True}
        )

        result = output.to_dict()

        assert result["delivery_profile"] == "SWEET_RESONANCE"
        assert result["adapted_message"] == "Adapted text"
        assert result["original_message"] == "Original text"
        assert result["diagnostics"]["test"] is True
        assert "timestamp" in result


class TestDHAInput:
    """Tests for DHAInput class."""

    def test_text_extraction_from_dict(self):
        """Test text extraction from dict renderer output."""
        dha_input = DHAInput(
            renderer_output={"text": "Test message"}
        )

        assert dha_input.text_to_adapt == "Test message"

    def test_text_extraction_fallback(self):
        """Test text extraction fallback to string."""
        dha_input = DHAInput(
            renderer_output="Plain string message"
        )

        assert "Plain string message" in dha_input.text_to_adapt

    def test_text_extraction_empty(self):
        """Test text extraction when no renderer output."""
        dha_input = DHAInput()

        assert dha_input.text_to_adapt == ""


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_run_dha_function(self):
        """Test run_dha convenience function."""
        result = run_dha(
            renderer_output={"text": "Test message"},
            metadata={
                "readiness_score": 0.7,
                "resistance_score": 0.2
            }
        )

        assert isinstance(result, DHAOutput)
        assert result.adapted_message != ""

    def test_adapt_message_function(self):
        """Test adapt_message convenience function."""
        adapted = adapt_message(
            text="Original message here.",
            readiness_score=0.8,
            resistance_score=0.2
        )

        assert isinstance(adapted, str)
        assert len(adapted) > 0

    def test_adapt_message_default_params(self):
        """Test adapt_message with default parameters."""
        adapted = adapt_message("Simple test message.")

        assert isinstance(adapted, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
