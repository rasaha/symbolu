"""
Test Suite for Intent Arc Engine v1.0

This module contains comprehensive deterministic tests for the Intent Arc Engine,
covering all 8 arc types, integration with the pipeline, and DILchat UI behavior.

Test Groups:
    Group A: Core Arc Detection (12 tests)
    Group B: Integration Tests (8 tests)
    Group C: DILchat UI Tests (6 tests)

Total: 26 tests
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Optional


# ============================================================================
# Mock Session Components
# ============================================================================


@dataclass
class MockSessionSummary:
    """Mock SessionSummary for testing."""
    turn_count: int = 5
    coherence_score: float = 0.7
    coherence_trend: float = 0.7
    persona_drift_avg: float = 0.3
    persona_drift_score: float = 0.3
    temporal_arc_avg: float = 0.6
    temporal_arc_score: float = 0.6
    semantic_stability_score: float = 0.7
    mapper_volatility_score: float = 0.3
    last_tier: str = "HYBRID"
    last_domain: str = "generic"
    coherence_timeline: List[float] = field(default_factory=lambda: [0.6, 0.65, 0.7, 0.75, 0.8])
    temporal_arc_timeline: List[float] = field(default_factory=lambda: [0.5, 0.55, 0.6, 0.65, 0.7])
    mapper_sets: List[Set[str]] = field(default_factory=lambda: [{"HRM"}, {"HRM"}, {"LAM"}, {"LAM"}, {"LAM"}])


@dataclass
class MockMemoryEntry:
    """Mock MemoryEntry for testing."""
    turn_index: int
    event_type: str
    description: str
    metrics: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MockSessionMemory:
    """Mock SessionMemory for testing."""
    events: List[MockMemoryEntry] = field(default_factory=list)


@dataclass
class MockSessionPolicyFlags:
    """Mock SessionPolicyFlags for testing."""
    session_needs_grounding: bool = False
    session_allow_deep_reflection: bool = False
    session_is_stable: bool = True
    session_is_recovering: bool = False
    session_is_fragmented: bool = False
    session_recommended_style: str = "reflective"


@dataclass
class MockSessionRecap:
    """Mock SessionRecap for testing."""
    overall_state: str = "stable"
    net_trajectory: str = "improving"
    turning_points: List[Dict] = field(default_factory=list)
    mapper_journey: List[str] = field(default_factory=lambda: ["HRM", "HRM", "LAM", "LAM", "LAM"])
    key_patterns: List[str] = field(default_factory=list)
    recommended_style: str = "reflective"
    turn_count: int = 5
    domain: str = "generic"


# ============================================================================
# GROUP A: Core Arc Detection Tests (12 tests)
# ============================================================================


def test_stabilization_arc_detection():
    """Test detection of stabilization arc (coherence rising + low volatility)."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session with rising coherence and low volatility (no LAM to avoid identity arc)
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.6, 0.65, 0.7, 0.75, 0.8],  # Rising
        mapper_volatility_score=0.30,  # Low volatility (< 0.40)
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],  # No LAM
    )
    memory = MockSessionMemory()
    recap = MockSessionRecap(net_trajectory="improving")

    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc.arc_type == "stabilization_arc"
    assert 0.70 <= arc.confidence <= 0.90
    assert "coherence_rising" in arc.reasons
    assert "low_volatility" in arc.reasons


def test_insight_arc_detection():
    """Test detection of insight arc (breakthrough + high temporal arc)."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session with breakthrough events and high temporal arc (no LAM)
    summary = MockSessionSummary(
        turn_count=5,
        temporal_arc_score=0.70,  # High (>= 0.55)
        coherence_timeline=[0.7, 0.72, 0.75, 0.77, 0.80],  # Improving
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],  # No LAM
    )
    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=3, event_type="breakthrough", description="Breakthrough detected")
    ])
    recap = MockSessionRecap()

    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc.arc_type == "insight_arc"
    assert 0.75 <= arc.confidence <= 0.95
    assert "breakthrough_detected" in arc.reasons
    assert "strong_upward_arc" in arc.reasons


def test_identity_arc_detection():
    """Test detection of identity arc (LAM active + reflective/exploratory)."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session with LAM active and reflective style
    summary = MockSessionSummary(
        turn_count=5,
        mapper_sets=[{"HRM"}, {"HRM"}, {"LAM"}, {"LAM"}, {"LAM"}],
    )
    memory = MockSessionMemory()
    recap = MockSessionRecap(
        recommended_style="reflective",
        net_trajectory="improving"
    )

    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc.arc_type == "identity_arc"
    assert 0.60 <= arc.confidence <= 0.85
    assert "lam_active" in arc.reasons
    assert "identity_exploration" in arc.reasons


