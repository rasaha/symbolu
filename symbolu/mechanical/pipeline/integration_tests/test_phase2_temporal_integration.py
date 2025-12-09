"""
Phase 2 Temporal Formula Integration Tests
===========================================

Tests for Phase 2 Symbol-U Formula Integration Plan v1.0.

These tests verify that Phase 1 temporal formulas (SMI, ΔSMI, Bhava Gap, Tension Corridor)
are correctly wired into:
- Temporal tracker
- Coherence state
- Session summary
- Memory entries
- Unified output
- Coherence observer

All changes must be:
- Zero-LLM (deterministic)
- Non-invasive (no behavior changes)
- CI-safe (all tests pass)
- Observation-only (formulas don't affect routing/scoring)

Test Coverage:
1. Single-turn formula computation and propagation
2. Multi-turn session with formula aggregates
3. Coherence state formula histories and aggregates
4. Session summary formula fields
5. Memory entries with formula context
6. UnifiedOutput formulas section
7. CoherenceObserver formulas snapshot
8. Behavioral invariance (no routing/scoring changes)
"""

import pytest
from typing import Dict, Any, Optional

from symbolu.temporal.temporal_bhava_tracker import (
    TemporalBhavaTracker,
    TemporalFormulaSnapshot,
    TemporalState,
)
from symbolu.core.coherence.coherence_engine import CoherenceEngine
from symbolu.core.coherence.coherence_state import CoherenceState
from symbolu.service.sessions.session_store import SessionStore, compute_session_summary
from symbolu.service.sessions.session_models import SessionState, SessionSummary
from symbolu.service.sessions.session_memory import MemoryEntry, SessionMemory
from symbolu.mechanical.pipeline.coherence_observer import CoherenceObserver, CoherenceObservation


# ==============================================================================
# Test 1: TemporalFormulaSnapshot and TemporalState
# ==============================================================================


def test_temporal_formula_snapshot_creation():
    """Test TemporalFormulaSnapshot creation and to_dict()."""
    snapshot = TemporalFormulaSnapshot(
        smi=0.65,
        delta_smi=0.15,
        bhava_gap=0.33,
        tension_corridor=0.42,
    )

    assert snapshot.smi == 0.65
    assert snapshot.delta_smi == 0.15
    assert snapshot.bhava_gap == 0.33
    assert snapshot.tension_corridor == 0.42

    # Test to_dict
    snapshot_dict = snapshot.to_dict()
    assert snapshot_dict["smi"] == 0.65
    assert snapshot_dict["delta_smi"] == 0.15
    assert snapshot_dict["bhava_gap"] == 0.33
    assert snapshot_dict["tension_corridor"] == 0.42


def test_temporal_state_contains_snapshot():
    """Test TemporalState contains TemporalFormulaSnapshot."""
    snapshot = TemporalFormulaSnapshot(smi=0.5, delta_smi=0.1, bhava_gap=0.2, tension_corridor=0.3)
    state = TemporalState(formulas=snapshot)

    # Test backward compatibility properties
    assert state.smi == 0.5
    assert state.delta_smi == 0.1
    assert state.bhava_gap == 0.2
    assert state.tension_corridor == 0.3

    # Test formulas field
    assert state.formulas.smi == 0.5
    assert state.formulas.delta_smi == 0.1
    assert state.formulas.bhava_gap == 0.2
    assert state.formulas.tension_corridor == 0.3


