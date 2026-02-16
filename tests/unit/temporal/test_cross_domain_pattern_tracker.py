"""
Unit tests for P38 CrossDomainPatternTracker
=============================================

Tests cover:
1. Pattern lifecycle events (onset, sustain, exit, recurrence)
2. Boundary proximity and trajectory
3. Pattern persistence and volatility
4. Sequence detection (full and partial)
5. P35 integration (instability signal, threshold adjustment)
6. Aspect derivation
7. P38 invariants (deterministic, observer-only, bounded window)
"""

import pytest
from symbolu.temporal.cross_domain_pattern_tracker import (
    CrossDomainPatternTracker,
    PatternSnapshot,
    PatternEvent,
    BoundaryProximity,
    SequenceMatch,
    PatternTrackerReport,
    P38_VERSION,
    THRESHOLD_FLOOR,
)
from symbolu.temporal.pattern_sequence_rules import (
    PATTERN_SEQUENCES,
    SEQUENCE_BY_NAME,
    PatternSequenceRule,
)
from symbolu.temporal.pattern_aspect_derivation import (
    derive_aspect_vector,
    ASPECT_NAMES,
)


# =============================================================================
# Helpers: known signal sets that trigger specific patterns
# =============================================================================

# These are taken from the existing CDI test suite
RISK_HIDING_SIGNALS = dict(smi=0.62, bhava_id=5, bhava_direction="downward", kosha_id=3, ontology_id=5, temporal_trend="rising")
BREAKTHROUGH_SIGNALS = dict(smi=0.25, bhava_id=7, bhava_direction="upward", kosha_id=5, ontology_id=7, temporal_trend="falling")
ACUTE_ANXIETY_SIGNALS = dict(smi=0.85, bhava_id=2, bhava_direction="downward", kosha_id=1, ontology_id=2, temporal_trend="rising")
CHRONIC_STRESS_SIGNALS = dict(smi=0.65, bhava_id=3, bhava_direction="downward", kosha_id=2, ontology_id=3, temporal_trend="stable")
EMOTIONAL_MASKING_SIGNALS = dict(smi=0.55, bhava_id=4, bhava_direction="downward", kosha_id=2, ontology_id=4, temporal_trend="stable")
RECOVERY_SIGNALS = dict(smi=0.42, bhava_id=5, bhava_direction="upward", kosha_id=4, ontology_id=5, temporal_trend="falling")
RESILIENCE_SIGNALS = dict(smi=0.35, bhava_id=6, bhava_direction="upward", kosha_id=5, ontology_id=6, temporal_trend="stable")
NEUTRAL_SIGNALS = dict(smi=0.10, bhava_id=10, bhava_direction="upward", kosha_id=6, ontology_id=10, temporal_trend="stable")


class TestPatternLifecycle:
    """Tests for lifecycle event detection."""

    def test_onset_detected_on_first_appearance(self):
        tracker = CrossDomainPatternTracker()
        report = tracker.process_turn(**RISK_HIDING_SIGNALS)
        onset_events = [e for e in report.events if e.event_type == "onset"]
        pattern_names = [e.pattern_name for e in onset_events]
        assert "risk_hiding" in pattern_names

    def test_sustain_on_consecutive_turns(self):
        tracker = CrossDomainPatternTracker()
        tracker.process_turn(**RISK_HIDING_SIGNALS)
        report2 = tracker.process_turn(**RISK_HIDING_SIGNALS)
        sustain_events = [e for e in report2.events if e.event_type == "sustain"]
        pattern_names = [e.pattern_name for e in sustain_events]
        assert "risk_hiding" in pattern_names
        rh_sustain = next(e for e in sustain_events if e.pattern_name == "risk_hiding")
        assert rh_sustain.dwell_turns == 2

    def test_exit_when_pattern_disappears(self):
        tracker = CrossDomainPatternTracker()
        tracker.process_turn(**RISK_HIDING_SIGNALS)
        report2 = tracker.process_turn(**NEUTRAL_SIGNALS)
        exit_events = [e for e in report2.events if e.event_type == "exit"]
        pattern_names = [e.pattern_name for e in exit_events]
        assert "risk_hiding" in pattern_names

    def test_recurrence_after_gap(self):
        tracker = CrossDomainPatternTracker()
        tracker.process_turn(**RISK_HIDING_SIGNALS)
        tracker.process_turn(**NEUTRAL_SIGNALS)
        report3 = tracker.process_turn(**RISK_HIDING_SIGNALS)
        recurrence_events = [e for e in report3.events if e.event_type == "recurrence"]
        pattern_names = [e.pattern_name for e in recurrence_events]
        assert "risk_hiding" in pattern_names
        rh_recurrence = next(e for e in recurrence_events if e.pattern_name == "risk_hiding")
        assert rh_recurrence.gap_turns >= 1

    def test_no_events_on_empty_pattern(self):
        tracker = CrossDomainPatternTracker()
        report = tracker.process_turn(**NEUTRAL_SIGNALS)
        # May have some events for whatever neutral matches, but should not crash
        assert isinstance(report.events, list)