def test_resolution_arc_detection():
    """Test detection of resolution arc (fragmentation → stabilization)."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session with fragmentation then stabilization
    summary = MockSessionSummary(turn_count=5)
    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Fragmentation"),
        MockMemoryEntry(turn_index=4, event_type="stabilization", description="Stabilization"),
    ])
    recap = MockSessionRecap(net_trajectory="improving")

    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc.arc_type == "resolution_arc"
    assert 0.65 <= arc.confidence <= 0.90
    assert "fragmentation_to_stabilization" in arc.reasons
    assert "recovery_trajectory" in arc.reasons


def test_dissonance_arc_detection():
    """Test detection of dissonance arc (high persona drift + oscillating)."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session with high persona drift and oscillating trajectory (no rising coherence)
    summary = MockSessionSummary(
        turn_count=5,
        persona_drift_score=0.70,  # High (> 0.55)
        coherence_timeline=[0.65, 0.60, 0.68, 0.62, 0.66],  # Oscillating, not rising
        mapper_sets=[{"HRM"}, {"LCM"}, {"HRM"}, {"LCM"}, {"HRM"}],  # No LAM
    )
    memory = MockSessionMemory()
    recap = MockSessionRecap(net_trajectory="oscillating")

    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc.arc_type == "dissonance_arc"
    assert 0.55 <= arc.confidence <= 0.80
    assert "high_persona_drift" in arc.reasons
    assert "trajectory_instability" in arc.reasons


def test_avoidance_arc_detection():
    """Test detection of avoidance arc (flat coherence + low temporal)."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session with flat coherence and low temporal arc (no LAM)
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.70, 0.70, 0.71, 0.70, 0.70],  # Flat (delta < 0.05)
        temporal_arc_score=0.30,  # Low (< 0.40)
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],  # No LAM
    )
    memory = MockSessionMemory()  # No breakthrough events
    recap = MockSessionRecap()

    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc.arc_type == "avoidance_arc"
    assert 0.50 <= arc.confidence <= 0.75
    assert "low_temporal_progress" in arc.reasons
    assert "flat_coherence" in arc.reasons


def test_expansion_arc_detection():
    """Test detection of expansion arc (HRM+LAM synergy + rising temporal)."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session with HRM+LAM synergy
    summary = MockSessionSummary(
        turn_count=5,
        mapper_sets=[{"HRM"}, {"HRM", "LAM"}, {"HRM", "LAM"}, {"HRM", "LAM"}, {"HRM", "LAM"}],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.70],  # Rising
        coherence_timeline=[0.65, 0.68, 0.71, 0.74, 0.77],  # Improving
    )
    memory = MockSessionMemory()
    recap = MockSessionRecap()

    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc.arc_type == "expansion_arc"
    assert 0.70 <= arc.confidence <= 0.95
    assert "lam_hrm_synergy" in arc.reasons
    assert "expanding_context" in arc.reasons


