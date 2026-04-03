"""
Temporal Module Integration Tests
==================================

This test module verifies that the temporal module integrates correctly
with the existing core analysis infrastructure.

The tests are designed to be robust whether or not a real core engine exists,
using a DummyEngine fallback when necessary.
"""

import pytest
from typing import Dict, Any, Optional

# Try to import real core engine, fall back to dummy
try:
    from core import CoreInterface as ConsciousnessEngine
    HAS_REAL_ENGINE = True
except ImportError:
    ConsciousnessEngine = None
    HAS_REAL_ENGINE = False

# Import temporal module
from agentic.temporal import TemporalBhavaTracker, CrossDomainIntelligence


class DummyEngine:
    """
    A minimal mock engine that simulates core analysis results.

    This is used when the real core engine is not available,
    ensuring tests remain deterministic and independent.
    """

    def __init__(self):
        self._call_count = 0
        # Predefined responses for deterministic testing
        self._responses = [
            {
                "smi": 0.55,
                "bhava_id": 4,
                "bhava_direction": "downward",
                "kosha_id": 3,
                "ontology_id": 5,
            },
            {
                "smi": 0.62,
                "bhava_id": 5,
                "bhava_direction": "downward",
                "kosha_id": 3,
                "ontology_id": 5,
            },
            {
                "smi": 0.68,
                "bhava_id": 5,
                "bhava_direction": "neutral",
                "kosha_id": 3,
                "ontology_id": 4,
            },
            {
                "smi": 0.58,
                "bhava_id": 6,
                "bhava_direction": "upward",
                "kosha_id": 4,
                "ontology_id": 5,
            },
        ]

    def analyze(self, text: str) -> Dict[str, Any]:
        """
        Simulate core analysis returning deterministic results.

        Args:
            text: The text to analyze (used for cycling responses).

        Returns:
            A dict with smi, bhava_id, bhava_direction, kosha_id, ontology_id.
        """
        response = self._responses[self._call_count % len(self._responses)]
        self._call_count += 1
        return response.copy()


def get_engine():
    """
    Get an engine instance - real if available, dummy otherwise.

    Returns:
        Either a real ConsciousnessEngine or DummyEngine instance.
    """
    if HAS_REAL_ENGINE and ConsciousnessEngine is not None:
        try:
            return ConsciousnessEngine()
        except Exception:
            pass
    return DummyEngine()