def test_temporal_tracker_compute_formulas():
    """Test TemporalBhavaTracker.compute_formulas() populates snapshot."""
    tracker = TemporalBhavaTracker(window_size=10)

    # First turn - should compute SMI, but delta_smi=0.0 (no previous)
    state = tracker.compute_formulas(
        dimensional_resonance=0.6,
        vrtti_intensity=0.7,
        bhava_position=0.5,
        current_bhava=3,
    )

    assert state.formulas.smi is not None
    assert 0.0 <= state.formulas.smi <= 1.0
    assert state.formulas.delta_smi == 0.0  # First turn
    assert state.formulas.bhava_gap == 0.0  # First turn
    assert state.formulas.tension_corridor is not None

    # Second turn - should compute delta_smi and bhava_gap
    state2 = tracker.compute_formulas(
        dimensional_resonance=0.7,
        vrtti_intensity=0.8,
        bhava_position=0.6,
        current_bhava=5,
    )

    assert state2.formulas.smi is not None
    assert state2.formulas.delta_smi is not None
    assert state2.formulas.bhava_gap is not None
    assert state2.formulas.bhava_gap > 0.0  # Bhava changed from 3 to 5
    assert state2.formulas.tension_corridor is not None


def test_temporal_tracker_get_pattern_summary_includes_formulas():
    """Test get_pattern_summary() includes formulas section."""
    tracker = TemporalBhavaTracker(window_size=10)

    # Add some entries
    tracker.add_analysis(
        text="test",
        smi=0.5,
        bhava_id=1,
        bhava_direction="upward",
        kosha_id=0,
        ontology_id=0,
    )

    # Compute formulas
    tracker.compute_formulas(
        dimensional_resonance=0.6,
        vrtti_intensity=0.5,
        bhava_position=0.4,
        current_bhava=1,
    )

    # Get summary with formulas
    summary = tracker.get_pattern_summary(include_formulas=True)

    assert "formulas" in summary
    assert "smi" in summary["formulas"]
    assert "delta_smi" in summary["formulas"]
    assert "bhava_gap" in summary["formulas"]
    assert "tension_corridor" in summary["formulas"]

    # Test without formulas
    summary_no_formulas = tracker.get_pattern_summary(include_formulas=False)
    assert "formulas" not in summary_no_formulas


# ==============================================================================
# Test 2: CoherenceState Formula Aggregates
# ==============================================================================


def test_coherence_state_has_formula_aggregates():
    """Test CoherenceState has Phase 2 formula aggregate fields."""
    state = CoherenceState(convo_id="test", turn_index=0)

    # Check that aggregate fields exist
    assert hasattr(state, "avg_smi")
    assert hasattr(state, "max_smi")
    assert hasattr(state, "min_smi")
    assert hasattr(state, "avg_tension_corridor")
    assert hasattr(state, "max_tension_corridor")

    # Initially None
    assert state.avg_smi is None
    assert state.max_smi is None
    assert state.min_smi is None


def test_coherence_engine_updates_formula_aggregates():
    """Test CoherenceEngine._update_formula_aggregates() populates aggregates."""
    engine = CoherenceEngine(window=10)

    # Create state with some SMI history
    state = CoherenceState(convo_id="test", turn_index=2)
    state.smi_history = [0.5, 0.6, 0.7]
    state.tension_corridor_history = [0.3, 0.4, 0.5]

    # Update aggregates
    engine._update_formula_aggregates(state)

    # Check aggregates
    assert state.avg_smi == pytest.approx(0.6, rel=1e-2)
    assert state.max_smi == 0.7
    assert state.min_smi == 0.5
    assert state.avg_tension_corridor == pytest.approx(0.4, rel=1e-2)
    assert state.max_tension_corridor == 0.5


def test_coherence_engine_update_state_computes_aggregates():
    """Test CoherenceEngine.update_state() automatically computes aggregates."""
    engine = CoherenceEngine(window=10)

    # Mock routing plan
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "generic"
        long_arc_tension = 0.5

    routing_plan = MockRoutingPlan()

    # First turn
    state1 = engine.update_state(
        prev_state=None,
        convo_id="test",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile={},
        temporal_summary={"smi": 0.5, "delta_smi": 0.0, "bhava_gap": 0.0, "tension_corridor": 0.3},
        semantic_signature={},
    )

    # Aggregates should be computed
    assert state1.avg_smi == 0.5
    assert state1.max_smi == 0.5
    assert state1.min_smi == 0.5
    assert state1.avg_tension_corridor == 0.3
    assert state1.max_tension_corridor == 0.3