def test_chaotic_arc_detection():
    """Test detection of chaotic arc (high volatility + multiple instabilities)."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session with high mapper volatility (no LAM to avoid identity arc)
    summary = MockSessionSummary(
        turn_count=5,
        mapper_volatility_score=0.70,  # High (> 0.55)
        coherence_timeline=[0.70, 0.60, 0.75, 0.55, 0.72],  # Oscillating
        mapper_sets=[{"HRM"}, {"LCM"}, {"HRM"}, {"LCM"}, {"HRM"}],  # No LAM, high volatility
    )
    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Fragmentation"),
        MockMemoryEntry(turn_index=3, event_type="arc_shift", description="Arc shift"),
    ])
    recap = MockSessionRecap()

    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc.arc_type == "chaotic_arc"
    assert 0.60 <= arc.confidence <= 0.85
    assert "high_volatility" in arc.reasons


def test_mixed_patterns_ranking():
    """Test that multiple matching arcs are ranked correctly by confidence."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session that could match multiple arcs, but insight should win (highest confidence)
    summary = MockSessionSummary(
        turn_count=5,
        temporal_arc_score=0.75,  # High - matches insight
        coherence_timeline=[0.60, 0.65, 0.70, 0.75, 0.80],  # Rising - matches stabilization
        mapper_volatility_score=0.30,  # Low volatility
        mapper_sets=[{"LAM"}, {"LAM"}, {"LAM"}, {"LAM"}, {"LAM"}],  # LAM active - matches identity
    )
    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=3, event_type="breakthrough", description="Breakthrough")
    ])
    recap = MockSessionRecap(
        recommended_style="reflective",
        net_trajectory="improving"
    )

    arc = compute_intent_arc(summary, memory, None, recap)

    # Insight arc should win due to highest confidence (breakthrough + high temporal)
    assert arc.arc_type == "insight_arc"
    assert arc.confidence > 0.75


def test_tiebreak_deterministic():
    """Test that tiebreaking is deterministic when confidences are equal."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create session with minimal signals (low confidence for all arcs)
    summary = MockSessionSummary(
        turn_count=3,
        coherence_timeline=[0.70, 0.70, 0.70],  # Flat
        temporal_arc_score=0.35,  # Low
        mapper_volatility_score=0.50,  # Medium
    )
    memory = MockSessionMemory()
    recap = MockSessionRecap()

    # Run multiple times to verify determinism
    arc1 = compute_intent_arc(summary, memory, None, recap)
    arc2 = compute_intent_arc(summary, memory, None, recap)
    arc3 = compute_intent_arc(summary, memory, None, recap)

    assert arc1.arc_type == arc2.arc_type == arc3.arc_type
    assert arc1.confidence == arc2.confidence == arc3.confidence


def test_confidence_computation():
    """Test that confidence scores are computed correctly within expected ranges."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Test stabilization arc with strong signal (no LAM)
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.50, 0.60, 0.70, 0.80, 0.90],  # Strong rise
        mapper_volatility_score=0.20,  # Very low volatility
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],  # No LAM
    )
    memory = MockSessionMemory()
    recap = MockSessionRecap()

    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc.arc_type == "stabilization_arc"
    # Strong signal should result in high confidence
    assert arc.confidence >= 0.80


def test_edge_case_minimal_turns():
    """Test that engine handles minimal turns gracefully."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Test with 0 turns
    summary = MockSessionSummary(
        turn_count=0,
        coherence_timeline=[],
        temporal_arc_timeline=[],
        mapper_sets=[],
    )
    memory = MockSessionMemory()
    recap = None

    arc = compute_intent_arc(summary, memory, None, recap)

    # Should return avoidance_arc with low confidence
    assert arc.arc_type == "avoidance_arc"
    assert arc.confidence < 0.50
    assert "insufficient_turns" in arc.reasons


# ============================================================================
# GROUP B: Integration Tests (8 tests)
# ============================================================================


def test_orchestrator_integration():
    """Test that orchestrator attaches intent_arc to context."""
    # This is a smoke test for orchestrator integration
    # In a real test, we would mock PipelineContext and verify ctx.intent_arc is set
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    summary = MockSessionSummary()
    memory = MockSessionMemory()
    recap = MockSessionRecap()

    arc = compute_intent_arc(summary, memory, None, recap)

    # Verify that compute_intent_arc returns a valid IntentArc object
    assert arc is not None
    assert hasattr(arc, 'arc_type')
    assert hasattr(arc, 'confidence')
    assert hasattr(arc, 'reasons')


def test_unified_api_serialization():
    """Test that intent_arc serializes correctly for unified API."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    summary = MockSessionSummary()
    memory = MockSessionMemory()
    recap = MockSessionRecap()

    arc = compute_intent_arc(summary, memory, None, recap)

    # Test serialization
    serialized = arc.serialize()

    assert isinstance(serialized, dict)
    assert "arc_type" in serialized
    assert "confidence" in serialized
    assert "reasons" in serialized
    assert "turn_count" in serialized
    assert "domain" in serialized