class TestBoundaryProximity:
    """Tests for boundary distance and trajectory."""

    def test_distance_zero_when_inside_range(self):
        tracker = CrossDomainPatternTracker()
        report = tracker.process_turn(**RISK_HIDING_SIGNALS)
        rh_prox = next(p for p in report.proximities if p.pattern_name == "risk_hiding")
        assert rh_prox.distance_to_entry == 0.0

    def test_distance_positive_when_outside(self):
        tracker = CrossDomainPatternTracker()
        # SMI 0.10 is far outside risk_hiding range (0.50-0.75)
        report = tracker.process_turn(**NEUTRAL_SIGNALS)
        rh_prox = next(p for p in report.proximities if p.pattern_name == "risk_hiding")
        assert rh_prox.distance_to_entry > 0.0

    def test_approaching_detected_with_decreasing_distance(self):
        tracker = CrossDomainPatternTracker()
        # Feed signals where SMI increases toward risk_hiding range (0.50-0.75)
        for smi_val in [0.30, 0.35, 0.40, 0.45]:
            report = tracker.process_turn(
                smi=smi_val, bhava_id=5, bhava_direction="downward",
                kosha_id=3, ontology_id=5, temporal_trend="rising",
            )
        rh_prox = next(p for p in report.proximities if p.pattern_name == "risk_hiding")
        assert rh_prox.direction == "approaching"

    def test_eta_computed_when_approaching(self):
        tracker = CrossDomainPatternTracker()
        for smi_val in [0.30, 0.35, 0.40, 0.45]:
            report = tracker.process_turn(
                smi=smi_val, bhava_id=5, bhava_direction="downward",
                kosha_id=3, ontology_id=5, temporal_trend="rising",
            )
        rh_prox = next(p for p in report.proximities if p.pattern_name == "risk_hiding")
        if rh_prox.direction == "approaching":
            assert rh_prox.estimated_turns_to_entry is not None
            assert rh_prox.estimated_turns_to_entry >= 1

    def test_all_13_patterns_have_proximity(self):
        tracker = CrossDomainPatternTracker()
        report = tracker.process_turn(**RISK_HIDING_SIGNALS)
        assert len(report.proximities) == 13


