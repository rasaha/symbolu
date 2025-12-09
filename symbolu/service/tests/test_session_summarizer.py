"""
Test Suite for Session Summarizer v1.0

This module tests the deterministic multi-turn recap layer with 22 tests covering:
- Group A: Recap Construction (10 tests)
- Group B: Key Pattern Logic (6 tests)
- Group C: Pipeline Integration (6 tests)

All tests are deterministic and zero-LLM.
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Set, Any, Dict

# Import session summarizer components
from symbolu.service.sessions.session_summarizer import (
    SessionRecap,
    compute_session_recap,
    _compute_net_trajectory,
    _extract_turning_points,
    _build_mapper_journey,
    _detect_key_patterns,
    _determine_recommended_style,
)

# Import session models for test fixtures
from symbolu.service.sessions.session_memory import MemoryEntry, SessionMemory


# ============================================================================
# TEST FIXTURES
# ============================================================================


@dataclass
class MockSessionSummary:
    """Mock SessionSummary for testing."""
    coherence_score: float = 0.75
    coherence_timeline: List[float] = field(default_factory=list)
    temporal_arc_timeline: List[float] = field(default_factory=list)
    mapper_sets: List[Set[str]] = field(default_factory=list)
    mapper_volatility_score: float = 0.3
    turn_count: int = 0
    last_domain: str = "generic"


@dataclass
class MockSessionPolicy:
    """Mock SessionPolicyFlags for testing."""
    session_recommended_style: str = "neutral"


# ============================================================================
# GROUP A: RECAP CONSTRUCTION TESTS (10 tests)
# ============================================================================


def test_stable_classification():
    """Test that coherence_score >= 0.70 results in 'stable' classification."""
    summary = MockSessionSummary(
        coherence_score=0.75,
        coherence_timeline=[0.7, 0.72, 0.75],
        turn_count=3
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert recap.overall_state == "stable"


def test_recovering_classification():
    """Test that 0.45 <= coherence_score < 0.70 results in 'recovering' classification."""
    summary = MockSessionSummary(
        coherence_score=0.55,
        coherence_timeline=[0.5, 0.53, 0.55],
        turn_count=3
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert recap.overall_state == "recovering"


def test_fragmented_classification():
    """Test that coherence_score < 0.45 results in 'fragmented' classification."""
    summary = MockSessionSummary(
        coherence_score=0.35,
        coherence_timeline=[0.4, 0.37, 0.35],
        turn_count=3
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert recap.overall_state == "fragmented"


def test_improving_trajectory_detection():
    """Test that delta >= 0.10 results in 'improving' trajectory."""
    summary = MockSessionSummary(
        coherence_score=0.75,
        coherence_timeline=[0.5, 0.6, 0.7],  # delta = 0.2
        turn_count=3
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert recap.net_trajectory == "improving"


def test_declining_trajectory_detection():
    """Test that delta <= -0.10 results in 'declining' trajectory."""
    summary = MockSessionSummary(
        coherence_score=0.45,
        coherence_timeline=[0.7, 0.6, 0.45],  # delta = -0.25
        turn_count=3
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert recap.net_trajectory == "declining"


def test_oscillating_detection():
    """Test that small delta (not improving/declining) results in 'oscillating'."""
    summary = MockSessionSummary(
        coherence_score=0.65,
        coherence_timeline=[0.6, 0.7, 0.65],  # delta = 0.05 (not >= 0.10 or <= -0.10)
        turn_count=3
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert recap.net_trajectory == "oscillating"


def test_ambiguous_trajectory_detection():
    """Test that abs(delta) < 0.05 results in 'ambiguous' trajectory."""
    summary = MockSessionSummary(
        coherence_score=0.65,
        coherence_timeline=[0.64, 0.645, 0.65],  # delta = 0.01
        turn_count=3
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert recap.net_trajectory == "ambiguous"


def test_turning_point_extraction_correctness():
    """Test that all turning point event types are correctly extracted."""
    summary = MockSessionSummary(turn_count=5)
    memory = SessionMemory()

    # Add various event types
    memory.add_event(MemoryEntry(0, "breakthrough", "Breakthrough detected", {}))
    memory.add_event(MemoryEntry(1, "fragmentation", "Fragmentation detected", {}))
    memory.add_event(MemoryEntry(2, "stabilization", "Stabilization detected", {}))
    memory.add_event(MemoryEntry(3, "arc_shift", "Arc shift detected", {}))
    memory.add_event(MemoryEntry(4, "mapper_flip", "Mapper flip detected", {}))

    recap = compute_session_recap(summary, memory, None, "generic")

    assert len(recap.turning_points) == 5
    event_types = [tp['event_type'] for tp in recap.turning_points]
    assert 'breakthrough' in event_types
    assert 'fragmentation' in event_types
    assert 'stabilization' in event_types
    assert 'arc_shift' in event_types
    assert 'mapper_flip' in event_types


def test_mapper_journey_serialization():
    """Test that mapper sets are correctly serialized to strings."""
    summary = MockSessionSummary(
        coherence_score=0.75,
        mapper_sets=[
            {"HRM"},
            {"HRM", "LAM"},
            {"LCM"},
            set()
        ],
        turn_count=4
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert recap.mapper_journey == ["HRM", "HRM+LAM", "LCM", "none"]


def test_recommended_style_propagation():
    """Test that session_policy.session_recommended_style is correctly propagated."""
    summary = MockSessionSummary(coherence_score=0.75, turn_count=1)
    memory = SessionMemory()
    policy = MockSessionPolicy(session_recommended_style="reflective")

    recap = compute_session_recap(summary, memory, policy, "generic")

    assert recap.recommended_style == "reflective"


# ============================================================================
# GROUP B: KEY PATTERN LOGIC TESTS (6 tests)
# ============================================================================


def test_breakthrough_detected_pattern():
    """Test that 'breakthrough_detected' pattern is added when breakthrough event exists."""
    summary = MockSessionSummary(turn_count=1)
    memory = SessionMemory()
    memory.add_event(MemoryEntry(0, "breakthrough", "Breakthrough", {}))

    recap = compute_session_recap(summary, memory, None, "generic")

    assert "breakthrough_detected" in recap.key_patterns


def test_instability_present_pattern():
    """Test that 'instability_present' pattern is added when fragmentation event exists."""
    summary = MockSessionSummary(turn_count=1)
    memory = SessionMemory()
    memory.add_event(MemoryEntry(0, "fragmentation", "Fragmentation", {}))

    recap = compute_session_recap(summary, memory, None, "generic")

    assert "instability_present" in recap.key_patterns


def test_recovery_in_progress_pattern():
    """Test that 'recovery_in_progress' pattern is added when stabilization occurs after fragmentation."""
    summary = MockSessionSummary(turn_count=3)
    memory = SessionMemory()
    memory.add_event(MemoryEntry(0, "fragmentation", "Fragmentation", {}))
    memory.add_event(MemoryEntry(2, "stabilization", "Stabilization", {}))

    recap = compute_session_recap(summary, memory, None, "generic")

    assert "recovery_in_progress" in recap.key_patterns


def test_deepening_arc_pattern():
    """Test that 'deepening_arc' pattern is added when trajectory improving AND LAM active."""
    summary = MockSessionSummary(
        coherence_timeline=[0.5, 0.6, 0.75],  # improving trajectory
        mapper_sets=[{"HRM"}, {"LAM"}],
        turn_count=2
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert "deepening_arc" in recap.key_patterns


def test_volatile_strategy_shift_pattern():
    """Test that 'volatile_strategy_shift' pattern is added when mapper_volatility_score > 0.55."""
    summary = MockSessionSummary(
        mapper_volatility_score=0.65,
        turn_count=1
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "generic")

    assert "volatile_strategy_shift" in recap.key_patterns


def test_deterministic_results_for_same_input():
    """Test that same input produces same output (determinism check)."""
    summary = MockSessionSummary(
        coherence_score=0.75,
        coherence_timeline=[0.6, 0.7, 0.75],
        mapper_sets=[{"HRM"}, {"LAM"}],
        turn_count=3
    )
    memory = SessionMemory()
    memory.add_event(MemoryEntry(0, "breakthrough", "Breakthrough", {}))

    recap1 = compute_session_recap(summary, memory, None, "generic")
    recap2 = compute_session_recap(summary, memory, None, "generic")

    assert recap1.overall_state == recap2.overall_state
    assert recap1.net_trajectory == recap2.net_trajectory
    assert recap1.key_patterns == recap2.key_patterns
    assert recap1.recommended_style == recap2.recommended_style


# ============================================================================
# GROUP C: PIPELINE INTEGRATION TESTS (6 tests)
# ============================================================================


def test_orchestrator_attaches_session_recap():
    """Test that session recap is attached to context (integration simulation)."""
    # This test simulates the orchestrator integration
    summary = MockSessionSummary(
        coherence_score=0.75,
        turn_count=1
    )
    memory = SessionMemory()

    # Simulate orchestrator calling compute_session_recap
    session_recap = compute_session_recap(summary, memory, None, "trading")

    # Verify recap is not None and has expected attributes
    assert session_recap is not None
    assert hasattr(session_recap, 'overall_state')
    assert hasattr(session_recap, 'net_trajectory')
    assert hasattr(session_recap, 'domain')
    assert session_recap.domain == "trading"


def test_unified_output_exposes_recap():
    """Test that SessionRecap.serialize() produces JSON-safe output."""
    summary = MockSessionSummary(
        coherence_score=0.75,
        coherence_timeline=[0.7, 0.75],
        turn_count=2
    )
    memory = SessionMemory()

    recap = compute_session_recap(summary, memory, None, "therapy")
    serialized = recap.serialize()

    # Verify all expected fields are present
    assert "overall_state" in serialized
    assert "net_trajectory" in serialized
    assert "turning_points" in serialized
    assert "mapper_journey" in serialized
    assert "key_patterns" in serialized
    assert "recommended_style" in serialized
    assert "turn_count" in serialized
    assert "domain" in serialized

    # Verify values are JSON-safe types
    assert isinstance(serialized["overall_state"], str)
    assert isinstance(serialized["net_trajectory"], str)
    assert isinstance(serialized["turning_points"], list)
    assert isinstance(serialized["mapper_journey"], list)
    assert isinstance(serialized["key_patterns"], list)
    assert isinstance(serialized["recommended_style"], str)
    assert isinstance(serialized["turn_count"], int)
    assert isinstance(serialized["domain"], str)


def test_public_response_trims_recap_safely():
    """Test that public response trimming works correctly."""
    summary = MockSessionSummary(
        coherence_score=0.75,
        turn_count=3
    )
    memory = SessionMemory()
    memory.add_event(MemoryEntry(0, "breakthrough", "Breakthrough", {"score": 0.9}))
    memory.add_event(MemoryEntry(1, "fragmentation", "Fragmentation", {"score": 0.3}))

    recap = compute_session_recap(summary, memory, None, "generic")
    serialized = recap.serialize()

    # Simulate public API trimming (from unified_api._trim_session_recap_for_public)
    turning_points = serialized["turning_points"]
    significant_types = {'breakthrough', 'stabilization', 'fragmentation'}
    significant_turning_points = [
        tp for tp in turning_points
        if tp.get('event_type') in significant_types
    ]

    # Verify trimming preserves breakthrough and fragmentation
    assert len(significant_turning_points) == 2
    event_types = [tp['event_type'] for tp in significant_turning_points]
    assert 'breakthrough' in event_types
    assert 'fragmentation' in event_types


def test_dilchat_adapter_shows_badges_hints():
    """Test that DILchat adapter can extract recap data for badges/hints."""
    summary = MockSessionSummary(
        coherence_score=0.35,  # fragmented
        turn_count=1
    )
    memory = SessionMemory()
    memory.add_event(MemoryEntry(0, "breakthrough", "Breakthrough", {}))

    recap = compute_session_recap(summary, memory, None, "generic")

    # Simulate DILchat adapter logic
    overall_state = recap.overall_state
    key_patterns = recap.key_patterns
    recommended_style = recap.recommended_style

    # Verify badge conditions
    assert overall_state == "fragmented"  # Should trigger SESSION_FRAGMENTED badge

    # Verify hint conditions
    assert "breakthrough_detected" in key_patterns  # Should trigger BREAKTHROUGH badge
    assert recommended_style == "grounded"  # Should trigger GROUNDING_MODE hint


def test_sessionless_requests_do_not_break():
    """Test that system handles missing session components gracefully."""
    # Test with None session_memory
    summary = MockSessionSummary(coherence_score=0.75, turn_count=1)

    recap = compute_session_recap(summary, None, None, "generic")

    assert recap is not None
    assert recap.overall_state == "stable"
    assert recap.turning_points == []  # No events when memory is None


def test_snapshot_determinism():
    """Test that multiple invocations produce identical serialized output."""
    summary = MockSessionSummary(
        coherence_score=0.65,
        coherence_timeline=[0.5, 0.6, 0.65],
        mapper_sets=[{"HRM"}, {"LAM"}],
        mapper_volatility_score=0.45,
        turn_count=3
    )
    memory = SessionMemory()
    memory.add_event(MemoryEntry(0, "breakthrough", "Breakthrough", {}))
    memory.add_event(MemoryEntry(2, "stabilization", "Stabilization", {}))

    policy = MockSessionPolicy(session_recommended_style="exploratory")

    # Generate multiple recaps
    recap1 = compute_session_recap(summary, memory, policy, "trading")
    recap2 = compute_session_recap(summary, memory, policy, "trading")

    # Serialize and compare
    serialized1 = recap1.serialize()
    serialized2 = recap2.serialize()

    # Verify all fields match
    assert serialized1 == serialized2


# ============================================================================
# HELPER FUNCTION UNIT TESTS
# ============================================================================


def test_compute_net_trajectory_edge_cases():
    """Test edge cases for net trajectory computation."""
    # Empty timeline
    assert _compute_net_trajectory([]) == "ambiguous"

    # Single value
    assert _compute_net_trajectory([0.5]) == "ambiguous"

    # Exactly 0.05 delta (boundary case - should be oscillating since abs(0.05) is NOT < 0.05)
    # Use 0.55 - 0.5 = 0.05
    assert _compute_net_trajectory([0.50, 0.55]) == "oscillating"

    # Less than 0.05 delta (boundary case - should be ambiguous)
    # Use 0.04 difference
    assert _compute_net_trajectory([0.50, 0.54]) == "ambiguous"

    # Above 0.10 delta (should be improving) - use 0.15 to avoid float precision issues
    assert _compute_net_trajectory([0.50, 0.65]) == "improving"

    # Below -0.10 delta (should be declining) - use -0.15 to avoid float precision issues
    assert _compute_net_trajectory([0.65, 0.50]) == "declining"

    # Between 0.05 and 0.10 delta (should be oscillating)
    assert _compute_net_trajectory([0.50, 0.57]) == "oscillating"


def test_build_mapper_journey_edge_cases():
    """Test edge cases for mapper journey building."""
    # Empty list
    assert _build_mapper_journey([]) == []

    # Empty set
    assert _build_mapper_journey([set()]) == ["none"]

    # Multiple mappers
    journey = _build_mapper_journey([{"LAM", "HRM"}])
    assert journey == ["HRM+LAM"]  # Sorted alphabetically


def test_determine_recommended_style_fallback():
    """Test that fallback style logic works when no policy provided."""
    # Stable -> reflective
    assert _determine_recommended_style(None, "stable") == "reflective"

    # Recovering -> exploratory
    assert _determine_recommended_style(None, "recovering") == "exploratory"

    # Fragmented -> grounded
    assert _determine_recommended_style(None, "fragmented") == "grounded"

    # Unknown -> neutral
    assert _determine_recommended_style(None, "unknown") == "neutral"


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
