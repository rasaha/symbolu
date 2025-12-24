"""
Unit tests for TemporalBhavaTracker
====================================

Tests cover:
1. Basic tracking and statistics
2. Rising/falling/stable trend detection
3. Tension and recovery patterns
4. Window behavior (sliding window)
"""

import pytest
from symbolu.temporal.temporal_bhava_tracker import TemporalBhavaTracker, TemporalEntry


class TestBasicTracking:
    """Tests for basic tracking functionality."""

    def test_empty_tracker_summary(self):
        """Test that an empty tracker returns valid empty summary."""
        tracker = TemporalBhavaTracker(window_size=10)
        summary = tracker.get_pattern_summary()

        assert summary["state"] == "UNKNOWN"
        assert summary["stats"]["count"] == 0
        assert summary["stats"]["avg_smi"] == 0.0
        assert summary["trajectory"]["trend"] == "stable"
        assert summary["trajectory"]["confidence"] == 0.0

    def test_single_entry(self):
        """Test tracker with a single entry."""
        tracker = TemporalBhavaTracker(window_size=10)
        tracker.add_analysis(
            text="Test text",
            smi=0.5,
            bhava_id=4,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
        )

        summary = tracker.get_pattern_summary()
        assert summary["stats"]["count"] == 1
        assert summary["stats"]["avg_smi"] == 0.5
        assert summary["stats"]["current_smi"] == 0.5
        assert summary["trajectory"]["trend"] == "stable"

    def test_multiple_entries_stats(self):
        """Test that stats are computed correctly for multiple entries."""
        tracker = TemporalBhavaTracker(window_size=10)

        smi_values = [0.3, 0.4, 0.5, 0.6, 0.7]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()

        assert summary["stats"]["count"] == 5
        assert summary["stats"]["current_smi"] == 0.7
        # Average should be 0.5
        assert abs(summary["stats"]["avg_smi"] - 0.5) < 0.001

    def test_entry_structure(self):
        """Test that entries are created with correct structure."""
        tracker = TemporalBhavaTracker(window_size=10)
        tracker.add_analysis(
            text="Test",
            smi=0.45,
            bhava_id=3,
            bhava_direction="upward",
            kosha_id=2,
            ontology_id=4,
            timestamp=12345.0,
        )

        entries = tracker.entries
        assert len(entries) == 1
        entry = entries[0]

        assert entry.text == "Test"
        assert entry.smi == 0.45
        assert entry.bhava_id == 3
        assert entry.bhava_direction == "upward"
        assert entry.kosha_id == 2
        assert entry.ontology_id == 4
        assert entry.timestamp == 12345.0

    def test_reset(self):
        """Test that reset clears all entries."""
        tracker = TemporalBhavaTracker(window_size=10)
        tracker.add_analysis(
            text="Test",
            smi=0.5,
            bhava_id=4,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
        )

        tracker.reset()
        summary = tracker.get_pattern_summary()

        assert summary["stats"]["count"] == 0
        assert len(tracker.entries) == 0


class TestTrendDetection:
    """Tests for trajectory/trend detection."""

    def test_rising_trend(self):
        """Test detection of clearly rising SMI trend."""
        tracker = TemporalBhavaTracker(window_size=10)

        # Create a clearly rising sequence
        smi_values = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()

        assert summary["trajectory"]["trend"] == "rising"
        assert summary["trajectory"]["slope"] > 0
        assert summary["trajectory"]["confidence"] > 0.3

    def test_falling_trend(self):
        """Test detection of clearly falling SMI trend."""
        tracker = TemporalBhavaTracker(window_size=10)

        # Create a clearly falling sequence
        smi_values = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()

        assert summary["trajectory"]["trend"] == "falling"
        assert summary["trajectory"]["slope"] < 0
        assert summary["trajectory"]["confidence"] > 0.3

    def test_stable_trend(self):
        """Test detection of stable/flat SMI trend."""
        tracker = TemporalBhavaTracker(window_size=10)

        # Create a flat sequence with minimal variation
        smi_values = [0.5, 0.51, 0.49, 0.5, 0.50, 0.51, 0.49, 0.5]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()

        assert summary["trajectory"]["trend"] == "stable"
        assert abs(summary["trajectory"]["slope"]) < 0.05