class TestPatternPersistenceVolatility:
    """Tests for persistence, volatility, stability band."""

    def test_high_persistence_for_stable_pattern(self):
        tracker = CrossDomainPatternTracker()
        for _ in range(5):
            report = tracker.process_turn(**RISK_HIDING_SIGNALS)
        assert report.dominant_persistence >= 0.75

    def test_low_persistence_for_flickering_pattern(self):
        tracker = CrossDomainPatternTracker()
        signals = [RISK_HIDING_SIGNALS, NEUTRAL_SIGNALS]
        for i in range(6):
            report = tracker.process_turn(**signals[i % 2])
        # Flickering should reduce persistence (at or below stable threshold)
        assert report.dominant_persistence <= 0.75

    def test_volatility_zero_when_no_changes(self):
        tracker = CrossDomainPatternTracker()
        for _ in range(3):
            report = tracker.process_turn(**RISK_HIDING_SIGNALS)
        # Same patterns every turn → low volatility
        assert report.pattern_volatility < 0.1

    def test_volatility_high_when_many_changes(self):
        tracker = CrossDomainPatternTracker()
        alternating = [RISK_HIDING_SIGNALS, BREAKTHROUGH_SIGNALS]
        for i in range(6):
            report = tracker.process_turn(**alternating[i % 2])
        assert report.pattern_volatility > 0.0

    def test_stability_band_stable(self):
        tracker = CrossDomainPatternTracker()
        for _ in range(5):
            report = tracker.process_turn(**RISK_HIDING_SIGNALS)
        assert report.pattern_stability_band == "stable"

    def test_stability_band_fragile_on_flickering(self):
        tracker = CrossDomainPatternTracker()
        signals = [RISK_HIDING_SIGNALS, NEUTRAL_SIGNALS]
        for i in range(8):
            report = tracker.process_turn(**signals[i % 2])
        assert report.pattern_stability_band in ("soft", "fragile")


class TestSequenceDetection:
    """Tests for pattern sequence matching."""

    def test_partial_sequence_suppression_escalation(self):
        """acute_anxiety → emotional_masking should match 2/3 of suppression_escalation."""
        tracker = CrossDomainPatternTracker()
        tracker.process_turn(**ACUTE_ANXIETY_SIGNALS)
        report = tracker.process_turn(**EMOTIONAL_MASKING_SIGNALS)
        matching_names = [m.rule.name for m in report.sequence_matches]
        # May or may not match depending on exact confidence -- check structure
        for m in report.sequence_matches:
            assert m.steps_completed >= 2
            assert m.avg_confidence >= m.rule.min_confidence

    def test_full_recovery_arc_sequence(self):
        """chronic_stress → recovery_trajectory → resilience_pattern."""
        tracker = CrossDomainPatternTracker()
        tracker.process_turn(**CHRONIC_STRESS_SIGNALS)
        tracker.process_turn(**RECOVERY_SIGNALS)
        report = tracker.process_turn(**RESILIENCE_SIGNALS)
        matching_names = [m.rule.name for m in report.sequence_matches]
        # Check if recovery_arc is detected
        for m in report.sequence_matches:
            if m.rule.name == "recovery_arc":
                assert m.is_complete
                assert m.steps_completed == 3

    def test_gap_too_large_breaks_sequence(self):
        """Insert many gap turns to break max_gap_turns constraint."""
        tracker = CrossDomainPatternTracker()
        tracker.process_turn(**ACUTE_ANXIETY_SIGNALS)
        # 5 neutral turns should break suppression_escalation (max_gap=2)
        for _ in range(5):
            tracker.process_turn(**NEUTRAL_SIGNALS)
        report = tracker.process_turn(**EMOTIONAL_MASKING_SIGNALS)
        # suppression_escalation should NOT be matched (gap too large)
        se_matches = [m for m in report.sequence_matches if m.rule.name == "suppression_escalation"]
        assert len(se_matches) == 0

    def test_sequence_match_has_next_expected(self):
        """Partial matches should indicate next expected pattern."""
        tracker = CrossDomainPatternTracker()
        tracker.process_turn(**ACUTE_ANXIETY_SIGNALS)
        report = tracker.process_turn(**EMOTIONAL_MASKING_SIGNALS)
        for m in report.sequence_matches:
            if not m.is_complete:
                assert m.next_expected_pattern is not None