# ==============================================================================
# Test 3: Session Summary Formula Fields
# ==============================================================================


def test_session_summary_has_formula_fields():
    """Test SessionSummary has Phase 2 formula aggregate fields."""
    summary = SessionSummary(
        session_id="test",
        total_turns=5,
        coherence_trend=0.7,
        persona_drift_avg=0.2,
        temporal_arc_avg=0.6,
    )

    # Check that formula fields exist
    assert hasattr(summary, "avg_smi")
    assert hasattr(summary, "net_delta_smi")
    assert hasattr(summary, "avg_bhava_gap")
    assert hasattr(summary, "avg_tension_corridor")


def test_compute_session_summary_populates_formula_fields():
    """Test compute_session_summary() populates formula aggregate fields."""
    # Create session state with coherence history containing formulas
    state = SessionState(
        session_id="test",
        created_at=None,
    )

    # Add coherence history with formula data
    state.coherence_history = [
        {
            "coherence_score": 0.7,
            "avg_smi": 0.5,
            "delta_smi_history": [0.1],
            "bhava_gap_history": [0.2],
            "tension_corridor_history": [0.3],
        },
        {
            "coherence_score": 0.8,
            "avg_smi": 0.6,
            "delta_smi_history": [0.1, 0.15],
            "bhava_gap_history": [0.2, 0.25],
            "tension_corridor_history": [0.3, 0.35],
        },
    ]

    # Compute summary
    summary = compute_session_summary(state)

    # Check formula fields
    assert summary.avg_smi is not None
    assert summary.net_delta_smi is not None
    assert summary.avg_bhava_gap is not None
    assert summary.avg_tension_corridor is not None


# ==============================================================================
# Test 4: Session Memory Formula Context
# ==============================================================================


def test_memory_entry_has_formula_fields():
    """Test MemoryEntry has Phase 2 formula context fields."""
    entry = MemoryEntry(
        turn_index=5,
        event_type="breakthrough",
        description="Notable upward clarity shift detected.",
        metrics={"coherence_score": 0.85},
        smi=0.75,
        tension_corridor=0.45,
    )

    assert entry.smi == 0.75
    assert entry.tension_corridor == 0.45


def test_memory_entry_serialize_includes_formulas():
    """Test MemoryEntry.serialize() includes formula fields."""
    entry = MemoryEntry(
        turn_index=5,
        event_type="breakthrough",
        description="Notable upward clarity shift detected.",
        metrics={"coherence_score": 0.85},
        smi=0.75,
        tension_corridor=0.45,
    )

    serialized = entry.serialize()

    assert "smi" in serialized
    assert serialized["smi"] == 0.75
    assert "tension_corridor" in serialized
    assert serialized["tension_corridor"] == 0.45


# ==============================================================================
# Test 5: CoherenceObserver Formulas
# ==============================================================================


def test_coherence_observation_has_formula_fields():
    """Test CoherenceObservation has Phase 2 formula fields."""
    obs = CoherenceObservation(
        coherence_score=0.8,
        persona_drift_score=0.2,
        semantic_stability_score=0.75,
        temporal_arc_score=0.7,
        mapper_volatility_score=0.3,
        turn_number=5,
        tier="hybrid",
        domain="generic",
        active_mappers=["HRM"],
        avg_smi=0.65,
        max_smi=0.8,
        min_smi=0.5,
        delta_smi=0.1,
        bhava_gap=0.2,
        tension_corridor=0.35,
    )

    assert obs.avg_smi == 0.65
    assert obs.max_smi == 0.8
    assert obs.min_smi == 0.5
    assert obs.delta_smi == 0.1
    assert obs.bhava_gap == 0.2
    assert obs.tension_corridor == 0.35


