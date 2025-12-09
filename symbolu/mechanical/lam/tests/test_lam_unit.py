"""
LAM v1.0 Unit Tests

Tests for the Long-Arc Mapper engine components:
1. Tracker update: After build_map(), temporal_tracker history grows by 1
2. Trajectory extraction: Synthetic rising SMI sequence -> trend="rising"
3. Pattern detection: Use fixed inputs to force CDI to detect specific patterns
4. Arc state detection: Various scenarios for tension, recovery, turning_point, steady
"""

import pytest

from symbolu.mechanical.lam import LAMEngine, LAMInput, LongArcMap
from symbolu.temporal.temporal_bhava_tracker import TemporalBhavaTracker
from symbolu.temporal.cross_domain_intelligence import CrossDomainIntelligence


class TestLAMEngineBasics:
    """Basic LAM engine tests."""

    def test_engine_initialization(self):
        """Test that engine initializes with default thresholds."""
        engine = LAMEngine()

        assert engine.tension_threshold == LAMEngine.DEFAULT_TENSION_THRESHOLD
        assert engine.pattern_confidence_threshold == LAMEngine.DEFAULT_PATTERN_CONFIDENCE_THRESHOLD

    def test_engine_custom_thresholds(self):
        """Test engine initialization with custom thresholds."""
        engine = LAMEngine(tension_threshold=0.8, pattern_confidence_threshold=0.7)

        assert engine.tension_threshold == 0.8
        assert engine.pattern_confidence_threshold == 0.7

    def test_get_statistics(self):
        """Test get_statistics returns correct configuration."""
        engine = LAMEngine(tension_threshold=0.5, pattern_confidence_threshold=0.6)
        stats = engine.get_statistics()

        assert stats["tension_threshold"] == 0.5
        assert stats["pattern_confidence_threshold"] == 0.6