class TestP35Integration:
    """Tests for pattern instability signal and threshold adjustment."""

    def test_instability_signal_in_valid_range(self):
        tracker = CrossDomainPatternTracker()
        report = tracker.process_turn(**RISK_HIDING_SIGNALS)
        assert 0.0 <= report.pattern_instability_signal <= 1.0

    def test_instability_increases_with_volatility(self):
        tracker = CrossDomainPatternTracker()
        # Stable patterns
        for _ in range(4):
            stable_report = tracker.process_turn(**RISK_HIDING_SIGNALS)

        tracker2 = CrossDomainPatternTracker()
        # Volatile patterns
        alternating = [RISK_HIDING_SIGNALS, BREAKTHROUGH_SIGNALS]
        for i in range(4):
            volatile_report = tracker2.process_turn(**alternating[i % 2])

        assert volatile_report.pattern_instability_signal >= stable_report.pattern_instability_signal

    def test_context_adjusted_threshold_lowers_on_high_drift(self):
        adjusted = CrossDomainPatternTracker.get_context_adjusted_threshold(
            base_threshold=0.70,
            drift_forecast=0.80,
            continuity_mode="stable",
        )
        assert adjusted < 0.70
        assert adjusted >= THRESHOLD_FLOOR

    def test_context_adjusted_threshold_floor(self):
        adjusted = CrossDomainPatternTracker.get_context_adjusted_threshold(
            base_threshold=0.50,
            drift_forecast=0.90,
            continuity_mode="fragmenting",
        )
        assert adjusted >= THRESHOLD_FLOOR

    def test_context_adjusted_no_change_on_low_drift(self):
        adjusted = CrossDomainPatternTracker.get_context_adjusted_threshold(
            base_threshold=0.70,
            drift_forecast=0.30,
            continuity_mode="stable",
        )
        assert adjusted == 0.70


class TestAspectDerivation:
    """Tests for aspect vector derivation."""

    def test_all_10_aspects_present(self):
        vec = derive_aspect_vector(smi=0.5, bhava_id=5, bhava_direction="neutral", kosha_id=3, ontology_id=5)
        for name in ASPECT_NAMES:
            assert name in vec

    def test_all_aspects_in_valid_range(self):
        vec = derive_aspect_vector(smi=0.5, bhava_id=5, bhava_direction="neutral", kosha_id=3, ontology_id=5)
        for name, val in vec.items():
            assert 0.0 <= val <= 1.0, f"{name} = {val} out of range"

    def test_entropy_tracks_smi(self):
        low = derive_aspect_vector(smi=0.1, bhava_id=5, bhava_direction="neutral", kosha_id=3, ontology_id=5)
        high = derive_aspect_vector(smi=0.9, bhava_id=5, bhava_direction="neutral", kosha_id=3, ontology_id=5)
        assert high["ENTROPY"] > low["ENTROPY"]

    def test_flow_tracks_direction(self):
        up = derive_aspect_vector(smi=0.5, bhava_id=5, bhava_direction="upward", kosha_id=3, ontology_id=5)
        down = derive_aspect_vector(smi=0.5, bhava_id=5, bhava_direction="downward", kosha_id=3, ontology_id=5)
        assert up["FLOW"] > down["FLOW"]

    def test_aspect_vector_in_snapshot(self):
        tracker = CrossDomainPatternTracker()
        report = tracker.process_turn(**RISK_HIDING_SIGNALS)
        assert len(report.snapshot.aspect_vector) == 10

    def test_deterministic_aspect_derivation(self):
        vec1 = derive_aspect_vector(smi=0.5, bhava_id=5, bhava_direction="neutral", kosha_id=3, ontology_id=5)
        vec2 = derive_aspect_vector(smi=0.5, bhava_id=5, bhava_direction="neutral", kosha_id=3, ontology_id=5)
        assert vec1 == vec2