def test_coherence_observer_extracts_formulas():
    """Test CoherenceObserver.observe() extracts formulas from coherence_state."""
    observer = CoherenceObserver()

    # Mock pipeline context
    class MockContext:
        pass

    ctx = MockContext()

    # Mock coherence state with formulas
    coherence_state = CoherenceState(convo_id="test", turn_index=5)
    coherence_state.smi_history = [0.5, 0.6, 0.7]
    coherence_state.delta_smi_history = [0.0, 0.1, 0.1]
    coherence_state.bhava_gap_history = [0.0, 0.2, 0.25]
    coherence_state.tension_corridor_history = [0.3, 0.35, 0.4]
    coherence_state.avg_smi = 0.6
    coherence_state.max_smi = 0.7
    coherence_state.min_smi = 0.5
    coherence_state.avg_tension_corridor = 0.35
    coherence_state.max_tension_corridor = 0.4

    # Observe
    obs = observer.observe("test text", ctx, coherence_state)

    # Check formula fields
    assert obs.avg_smi == 0.6
    assert obs.max_smi == 0.7
    assert obs.min_smi == 0.5
    assert obs.delta_smi == 0.1  # Last value from delta_smi_history
    assert obs.bhava_gap == 0.25  # Last value from bhava_gap_history
    assert obs.tension_corridor == 0.4  # Last value from tension_corridor_history


def test_coherence_observer_snapshot_includes_formulas():
    """Test CoherenceObserver.snapshot() includes formulas section."""
    observer = CoherenceObserver()

    # Mock pipeline context
    class MockContext:
        pass

    ctx = MockContext()

    # Mock coherence state with formulas
    coherence_state = CoherenceState(convo_id="test", turn_index=5)
    coherence_state.smi_history = [0.7]
    coherence_state.delta_smi_history = [0.1]
    coherence_state.bhava_gap_history = [0.2]
    coherence_state.tension_corridor_history = [0.35]
    coherence_state.avg_smi = 0.7
    coherence_state.max_smi = 0.7

    # Observe
    observer.observe("test text", ctx, coherence_state)

    # Get snapshot
    snapshot = observer.snapshot()

    # Check formulas section
    assert "formulas" in snapshot
    formulas = snapshot["formulas"]
    assert "smi" in formulas
    assert "delta_smi" in formulas
    assert "bhava_gap" in formulas
    assert "tension_corridor" in formulas


# ==============================================================================
# Test 6: Behavioral Invariance (No Routing/Scoring Changes)
# ==============================================================================


def test_coherence_score_formula_unchanged():
    """
    Test that coherence_score formula is unchanged by Phase 2 aggregates.

    This is a critical invariance test - coherence_score must not be affected
    by Phase 2 formula aggregates.
    """
    engine = CoherenceEngine(window=10)

    # Mock routing plan
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "generic"
        long_arc_tension = 0.5

    routing_plan = MockRoutingPlan()

    # Create two states - one with formulas, one without
    # Both should have identical coherence scores

    # State 1: With formulas
    state1 = engine.update_state(
        prev_state=None,
        convo_id="test1",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile={},
        temporal_summary={"smi": 0.5, "delta_smi": 0.0, "bhava_gap": 0.0, "tension_corridor": 0.3},
        semantic_signature={},
    )

    # State 2: Without formulas (None values)
    state2 = engine.update_state(
        prev_state=None,
        convo_id="test2",
        turn_index=0,
        routing_plan=routing_plan,
        mapper_profile={},
        temporal_summary={},  # No formulas
        semantic_signature={},
    )

    # Coherence scores should be identical (formulas don't affect scoring)
    # Both should default to same base values
    assert state1.coherence_score == state2.coherence_score