class TestTrackerUpdate:
    """Tests for temporal tracker update after build_map()."""

    def test_tracker_history_grows_by_one(self):
        """After build_map(), temporal_tracker history should grow by 1."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Initial state
        initial_count = len(tracker.entries)
        assert initial_count == 0

        # Build map
        lam_input = LAMInput(
            text="I feel uncertain about my path",
            smi=0.5,
            bhava_id=4,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
            domain="psychology",
            long_arc_tension=0.3,
            temporal_tracker=tracker,
            cdi=cdi,
        )

        engine.build_map(lam_input)

        # Check history grew by 1
        assert len(tracker.entries) == initial_count + 1

    def test_tracker_history_grows_multiple_times(self):
        """Multiple build_map() calls should grow history accordingly."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Build maps 3 times
        for i in range(3):
            lam_input = LAMInput(
                text=f"Query {i}",
                smi=0.3 + i * 0.1,
                bhava_id=4 + i,
                bhava_direction="upward" if i > 0 else "neutral",
                kosha_id=3,
                ontology_id=5,
                domain="psychology",
                long_arc_tension=0.2,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            engine.build_map(lam_input)

        assert len(tracker.entries) == 3


class TestTrajectoryExtraction:
    """Tests for trajectory extraction and trend detection."""

    def test_rising_smi_sequence_gives_rising_trend(self):
        """Synthetic rising SMI sequence should produce trend='rising'."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Feed a rising SMI sequence
        smi_values = [0.2, 0.3, 0.4, 0.5, 0.6]

        for i, smi in enumerate(smi_values):
            lam_input = LAMInput(
                text=f"Rising query {i}",
                smi=smi,
                bhava_id=5,
                bhava_direction="upward",
                kosha_id=4,
                ontology_id=6,
                domain="psychology",
                long_arc_tension=0.4,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)

        # Last result should show rising trend
        assert result.trajectory_summary.get("trend") == "rising"

    def test_falling_smi_sequence_gives_falling_trend(self):
        """Synthetic falling SMI sequence should produce trend='falling'."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Feed a falling SMI sequence
        smi_values = [0.8, 0.7, 0.6, 0.5, 0.4]

        for i, smi in enumerate(smi_values):
            lam_input = LAMInput(
                text=f"Falling query {i}",
                smi=smi,
                bhava_id=5,
                bhava_direction="downward",
                kosha_id=4,
                ontology_id=6,
                domain="psychology",
                long_arc_tension=0.3,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)

        # Last result should show falling trend
        assert result.trajectory_summary.get("trend") == "falling"

    def test_stable_smi_sequence_gives_stable_trend(self):
        """Stable SMI sequence should produce trend='stable'."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Feed a stable SMI sequence
        smi_values = [0.5, 0.5, 0.5, 0.51, 0.49]

        for i, smi in enumerate(smi_values):
            lam_input = LAMInput(
                text=f"Stable query {i}",
                smi=smi,
                bhava_id=5,
                bhava_direction="neutral",
                kosha_id=4,
                ontology_id=6,
                domain="psychology",
                long_arc_tension=0.2,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)

        # Last result should show stable trend
        assert result.trajectory_summary.get("trend") == "stable"


class TestPatternDetection:
    """Tests for pattern detection via CrossDomainIntelligence."""

    def test_risk_hiding_pattern_detection(self):
        """Fixed inputs should trigger risk_hiding pattern detection."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine(pattern_confidence_threshold=0.60)

        # Inputs designed to trigger risk_hiding pattern
        # risk_hiding: smi_range=(0.5, 0.75), bhava_range=(3, 7), directions=["downward", "neutral"]
        lam_input = LAMInput(
            text="Everything is fine",
            smi=0.62,  # In risk_hiding range
            bhava_id=5,  # In risk_hiding range
            bhava_direction="downward",  # Matches risk_hiding
            kosha_id=3,  # Has weight in risk_hiding
            ontology_id=5,  # Has weight in risk_hiding
            domain="finance",
            long_arc_tension=0.4,
            temporal_tracker=tracker,
            cdi=cdi,
        )

        result = engine.build_map(lam_input)

        assert "risk_hiding" in result.active_patterns

    def test_breakthrough_insight_pattern_detection(self):
        """Fixed inputs should trigger breakthrough_insight pattern detection."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine(pattern_confidence_threshold=0.60)

        # Inputs designed to trigger breakthrough_insight pattern
        # breakthrough_insight: smi_range=(0.15, 0.35), bhava_range=(6, 9), directions=["upward"]
        lam_input = LAMInput(
            text="I finally understand what I need to do",
            smi=0.25,  # In breakthrough_insight range
            bhava_id=7,  # In breakthrough_insight range
            bhava_direction="upward",  # Matches breakthrough_insight
            kosha_id=5,  # Has weight in breakthrough_insight
            ontology_id=7,  # Has weight in breakthrough_insight
            domain="psychology",
            long_arc_tension=0.3,
            temporal_tracker=tracker,
            cdi=cdi,
        )

        result = engine.build_map(lam_input)

        assert "breakthrough_insight" in result.active_patterns

    def test_domain_transfers_generated_for_patterns(self):
        """Detected patterns should have domain-specific transfers."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine(pattern_confidence_threshold=0.60)

        # Trigger a pattern that will generate domain transfer
        lam_input = LAMInput(
            text="I finally understand",
            smi=0.25,
            bhava_id=7,
            bhava_direction="upward",
            kosha_id=5,
            ontology_id=7,
            domain="psychology",
            long_arc_tension=0.3,
            temporal_tracker=tracker,
            cdi=cdi,
        )

        result = engine.build_map(lam_input)

        # If breakthrough_insight is detected, it should have a domain transfer
        if "breakthrough_insight" in result.active_patterns:
            assert "breakthrough_insight" in result.domain_transfers
            assert "psychology" in result.domain_transfers["breakthrough_insight"].lower() or \
                   "therapeutic" in result.domain_transfers["breakthrough_insight"].lower()


class TestArcStateDetection:
    """Tests for arc state classification."""

    def test_tension_state_with_active_tension(self):
        """Active tension corridor should produce arc_state='tension'."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Feed high SMI values to trigger tension
        for i in range(3):
            lam_input = LAMInput(
                text=f"Tension query {i}",
                smi=0.75,  # High SMI triggers tension
                bhava_id=3,
                bhava_direction="downward",
                kosha_id=2,
                ontology_id=3,
                domain="psychology",
                long_arc_tension=0.7,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)

        assert result.arc_state == "tension"

    def test_recovery_state_after_peak(self):
        """Dropping from peak SMI should eventually produce arc_state='recovery'."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # First create a peak with high SMI
        peak_input = LAMInput(
            text="Peak tension",
            smi=0.8,
            bhava_id=3,
            bhava_direction="downward",
            kosha_id=2,
            ontology_id=3,
            domain="psychology",
            long_arc_tension=0.5,
            temporal_tracker=tracker,
            cdi=cdi,
        )
        engine.build_map(peak_input)

        # Then drop SMI to trigger recovery
        recovery_smi_values = [0.6, 0.5, 0.4]
        for i, smi in enumerate(recovery_smi_values):
            lam_input = LAMInput(
                text=f"Recovery query {i}",
                smi=smi,
                bhava_id=5,
                bhava_direction="upward",
                kosha_id=3,
                ontology_id=5,
                domain="psychology",
                long_arc_tension=0.3,
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)

        assert result.arc_state == "recovery"

    def test_turning_point_with_rising_trend(self):
        """Rising trend with high confidence should produce arc_state='turning_point'."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Create a clear rising trend with low tension
        smi_values = [0.3, 0.35, 0.4, 0.45, 0.5]
        for i, smi in enumerate(smi_values):
            lam_input = LAMInput(
                text=f"Rising query {i}",
                smi=smi,
                bhava_id=6,
                bhava_direction="upward",
                kosha_id=4,
                ontology_id=6,
                domain="psychology",
                long_arc_tension=0.2,  # Low tension
                temporal_tracker=tracker,
                cdi=cdi,
            )
            result = engine.build_map(lam_input)

        assert result.arc_state == "turning_point"

    def test_steady_state_default(self):
        """Single input with no special signals should produce arc_state='steady'."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        lam_input = LAMInput(
            text="Neutral query",
            smi=0.4,
            bhava_id=5,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
            domain="psychology",
            long_arc_tension=0.1,
            temporal_tracker=tracker,
            cdi=cdi,
        )

        result = engine.build_map(lam_input)

        assert result.arc_state == "steady"