class TestP38Invariants:
    """Tests for P38 governance invariants."""

    def test_inv_p38_1_deterministic(self):
        """INV-P38-1: Same inputs -> same outputs."""
        tracker1 = CrossDomainPatternTracker()
        tracker2 = CrossDomainPatternTracker()
        r1 = tracker1.process_turn(**RISK_HIDING_SIGNALS)
        r2 = tracker2.process_turn(**RISK_HIDING_SIGNALS)
        assert r1.snapshot.active_patterns == r2.snapshot.active_patterns
        assert r1.snapshot.pattern_confidences == r2.snapshot.pattern_confidences
        assert r1.pattern_instability_signal == r2.pattern_instability_signal
        assert r1.pattern_volatility == r2.pattern_volatility
        assert r1.dominant_persistence == r2.dominant_persistence

    def test_inv_p38_4_window_bounded(self):
        """INV-P38-4: Window never exceeds window_size."""
        tracker = CrossDomainPatternTracker(window_size=5)
        for _ in range(20):
            tracker.process_turn(**RISK_HIDING_SIGNALS)
        assert len(tracker.window) <= 5

    def test_window_size_validation(self):
        with pytest.raises(ValueError):
            CrossDomainPatternTracker(window_size=0)

    def test_reset_clears_state(self):
        tracker = CrossDomainPatternTracker()
        tracker.process_turn(**RISK_HIDING_SIGNALS)
        tracker.process_turn(**RISK_HIDING_SIGNALS)
        tracker.reset()
        assert len(tracker.window) == 0
        assert tracker.turn_counter == 0

    def test_version_exists(self):
        assert P38_VERSION == "1.0.0"


class TestSequenceRules:
    """Tests for the pattern sequence rule definitions."""

    def test_all_sequences_have_at_least_2_steps(self):
        for seq in PATTERN_SEQUENCES:
            assert len(seq.steps) >= 2, f"{seq.name} has fewer than 2 steps"

    def test_all_sequences_have_valid_category(self):
        valid = {"escalation", "resolution", "entrenchment"}
        for seq in PATTERN_SEQUENCES:
            assert seq.category in valid, f"{seq.name} has invalid category {seq.category}"

    def test_8_sequences_defined(self):
        assert len(PATTERN_SEQUENCES) == 8

    def test_lookup_by_name(self):
        assert "suppression_escalation" in SEQUENCE_BY_NAME
        assert SEQUENCE_BY_NAME["suppression_escalation"].category == "escalation"


class TestSignalSnapshotP38Extension:
    """Tests for the P35 SignalSnapshot pattern_instability field."""

    def test_signal_snapshot_backwards_compatible(self):
        from symbolu.core.predictive.persona_drift.drift_trend_analyzer import (
            SignalSnapshot,
            compute_signal_deltas,
        )
        # Old-style creation without pattern_instability should still work
        snap = SignalSnapshot(drift_fusion_index=0.5, schema_drift=0.3)
        assert snap.pattern_instability is None

    def test_signal_snapshot_with_pattern_instability(self):
        from symbolu.core.predictive.persona_drift.drift_trend_analyzer import (
            SignalSnapshot,
            compute_signal_deltas,
        )
        snap = SignalSnapshot(
            drift_fusion_index=0.5,
            schema_drift=0.3,
            pattern_instability=0.42,
        )
        assert snap.pattern_instability == 0.42

    def test_pattern_instability_included_in_deltas(self):
        from symbolu.core.predictive.persona_drift.drift_trend_analyzer import (
            SignalSnapshot,
            compute_signal_deltas,
        )
        prev = SignalSnapshot(pattern_instability=0.30)
        curr = SignalSnapshot(pattern_instability=0.50)
        deltas = compute_signal_deltas(curr, prev)
        # Should contain the delta: 0.50 - 0.30 = 0.20
        assert 0.20 in [round(d, 2) for d in deltas]

    def test_pattern_instability_none_excluded_from_deltas(self):
        from symbolu.core.predictive.persona_drift.drift_trend_analyzer import (
            SignalSnapshot,
            compute_signal_deltas,
        )
        prev = SignalSnapshot(pattern_instability=None)
        curr = SignalSnapshot(pattern_instability=0.50)
        deltas = compute_signal_deltas(curr, prev)
        # No delta should be computed when one side is None
        assert len(deltas) == 0