class TestTensionAndRecovery:
    """Tests for tension corridor and recovery pattern detection."""

    def test_tension_corridor_detection(self):
        """Test detection of high-SMI tension corridor."""
        tracker = TemporalBhavaTracker(window_size=10)

        # Create a high-SMI streak
        smi_values = [0.3, 0.4, 0.65, 0.70, 0.75, 0.72, 0.68]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=3,
                bhava_direction="downward",
                kosha_id=2,
                ontology_id=4,
            )

        summary = tracker.get_pattern_summary()

        # Should detect tension corridor
        assert summary["tension"]["max_corridor_length"] >= 4
        assert summary["tension"]["current"] is True
        assert summary["tension"]["corridor_length"] >= 1

    def test_recovery_detection(self):
        """Test detection of recovery from high tension."""
        tracker = TemporalBhavaTracker(window_size=10)

        # Create a pattern: high SMI followed by lower values
        smi_values = [0.4, 0.6, 0.75, 0.8, 0.65, 0.5, 0.4]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=4 + (i % 2),  # Vary bhava
                bhava_direction="upward" if i > 3 else "downward",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()

        # Should detect recovery
        assert summary["recovery"]["active"] is True
        assert summary["recovery"]["progress"] > 0

    def test_tense_state_classification(self):
        """Test that TENSE state is classified during sustained high SMI."""
        tracker = TemporalBhavaTracker(window_size=10)

        # Create sustained high SMI
        smi_values = [0.65, 0.70, 0.72, 0.75, 0.73]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=3,
                bhava_direction="downward",
                kosha_id=2,
                ontology_id=4,
            )

        summary = tracker.get_pattern_summary()
        assert summary["state"] == "TENSE"

    def test_recovering_state_classification(self):
        """Test that RECOVERING state is classified during recovery."""
        tracker = TemporalBhavaTracker(window_size=10)

        # Create recovery pattern
        smi_values = [0.5, 0.7, 0.8, 0.75, 0.6, 0.5, 0.45]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=5,
                bhava_direction="upward" if i > 3 else "downward",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()
        # Either RECOVERING or FALLING would be acceptable here
        assert summary["state"] in ["RECOVERING", "FALLING"]


class TestWindowBehavior:
    """Tests for sliding window behavior."""

    def test_window_size_enforcement(self):
        """Test that window_size is enforced."""
        tracker = TemporalBhavaTracker(window_size=3)

        # Add 5 entries
        for i in range(5):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=0.1 * (i + 1),  # 0.1, 0.2, 0.3, 0.4, 0.5
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        # Only last 3 should remain
        entries = tracker.entries
        assert len(entries) == 3

        # Verify these are the last 3 entries (use approx for float comparison)
        assert entries[0].smi == pytest.approx(0.3)
        assert entries[1].smi == pytest.approx(0.4)
        assert entries[2].smi == pytest.approx(0.5)

    def test_window_stats_only_use_window(self):
        """Test that stats are computed only from window entries."""
        tracker = TemporalBhavaTracker(window_size=3)

        # Add 5 entries with increasing SMI
        for i in range(5):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=0.1 * (i + 1),
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()

        # Count should be 3 (window size)
        assert summary["stats"]["count"] == 3

        # Average should be (0.3 + 0.4 + 0.5) / 3 = 0.4
        assert abs(summary["stats"]["avg_smi"] - 0.4) < 0.001

        # Current should be 0.5
        assert summary["stats"]["current_smi"] == 0.5

    def test_window_property(self):
        """Test that window_size property returns correct value."""
        tracker = TemporalBhavaTracker(window_size=7)
        assert tracker.window_size == 7

    def test_invalid_window_size(self):
        """Test that invalid window_size raises error."""
        with pytest.raises(ValueError):
            TemporalBhavaTracker(window_size=0)

        with pytest.raises(ValueError):
            TemporalBhavaTracker(window_size=-1)


class TestMomentum:
    """Tests for momentum calculation."""

    def test_upward_momentum(self):
        """Test detection of upward momentum."""
        tracker = TemporalBhavaTracker(window_size=10)

        smi_values = [0.3, 0.4, 0.5, 0.6, 0.7]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()
        assert summary["momentum"]["direction"] == "upward"
        assert summary["momentum"]["strength"] > 0

    def test_downward_momentum(self):
        """Test detection of downward momentum."""
        tracker = TemporalBhavaTracker(window_size=10)

        smi_values = [0.7, 0.6, 0.5, 0.4, 0.3]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()
        assert summary["momentum"]["direction"] == "downward"
        assert summary["momentum"]["strength"] > 0


class TestStateClassification:
    """Tests for overall state classification."""

    def test_stable_state(self):
        """Test STABLE state classification."""
        tracker = TemporalBhavaTracker(window_size=10)

        # Low variance, mid-range SMI
        smi_values = [0.4, 0.42, 0.38, 0.41, 0.39, 0.40]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=5,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()
        assert summary["state"] == "STABLE"

    def test_volatile_state(self):
        """Test VOLATILE state classification with high variance."""
        tracker = TemporalBhavaTracker(window_size=10)

        # High variance SMI values
        smi_values = [0.2, 0.8, 0.3, 0.7, 0.25, 0.75]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=4,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()
        assert summary["state"] == "VOLATILE"

    def test_rising_state(self):
        """Test RISING state classification."""
        tracker = TemporalBhavaTracker(window_size=10)

        # Clear rising trend with low variance
        smi_values = [0.2, 0.25, 0.3, 0.35, 0.4, 0.45]
        for i, smi in enumerate(smi_values):
            tracker.add_analysis(
                text=f"Text {i}",
                smi=smi,
                bhava_id=5,
                bhava_direction="neutral",
                kosha_id=3,
                ontology_id=5,
            )

        summary = tracker.get_pattern_summary()
        assert summary["state"] == "RISING"