class TestLongArcSignal:
    """Tests for long_arc_signal computation."""

    def test_signal_increases_with_tension(self):
        """Long arc signal should increase with high tension."""
        tracker1 = TemporalBhavaTracker(window_size=10)
        tracker2 = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Low tension scenario
        low_tension_input = LAMInput(
            text="Low tension",
            smi=0.3,
            bhava_id=5,
            bhava_direction="neutral",
            kosha_id=3,
            ontology_id=5,
            domain="psychology",
            long_arc_tension=0.1,
            temporal_tracker=tracker1,
            cdi=cdi,
        )
        low_result = engine.build_map(low_tension_input)

        # High tension scenario
        high_tension_input = LAMInput(
            text="High tension",
            smi=0.8,
            bhava_id=3,
            bhava_direction="downward",
            kosha_id=2,
            ontology_id=3,
            domain="psychology",
            long_arc_tension=0.9,
            temporal_tracker=tracker2,
            cdi=cdi,
        )
        high_result = engine.build_map(high_tension_input)

        assert high_result.long_arc_signal > low_result.long_arc_signal

    def test_signal_bounded_zero_to_one(self):
        """Long arc signal should always be in [0, 1]."""
        tracker = TemporalBhavaTracker(window_size=10)
        cdi = CrossDomainIntelligence()
        engine = LAMEngine()

        # Test with extreme values
        extreme_input = LAMInput(
            text="Extreme query",
            smi=1.0,
            bhava_id=10,
            bhava_direction="upward",
            kosha_id=5,
            ontology_id=9,
            domain="psychology",
            long_arc_tension=1.0,
            temporal_tracker=tracker,
            cdi=cdi,
        )

        result = engine.build_map(extreme_input)

        assert 0.0 <= result.long_arc_signal <= 1.0


class TestLongArcMapSerialization:
    """Tests for LongArcMap serialization."""

    def test_to_dict(self):
        """Test LongArcMap.to_dict() returns all fields."""
        lam_map = LongArcMap(
            trajectory_summary={"slope": 0.1, "trend": "rising", "confidence": 0.8},
            bhava_momentum={"upward_ratio": 0.7, "acceleration": 0.3, "strength": 0.5},
            tension_corridor={"length": 2.0, "intensity": 0.5, "active": 0.0},
            recovery_pattern={"recovering": 0.0, "progress": 0.0},
            active_patterns=["breakthrough_insight"],
            domain_transfers={"breakthrough_insight": "Therapeutic breakthrough"},
            arc_state="turning_point",
            long_arc_signal=0.45,
        )

        result = lam_map.to_dict()

        assert "trajectory_summary" in result
        assert "bhava_momentum" in result
        assert "tension_corridor" in result
        assert "recovery_pattern" in result
        assert "active_patterns" in result
        assert "domain_transfers" in result
        assert "arc_state" in result
        assert "long_arc_signal" in result
        assert result["arc_state"] == "turning_point"
        assert result["long_arc_signal"] == 0.45

    def test_repr(self):
        """Test LongArcMap.__repr__() is concise."""
        lam_map = LongArcMap(
            trajectory_summary={"trend": "rising"},
            active_patterns=["p1", "p2"],
            arc_state="turning_point",
            long_arc_signal=0.5,
        )

        repr_str = repr(lam_map)

        assert "arc_state=turning_point" in repr_str
        assert "trend=rising" in repr_str
        assert "patterns=2" in repr_str


class TestSingletonEngine:
    """Tests for singleton engine access."""

    def test_get_lam_engine_returns_same_instance(self):
        """get_lam_engine() should return the same instance."""
        from symbolu.mechanical.lam.lam_engine import get_lam_engine

        engine1 = get_lam_engine()
        engine2 = get_lam_engine()

        assert engine1 is engine2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