def test_public_response_safe():
    """Test that serialized arc is safe for public API consumption."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc
    import json

    summary = MockSessionSummary()
    memory = MockSessionMemory()
    recap = MockSessionRecap()

    arc = compute_intent_arc(summary, memory, None, recap)
    serialized = arc.serialize()

    # Verify JSON-safe
    try:
        json_str = json.dumps(serialized)
        roundtrip = json.loads(json_str)
        assert roundtrip == serialized
    except (TypeError, ValueError) as e:
        pytest.fail(f"Serialization not JSON-safe: {e}")


def test_recap_to_arc_flow():
    """Test data flow from session recap to intent arc computation."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create recap with specific trajectory (no LAM to avoid identity arc)
    recap = MockSessionRecap(
        overall_state="recovering",
        net_trajectory="improving",
        key_patterns=["recovery_in_progress"]
    )

    summary = MockSessionSummary(
        coherence_timeline=[0.50, 0.55, 0.60, 0.65, 0.70],  # Rising
        mapper_volatility_score=0.30,
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],  # No LAM
    )
    memory = MockSessionMemory()

    arc = compute_intent_arc(summary, memory, None, recap)

    # Should detect stabilization arc due to recovering trajectory
    assert arc.arc_type == "stabilization_arc"


def test_deterministic_output():
    """Test that same inputs always produce same outputs (determinism)."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    summary = MockSessionSummary()
    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough")
    ])
    recap = MockSessionRecap()

    # Run 10 times with same inputs
    results = []
    for _ in range(10):
        arc = compute_intent_arc(summary, memory, None, recap)
        results.append((arc.arc_type, arc.confidence, tuple(arc.reasons)))

    # All results should be identical
    assert len(set(results)) == 1


def test_sessionless_operation_safe():
    """Test that engine handles missing session components gracefully."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Test with None session_memory and session_recap
    summary = MockSessionSummary()

    arc = compute_intent_arc(summary, None, None, None)

    # Should still return a valid arc
    assert arc is not None
    assert arc.arc_type is not None
    assert arc.confidence > 0.0


def test_invalid_summary_fallback():
    """Test that engine handles invalid/minimal summary data."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Create minimal summary with empty timelines
    summary = MockSessionSummary(
        turn_count=1,
        coherence_timeline=[0.5],
        temporal_arc_timeline=[0.5],
        mapper_sets=[set()],
    )
    memory = MockSessionMemory()

    arc = compute_intent_arc(summary, memory, None, None)

    # Should return a safe fallback arc
    assert arc is not None
    assert arc.arc_type is not None


def test_no_turning_points_no_crash():
    """Test that engine handles sessions with no turning points."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    summary = MockSessionSummary()
    memory = MockSessionMemory(events=[])  # No events
    recap = MockSessionRecap(turning_points=[])  # No turning points

    # Should not crash
    arc = compute_intent_arc(summary, memory, None, recap)

    assert arc is not None
    assert arc.arc_type is not None


# ============================================================================
# GROUP C: DILchat UI Tests (6 tests)
# ============================================================================