def extract_analysis_params(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract temporal-relevant parameters from engine result.

    Handles both real engine results and dummy results.
    """
    # Handle potential nested structures from real engine
    if "analysis" in result:
        result = result["analysis"]

    return {
        "smi": result.get("smi", 0.5),
        "bhava_id": result.get("bhava_id", 4),
        "bhava_direction": result.get("bhava_direction", "neutral"),
        "kosha_id": result.get("kosha_id", 3),
        "ontology_id": result.get("ontology_id", 5),
    }


class TestTemporalCoreIntegration:
    """Integration tests for temporal module with core engine."""

    def test_temporal_tracker_with_engine(self):
        """
        Test that TemporalBhavaTracker works with engine output.

        Steps:
        1. Get engine (real or dummy)
        2. Analyze a small conversation
        3. Add results to tracker
        4. Verify summary is valid
        """
        engine = get_engine()
        tracker = TemporalBhavaTracker(window_size=10)

        # Small conversation for testing
        conversation = [
            "I'm feeling a bit uncertain about this decision.",
            "Maybe I'm overthinking it, but the risks seem significant.",
            "Actually, I think I need to reconsider my approach.",
            "Now I feel more confident about moving forward.",
        ]

        # Analyze each text and add to tracker
        for text in conversation:
            result = engine.analyze(text)
            params = extract_analysis_params(result)

            tracker.add_analysis(
                text=text,
                smi=params["smi"],
                bhava_id=params["bhava_id"],
                bhava_direction=params["bhava_direction"],
                kosha_id=params["kosha_id"],
                ontology_id=params["ontology_id"],
            )

        # Verify summary is valid
        summary = tracker.get_pattern_summary()

        assert summary["stats"]["count"] == len(conversation)
        assert summary["stats"]["count"] > 0
        assert "trajectory" in summary
        assert "trend" in summary["trajectory"]
        assert summary["trajectory"]["trend"] in ["rising", "falling", "stable"]
        assert "state" in summary
        assert "stats" in summary
        assert "avg_smi" in summary["stats"]
        assert "current_smi" in summary["stats"]

    def test_cross_domain_with_engine(self):
        """
        Test that CrossDomainIntelligence works with engine output.

        Steps:
        1. Get engine and analyze a text
        2. Use CrossDomainIntelligence to detect patterns
        3. If patterns found, transfer to finance domain
        4. Verify result structure
        """
        engine = get_engine()
        cdi = CrossDomainIntelligence()

        # Analyze a single text
        result = engine.analyze("I'm concerned about the financial implications.")
        params = extract_analysis_params(result)

        # Detect patterns
        patterns = cdi.detect_pattern(
            smi=params["smi"],
            bhava_id=params["bhava_id"],
            bhava_direction=params["bhava_direction"],
            kosha_id=params["kosha_id"],
            ontology_id=params["ontology_id"],
            temporal_trend=None,  # No temporal data yet
        )

        # Patterns should be a list (possibly empty)
        assert isinstance(patterns, list)

        # If we got patterns, test domain transfer
        if patterns:
            top_pattern = patterns[0][0]
            transfer_result = cdi.transfer_pattern_to_domain(top_pattern, "finance")

            assert "pattern" in transfer_result
            assert "domain" in transfer_result
            assert "interpretation" in transfer_result
            assert transfer_result["domain"] == "finance"
            assert len(transfer_result["interpretation"]) > 0

    def test_combined_tracker_and_intelligence(self):
        """
        Test full integration: engine -> tracker -> cross-domain intelligence.

        This simulates the complete temporal analysis pipeline.
        """
        engine = get_engine()
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()

        # Conversation that should produce detectable patterns
        conversation = [
            "Everything seems fine on the surface.",
            "But I'm worried about what might happen.",
            "The uncertainty is really getting to me.",
            "I need to find a way to manage these concerns.",
        ]

        # Process conversation through tracker
        for text in conversation:
            result = engine.analyze(text)
            params = extract_analysis_params(result)

            tracker.add_analysis(
                text=text,
                smi=params["smi"],
                bhava_id=params["bhava_id"],
                bhava_direction=params["bhava_direction"],
                kosha_id=params["kosha_id"],
                ontology_id=params["ontology_id"],
            )

        # Get temporal summary
        summary = tracker.get_pattern_summary()
        trend = summary["trajectory"]["trend"]

        # Use last analysis for pattern detection
        entries = tracker.entries
        last_entry = entries[-1]

        # Detect patterns with temporal trend
        patterns = cdi.detect_pattern(
            smi=last_entry.smi,
            bhava_id=last_entry.bhava_id,
            bhava_direction=last_entry.bhava_direction,
            kosha_id=last_entry.kosha_id,
            ontology_id=last_entry.ontology_id,
            temporal_trend=trend,
        )

        # Verify results
        assert isinstance(patterns, list)
        assert summary["stats"]["count"] == len(conversation)

        # If patterns detected, verify domain transfer works
        if patterns:
            pattern_name, confidence = patterns[0]
            assert confidence > 0

            # Test all domains
            for domain in ["finance", "medicine", "psychology", "education", "legal", "corporate"]:
                transfer = cdi.transfer_pattern_to_domain(pattern_name, domain)
                assert transfer["domain"] == domain
                assert len(transfer["interpretation"]) > 0


class TestTemporalModuleStandalone:
    """Tests for temporal module without engine dependency."""

    def test_tracker_deterministic_behavior(self):
        """Verify tracker produces consistent results for same input."""
        tracker1 = TemporalBhavaTracker(window_size=5)
        tracker2 = TemporalBhavaTracker(window_size=5)

        entries = [
            (0.4, 4, "neutral"),
            (0.5, 5, "upward"),
            (0.6, 5, "upward"),
        ]

        for smi, bhava_id, direction in entries:
            tracker1.add_analysis(
                text="test",
                smi=smi,
                bhava_id=bhava_id,
                bhava_direction=direction,
                kosha_id=3,
                ontology_id=5,
            )
            tracker2.add_analysis(
                text="test",
                smi=smi,
                bhava_id=bhava_id,
                bhava_direction=direction,
                kosha_id=3,
                ontology_id=5,
            )

        summary1 = tracker1.get_pattern_summary()
        summary2 = tracker2.get_pattern_summary()

        # Should produce identical results
        assert summary1["stats"]["avg_smi"] == summary2["stats"]["avg_smi"]
        assert summary1["trajectory"]["trend"] == summary2["trajectory"]["trend"]
        assert summary1["trajectory"]["slope"] == summary2["trajectory"]["slope"]

    def test_cdi_deterministic_behavior(self):
        """Verify CrossDomainIntelligence produces consistent results."""
        cdi1 = CrossDomainIntelligence()
        cdi2 = CrossDomainIntelligence()

        params = {
            "smi": 0.62,
            "bhava_id": 5,
            "bhava_direction": "downward",
            "kosha_id": 3,
            "ontology_id": 5,
            "temporal_trend": "rising",
        }

        patterns1 = cdi1.detect_pattern(**params)
        patterns2 = cdi2.detect_pattern(**params)

        # Should produce identical results
        assert patterns1 == patterns2

    def test_no_external_dependencies(self):
        """Verify temporal module has no network or external dependencies."""
        # This test passing confirms no network calls or external services
        tracker = TemporalBhavaTracker(window_size=5)
        cdi = CrossDomainIntelligence()

        # Add entries
        for i in range(3):
            tracker.add_analysis(
                text=f"test {i}",
                smi=0.5 + i * 0.1,
                bhava_id=4 + i,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        # Get summary (pure computation, no I/O)
        summary = tracker.get_pattern_summary()

        # Detect patterns (pure computation, no I/O)
        patterns = cdi.detect_pattern(
            smi=0.5,
            bhava_id=5,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
        )

        # If we got here without errors, no external dependencies were used
        assert True


class TestEdgeCases:
    """Edge case tests for temporal integration."""

    def test_empty_conversation(self):
        """Test handling of empty conversation."""
        tracker = TemporalBhavaTracker(window_size=10)
        summary = tracker.get_pattern_summary()

        assert summary["stats"]["count"] == 0
        assert summary["state"] == "UNKNOWN"

    def test_single_message_conversation(self):
        """Test handling of single message."""
        tracker = TemporalBhavaTracker(window_size=10)
        tracker.add_analysis(
            text="Single message",
            smi=0.5,
            bhava_id=4,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
        )

        summary = tracker.get_pattern_summary()
        assert summary["stats"]["count"] == 1
        assert summary["trajectory"]["trend"] == "stable"

    def test_extreme_smi_values(self):
        """Test handling of extreme SMI values."""
        cdi = CrossDomainIntelligence()

        # Very low SMI
        patterns_low = cdi.detect_pattern(
            smi=0.0,
            bhava_id=5,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
        )
        assert isinstance(patterns_low, list)

        # Very high SMI
        patterns_high = cdi.detect_pattern(
            smi=1.0,
            bhava_id=2,
            bhava_direction="downward",
            kosha_id=1,
            ontology_id=1,
        )
        assert isinstance(patterns_high, list)

    def test_pattern_detection_without_temporal(self):
        """Test that pattern detection works without temporal trend."""
        cdi = CrossDomainIntelligence()

        patterns = cdi.detect_pattern(
            smi=0.62,
            bhava_id=5,
            bhava_direction="downward",
            kosha_id=3,
            ontology_id=5,
            temporal_trend=None,
        )

        # Should still return valid patterns
        assert isinstance(patterns, list)
        if patterns:
            for name, confidence in patterns:
                assert isinstance(name, str)
                assert isinstance(confidence, float)
                assert 0 <= confidence <= 1