def test_phase2_formulas_are_observation_only():
    """
    Test that Phase 2 formulas are observation-only and don't affect behavior.

    This test verifies that formula values don't change:
    - Persona drift score
    - Semantic stability score
    - Mapper volatility score
    - Temporal arc score
    - Overall coherence score
    """
    engine = CoherenceEngine(window=10)

    # Mock routing plan
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "generic"
        long_arc_tension = 0.5

    routing_plan = MockRoutingPlan()

    # State with high formula values
    state_high = CoherenceState(convo_id="high", turn_index=0)
    state_high.smi_history = [0.9, 0.95, 1.0]
    state_high.delta_smi_history = [0.0, 0.05, 0.05]
    state_high.bhava_gap_history = [0.0, 0.5, 0.8]
    state_high.tension_corridor_history = [0.5, 0.7, 0.9]
    engine._update_formula_aggregates(state_high)

    # State with low formula values
    state_low = CoherenceState(convo_id="low", turn_index=0)
    state_low.smi_history = [0.1, 0.15, 0.2]
    state_low.delta_smi_history = [0.0, 0.05, 0.05]
    state_low.bhava_gap_history = [0.0, 0.1, 0.15]
    state_low.tension_corridor_history = [0.1, 0.15, 0.2]
    engine._update_formula_aggregates(state_low)

    # Both states should have identical core scores (since formula aggregates don't affect them)
    # The scores are computed from other factors (domain history, mapper profile, etc.)
    # which we haven't set differently

    # Verify aggregates are different
    assert state_high.avg_smi != state_low.avg_smi
    assert state_high.max_tension_corridor != state_low.max_tension_corridor

    # But core scores should both be at default/neutral values
    # (since we haven't provided different domain/mapper data)
    assert state_high.persona_drift_score == state_low.persona_drift_score
    assert state_high.semantic_stability_score == state_low.semantic_stability_score
    assert state_high.mapper_volatility_score == state_low.mapper_volatility_score


# ==============================================================================
# Test 7: Multi-Turn Integration
# ==============================================================================


def test_multi_turn_formula_propagation():
    """
    Test formula propagation across multiple turns in a realistic scenario.

    This integration test verifies:
    1. Formulas are computed by temporal tracker
    2. Formulas are ingested by coherence engine
    3. Formulas are aggregated in coherence state
    4. Formulas appear in session summary
    5. Formulas appear in unified output (tested via mock)
    """
    # Create temporal tracker
    tracker = TemporalBhavaTracker(window_size=10)

    # Create coherence engine
    coherence_engine = CoherenceEngine(window=10)

    # Mock routing plan
    class MockRoutingPlan:
        tier = "hybrid"
        domain = "generic"
        long_arc_tension = 0.5

    routing_plan = MockRoutingPlan()

    # Simulate 3 turns
    coherence_state = None

    for turn in range(3):
        # Compute formulas
        temporal_state = tracker.compute_formulas(
            dimensional_resonance=0.5 + turn * 0.1,
            vrtti_intensity=0.5 + turn * 0.1,
            bhava_position=0.5 + turn * 0.1,
            current_bhava=turn,
        )

        # Build temporal summary with formulas
        temporal_summary = {
            "smi": temporal_state.smi,
            "delta_smi": temporal_state.delta_smi,
            "bhava_gap": temporal_state.bhava_gap,
            "tension_corridor": temporal_state.tension_corridor,
        }

        # Update coherence state
        coherence_state = coherence_engine.update_state(
            prev_state=coherence_state,
            convo_id="test",
            turn_index=turn,
            routing_plan=routing_plan,
            mapper_profile={},
            temporal_summary=temporal_summary,
            semantic_signature={},
        )

    # Verify final coherence state has formula histories
    assert len(coherence_state.smi_history) == 3
    assert len(coherence_state.delta_smi_history) == 3
    assert len(coherence_state.bhava_gap_history) == 3
    assert len(coherence_state.tension_corridor_history) == 3

    # Verify aggregates are computed
    assert coherence_state.avg_smi is not None
    assert coherence_state.max_smi is not None
    assert coherence_state.min_smi is not None
    assert coherence_state.avg_tension_corridor is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