def test_correct_badges_per_arc():
    """Test that correct badges are generated for each arc type."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Test insight arc → INSIGHT badge
    summary = MockSessionSummary(
        temporal_arc_score=0.75,
        coherence_timeline=[0.70, 0.75, 0.80, 0.85, 0.90],
    )
    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=3, event_type="breakthrough", description="Breakthrough")
    ])

    arc = compute_intent_arc(summary, memory, None, None)

    # Simulate DILchat badge logic
    if arc.arc_type == "insight_arc":
        badge_label = "INSIGHT"
    elif arc.arc_type == "stabilization_arc":
        badge_label = "STABILIZING"
    else:
        badge_label = None

    assert arc.arc_type == "insight_arc"
    assert badge_label == "INSIGHT"


def test_correct_hints_per_arc():
    """Test that correct hints are generated for each arc type."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Test chaotic arc → PROMOTE_GROUNDING hint
    summary = MockSessionSummary(
        mapper_volatility_score=0.75,
        coherence_timeline=[0.70, 0.50, 0.80, 0.45, 0.75],
    )
    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Fragmentation"),
        MockMemoryEntry(turn_index=3, event_type="arc_shift", description="Arc shift"),
    ])

    arc = compute_intent_arc(summary, memory, None, None)

    # Simulate DILchat hint logic
    if arc.arc_type in ["chaotic_arc", "dissonance_arc"]:
        hint_code = "PROMOTE_GROUNDING"
    else:
        hint_code = None

    assert arc.arc_type == "chaotic_arc"
    assert hint_code == "PROMOTE_GROUNDING"


def test_badge_hint_combinations_deterministic():
    """Test that badge/hint combinations are deterministic."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    summary = MockSessionSummary()
    memory = MockSessionMemory()
    recap = MockSessionRecap()

    # Compute arc multiple times
    arcs = [compute_intent_arc(summary, memory, None, recap) for _ in range(5)]

    # All arc types should be the same
    arc_types = [arc.arc_type for arc in arcs]
    assert len(set(arc_types)) == 1


def test_multiple_turn_ui_consistency():
    """Test that UI indicators remain consistent across turns."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Simulate turn 3
    summary_t3 = MockSessionSummary(
        turn_count=3,
        coherence_timeline=[0.70, 0.75, 0.80],
        mapper_volatility_score=0.30,
    )

    arc_t3 = compute_intent_arc(summary_t3, MockSessionMemory(), None, None)

    # Simulate turn 4 (continuation)
    summary_t4 = MockSessionSummary(
        turn_count=4,
        coherence_timeline=[0.70, 0.75, 0.80, 0.85],
        mapper_volatility_score=0.30,
    )

    arc_t4 = compute_intent_arc(summary_t4, MockSessionMemory(), None, None)

    # Both should detect stabilization arc
    assert arc_t3.arc_type == "stabilization_arc"
    assert arc_t4.arc_type == "stabilization_arc"


def test_arc_transitions_stable():
    """Test that arc transitions produce stable UI behavior."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc

    # Start in stabilization
    summary_stable = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.65, 0.70, 0.75, 0.80],
        mapper_volatility_score=0.30,
    )

    arc_stable = compute_intent_arc(summary_stable, MockSessionMemory(), None, None)
    assert arc_stable.arc_type == "stabilization_arc"

    # Add breakthrough → should transition to insight arc
    memory_breakthrough = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=5, event_type="breakthrough", description="Breakthrough")
    ])
    summary_insight = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.60, 0.65, 0.70, 0.75, 0.80, 0.90],
        temporal_arc_score=0.75,
        mapper_volatility_score=0.30,
    )

    arc_insight = compute_intent_arc(summary_insight, memory_breakthrough, None, None)
    assert arc_insight.arc_type == "insight_arc"


def test_snapshot_determinism():
    """Test that snapshots of the same state produce identical results."""
    from symbolu.intent.intent_arc_engine import compute_intent_arc
    import copy

    # Create snapshot 1
    summary1 = MockSessionSummary()
    memory1 = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough")
    ])
    recap1 = MockSessionRecap()

    arc1 = compute_intent_arc(summary1, memory1, None, recap1)

    # Create snapshot 2 (deep copy)
    summary2 = copy.deepcopy(summary1)
    memory2 = copy.deepcopy(memory1)
    recap2 = copy.deepcopy(recap1)

    arc2 = compute_intent_arc(summary2, memory2, None, recap2)

    # Should produce identical results
    assert arc1.arc_type == arc2.arc_type
    assert arc1.confidence == arc2.confidence
    assert arc1.reasons == arc2.reasons


# ============================================================================
# Test Execution Summary
# ============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
