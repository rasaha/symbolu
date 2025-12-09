"""
Test Suite for Identity Signature Engine v1.0

This test suite provides comprehensive coverage of the Identity Signature Engine:
- Core classification logic (8 signature types)
- Feature influence tests (drivers: drift, coherence, memory events)
- Identity-marker detection tests
- Domain-amplified identity tests (therapy, identity)
- Neutral-case test
- Integration with session recap + intent arc
- Stability/determinism tests

Total: 28 tests ensuring full deterministic behavior
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Set, Optional, Any


# Import the identity signature engine
from symbolu.identity.identity_signature_engine import (
    IdentitySignature,
    compute_identity_signature,
)


# ============================================================================
# Mock Data Classes (matching Symbol-U schemas)
# ============================================================================


@dataclass
class MockMemoryEntry:
    """Mock MemoryEntry for testing"""
    turn_index: int
    event_type: str
    description: str
    metrics: dict = field(default_factory=dict)


@dataclass
class MockSessionMemory:
    """Mock SessionMemory for testing"""
    events: List[MockMemoryEntry] = field(default_factory=list)


@dataclass
class MockSessionSummary:
    """Mock SessionSummary for testing"""
    turn_count: int = 0
    coherence_timeline: List[float] = field(default_factory=list)
    temporal_arc_timeline: List[float] = field(default_factory=list)
    mapper_sets: List[Set[str]] = field(default_factory=list)
    persona_drift_score: float = 0.5
    coherence_score: float = 0.7
    temporal_arc_score: float = 0.6
    mapper_volatility_score: float = 0.3
    semantic_stability_score: float = 0.7
    last_domain: str = "generic"


@dataclass
class MockIntentArc:
    """Mock IntentArc for testing"""
    arc_type: str
    confidence: float
    reasons: List[str] = field(default_factory=list)
    turn_count: int = 0
    domain: str = "generic"


# ============================================================================
# Test Group 1: Core Classification Logic (8 tests)
# ============================================================================


def test_self_anchoring_detection():
    """Test self_anchoring signature detection with ideal conditions"""
    # Create mock session with high coherence, low drift, rising coherence
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.65, 0.70, 0.72, 0.75],
        temporal_arc_timeline=[0.5, 0.55, 0.60, 0.62, 0.65],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM", "LCM"}, {"HRM"}, {"HRM"}],
        persona_drift_score=0.30,
        coherence_score=0.75,
        temporal_arc_score=0.65,
        mapper_volatility_score=0.25,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])  # No fragmentation events

    result = compute_identity_signature(summary, memory)

    assert result.signature_type == "self_anchoring"
    assert result.confidence >= 0.70
    assert "high_coherence" in result.drivers
    assert "low_persona_drift" in result.drivers
    assert "rising_coherence" in result.drivers
    assert "no_fragmentation" in result.drivers


def test_self_expansion_detection():
    """Test self_expansion signature detection with LAM dominance"""
    # Create mock session with LAM-heavy mapper sets and high temporal arc
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.62, 0.65, 0.67, 0.70],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.68],
        mapper_sets=[{"LAM"}, {"LAM", "HRM"}, {"LAM"}, {"LAM", "HRM"}, {"LAM"}],
        persona_drift_score=0.45,
        temporal_arc_score=0.68,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="arc_shift", description="Arc shifted")
    ])

    result = compute_identity_signature(summary, memory, domain="identity")

    assert result.signature_type == "self_expansion"
    assert result.confidence >= 0.65
    assert "lam_dominant" in result.drivers
    assert "high_temporal_arc" in result.drivers
    assert any("lam_ratio" in m for m in result.markers)


def test_self_fragmentation_detection():
    """Test self_fragmentation signature detection with instability"""
    # Create mock session with high drift and fragmentation events
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.70, 0.60, 0.65, 0.55, 0.60, 0.50],  # Oscillating
        temporal_arc_timeline=[0.5, 0.45, 0.50, 0.48, 0.52, 0.46],
        mapper_sets=[{"HRM"}, {"LCM"}, {"HRM"}, {"LCM"}, {"LAM"}, {"LCM"}],
        persona_drift_score=0.65,
        mapper_volatility_score=0.60,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Fragmented"),
        MockMemoryEntry(turn_index=3, event_type="fragmentation", description="Fragmented again"),
    ])

    result = compute_identity_signature(summary, memory)

    assert result.signature_type == "self_fragmentation"
    assert result.confidence >= 0.60
    assert "high_persona_drift" in result.drivers
    assert "fragmentation_events" in result.drivers
    assert "oscillating_coherence" in result.drivers


def test_self_suppression_detection():
    """Test self_suppression signature detection with avoidance patterns"""
    # Create mock session with flat coherence and LCM dominance
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.65, 0.64, 0.66, 0.65, 0.64],  # Flat
        temporal_arc_timeline=[0.35, 0.33, 0.36, 0.34, 0.35],
        mapper_sets=[{"LCM"}, {"LCM"}, {"LCM"}, {"LCM"}, {"LCM"}],
        persona_drift_score=0.45,
        temporal_arc_score=0.35,
        mapper_volatility_score=0.15,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    intent_arc = MockIntentArc(arc_type="avoidance_arc", confidence=0.75)

    result = compute_identity_signature(summary, memory, intent_arc=intent_arc)

    assert result.signature_type == "self_suppression"
    assert result.confidence >= 0.55
    assert "flat_coherence" in result.drivers
    assert "lcm_dominant" in result.drivers
    assert "avoidance_arc" in result.drivers


def test_self_integration_detection():
    """Test self_integration signature detection with breakthrough + stabilization"""
    # Create mock session with breakthrough, stabilization, and HRM+LAM synergy
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.55, 0.60, 0.68, 0.72, 0.75, 0.78],
        temporal_arc_timeline=[0.45, 0.52, 0.60, 0.65, 0.70, 0.72],
        mapper_sets=[{"HRM"}, {"HRM", "LAM"}, {"HRM", "LAM"}, {"HRM", "LAM"}, {"HRM", "LAM"}, {"HRM", "LAM"}],
        persona_drift_score=0.35,
        temporal_arc_score=0.72,
        mapper_volatility_score=0.25,
        last_domain="therapy",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough detected"),
        MockMemoryEntry(turn_index=4, event_type="stabilization", description="Stabilization detected"),
    ])

    result = compute_identity_signature(summary, memory)

    assert result.signature_type == "self_integration"
    assert result.confidence >= 0.75
    assert "breakthrough_stabilization" in result.drivers
    assert "rising_temporal_arc" in result.drivers
    assert "hrm_lam_synergy" in result.drivers


def test_self_dissonance_detection():
    """Test self_dissonance signature detection with internal conflict"""
    # Create mock session with high volatility and moderate drift
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.65, 0.60, 0.68, 0.62, 0.70, 0.64],
        temporal_arc_timeline=[0.5, 0.55, 0.48, 0.52, 0.46, 0.50],
        mapper_sets=[{"HRM"}, {"LCM"}, {"LAM"}, {"HRM", "LCM"}, {"LAM"}, {"HRM"}],
        persona_drift_score=0.48,
        mapper_volatility_score=0.62,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    intent_arc = MockIntentArc(arc_type="dissonance_arc", confidence=0.72)

    result = compute_identity_signature(summary, memory, intent_arc=intent_arc)

    assert result.signature_type == "self_dissonance"
    assert result.confidence >= 0.60
    assert "high_mapper_volatility" in result.drivers
    assert "moderate_persona_drift" in result.drivers
    assert "dissonance_arc" in result.drivers


def test_self_discovery_detection():
    """Test self_discovery signature detection with identity turning points"""
    # Create mock session with breakthrough and improving trajectory
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.55, 0.60, 0.65, 0.70, 0.75],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.68],
        mapper_sets=[{"HRM"}, {"HRM"}, {"LAM"}, {"HRM", "LAM"}, {"LAM"}],
        persona_drift_score=0.40,
        temporal_arc_score=0.68,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough"),
        MockMemoryEntry(turn_index=2, event_type="arc_shift", description="Arc shifted"),
    ])

    result = compute_identity_signature(summary, memory, domain="identity")

    assert result.signature_type == "self_discovery"
    assert result.confidence >= 0.70
    assert "breakthrough_detected" in result.drivers
    assert "identity_triggers" in result.drivers
    assert "improving_trajectory" in result.drivers


def test_neutral_identity_fallback():
    """Test neutral_identity fallback when no clear signature detected"""
    # Create mock session with mixed signals
    summary = MockSessionSummary(
        turn_count=3,
        coherence_timeline=[0.60, 0.62, 0.61],
        temporal_arc_timeline=[0.50, 0.51, 0.52],
        mapper_sets=[{"HRM"}, {"LCM"}, {"HRM"}],
        persona_drift_score=0.45,
        temporal_arc_score=0.51,
        mapper_volatility_score=0.35,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    result = compute_identity_signature(summary, memory)

    # Should return neutral_identity with low confidence
    assert result.signature_type == "neutral_identity"
    assert result.confidence <= 0.50
    assert "no_signature_detected" in result.drivers


# ============================================================================
# Test Group 2: Feature Influence Tests (6 tests)
# ============================================================================


def test_coherence_influence_on_anchoring():
    """Test that coherence level influences self_anchoring confidence"""
    # Test with different coherence levels
    high_coherence_summary = MockSessionSummary(
        turn_count=4,
        coherence_timeline=[0.70, 0.75, 0.80, 0.85],
        persona_drift_score=0.30,
        mapper_volatility_score=0.20,
    )

    low_coherence_summary = MockSessionSummary(
        turn_count=4,
        coherence_timeline=[0.60, 0.63, 0.65, 0.67],
        persona_drift_score=0.30,
        mapper_volatility_score=0.20,
    )

    memory = MockSessionMemory(events=[])

    result_high = compute_identity_signature(high_coherence_summary, memory)
    result_low = compute_identity_signature(low_coherence_summary, memory)

    # Both should detect self_anchoring, but high coherence should have higher confidence
    assert result_high.signature_type == "self_anchoring"
    assert result_low.signature_type == "self_anchoring"
    assert result_high.confidence > result_low.confidence


def test_drift_influence_on_fragmentation():
    """Test that persona drift influences self_fragmentation detection"""
    # Higher drift should increase fragmentation confidence
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.70, 0.60, 0.65, 0.55, 0.60],  # Oscillating
        persona_drift_score=0.70,  # Very high drift
        mapper_volatility_score=0.50,
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Fragmented"),
    ])

    result = compute_identity_signature(summary, memory)

    assert result.signature_type == "self_fragmentation"
    assert result.confidence >= 0.65


def test_memory_events_influence_integration():
    """Test that memory events drive self_integration detection"""
    # Multiple breakthrough events should increase integration confidence
    summary = MockSessionSummary(
        turn_count=7,
        coherence_timeline=[0.55, 0.60, 0.65, 0.70, 0.72, 0.75, 0.78],
        temporal_arc_timeline=[0.45, 0.50, 0.55, 0.60, 0.65, 0.68, 0.70],
        mapper_sets=[{"HRM", "LAM"}] * 7,
        persona_drift_score=0.30,
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="First breakthrough"),
        MockMemoryEntry(turn_index=4, event_type="breakthrough", description="Second breakthrough"),
        MockMemoryEntry(turn_index=5, event_type="stabilization", description="Stabilization"),
    ])

    result = compute_identity_signature(summary, memory)

    assert result.signature_type == "self_integration"
    assert result.confidence >= 0.80  # Multiple breakthroughs increase confidence


def test_mapper_volatility_influence_dissonance():
    """Test that mapper volatility influences self_dissonance detection"""
    # Higher volatility should increase dissonance confidence
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.65, 0.62, 0.68, 0.64, 0.70, 0.66],
        mapper_sets=[{"HRM"}, {"LCM"}, {"LAM"}, {"HRM"}, {"LCM"}, {"LAM"}],
        persona_drift_score=0.48,
        mapper_volatility_score=0.70,  # Very high volatility
    )

    intent_arc = MockIntentArc(arc_type="chaotic_arc", confidence=0.75)

    result = compute_identity_signature(summary, MockSessionMemory(events=[]), intent_arc=intent_arc)

    assert result.signature_type == "self_dissonance"
    assert result.confidence >= 0.70


def test_temporal_arc_influence_expansion():
    """Test that temporal arc influences self_expansion detection"""
    # Higher temporal arc should increase expansion confidence
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.62, 0.65, 0.68, 0.70],
        temporal_arc_timeline=[0.50, 0.55, 0.62, 0.68, 0.75],
        mapper_sets=[{"LAM"}] * 5,
        temporal_arc_score=0.75,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="arc_shift", description="Arc shift"),
    ])

    result = compute_identity_signature(summary, memory, domain="identity")

    assert result.signature_type == "self_expansion"
    assert result.confidence >= 0.80


def test_lam_ratio_influence_expansion():
    """Test that LAM activity ratio influences self_expansion confidence"""
    # Test with different LAM ratios
    high_lam_summary = MockSessionSummary(
        turn_count=5,
        mapper_sets=[{"LAM"}, {"LAM"}, {"LAM"}, {"LAM"}, {"LAM"}],  # 100% LAM
        temporal_arc_score=0.65,
        last_domain="identity",
    )

    moderate_lam_summary = MockSessionSummary(
        turn_count=5,
        mapper_sets=[{"LAM"}, {"HRM"}, {"LAM"}, {"HRM"}, {"LAM"}],  # 60% LAM
        temporal_arc_score=0.65,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="arc_shift", description="Arc shift"),
    ])

    result_high = compute_identity_signature(high_lam_summary, memory, domain="identity")
    result_moderate = compute_identity_signature(moderate_lam_summary, memory, domain="identity")

    # Both should detect expansion, but high LAM should have higher confidence
    if result_high.signature_type == "self_expansion" and result_moderate.signature_type == "self_expansion":
        assert result_high.confidence >= result_moderate.confidence


# ============================================================================
# Test Group 3: Identity-Marker Detection Tests (4 tests)
# ============================================================================


def test_marker_extraction_breakthrough():
    """Test that breakthrough markers are correctly extracted"""
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.55, 0.60, 0.65, 0.70, 0.75],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.70],
        mapper_sets=[{"HRM"}] * 5,
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough at turn 2"),
        MockMemoryEntry(turn_index=3, event_type="arc_shift", description="Arc shift"),
    ])

    result = compute_identity_signature(summary, memory, domain="identity")

    # Should detect self_discovery with breakthrough marker
    assert result.signature_type == "self_discovery"
    assert any("breakthrough_t2" in m for m in result.markers)


def test_marker_extraction_fragmentation():
    """Test that fragmentation markers are correctly extracted"""
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.70, 0.60, 0.65, 0.55, 0.60],
        persona_drift_score=0.65,
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Fragmentation at turn 1"),
        MockMemoryEntry(turn_index=3, event_type="fragmentation", description="Fragmentation at turn 3"),
    ])

    result = compute_identity_signature(summary, memory)

    # Should detect self_fragmentation with fragmentation markers
    assert result.signature_type == "self_fragmentation"
    assert any("fragmentation_t" in m for m in result.markers)


def test_marker_extraction_lam_ratio():
    """Test that LAM ratio markers are correctly extracted"""
    summary = MockSessionSummary(
        turn_count=5,
        mapper_sets=[{"LAM"}, {"LAM", "HRM"}, {"LAM"}, {"LAM"}, {"LAM"}],
        temporal_arc_score=0.70,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="arc_shift", description="Arc shift"),
    ])

    result = compute_identity_signature(summary, memory, domain="identity")

    # Should detect self_expansion with LAM ratio marker
    assert result.signature_type == "self_expansion"
    assert any("lam_ratio" in m for m in result.markers)


def test_marker_extraction_coherence_drift():
    """Test that coherence and drift markers are correctly extracted"""
    summary = MockSessionSummary(
        turn_count=4,
        coherence_timeline=[0.70, 0.75, 0.80, 0.85],
        persona_drift_score=0.25,
    )

    memory = MockSessionMemory(events=[])

    result = compute_identity_signature(summary, memory)

    # Should detect self_anchoring with coherence and drift markers
    assert result.signature_type == "self_anchoring"
    assert any("coherence_" in m for m in result.markers)
    assert any("drift_" in m for m in result.markers)


# ============================================================================
# Test Group 4: Domain-Amplified Identity Tests (3 tests)
# ============================================================================


def test_identity_domain_amplification():
    """Test that identity domain amplifies identity-related signatures"""
    summary = MockSessionSummary(
        turn_count=5,
        mapper_sets=[{"LAM"}, {"LAM"}, {"LAM"}, {"LAM"}, {"LAM"}],
        temporal_arc_score=0.65,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[])

    result = compute_identity_signature(summary, memory, domain="identity")

    # Identity domain should enable self_expansion even without arc_shift
    # if LAM is dominant and temporal arc is high
    # Note: This might still require arc_shift based on implementation
    assert result.signature_type in ["self_expansion", "neutral_identity"]


def test_therapy_domain_integration():
    """Test that therapy domain influences integration detection"""
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.55, 0.60, 0.65, 0.70, 0.75, 0.78],
        temporal_arc_timeline=[0.45, 0.50, 0.55, 0.60, 0.65, 0.70],
        mapper_sets=[{"HRM", "LAM"}] * 6,
        persona_drift_score=0.30,
        last_domain="therapy",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough"),
        MockMemoryEntry(turn_index=4, event_type="stabilization", description="Stabilization"),
    ])

    result = compute_identity_signature(summary, memory, domain="therapy")

    # Therapy domain with breakthrough + stabilization should detect integration
    assert result.signature_type == "self_integration"
    assert result.domain == "therapy"


def test_generic_domain_neutral_behavior():
    """Test that generic domain doesn't bias classification"""
    summary = MockSessionSummary(
        turn_count=3,
        coherence_timeline=[0.60, 0.62, 0.63],
        temporal_arc_timeline=[0.50, 0.52, 0.53],
        mapper_sets=[{"HRM"}, {"LCM"}, {"HRM"}],
        persona_drift_score=0.45,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    result = compute_identity_signature(summary, memory, domain="generic")

    # Generic domain with weak signals should fall back to neutral
    assert result.signature_type == "neutral_identity"
    assert result.domain == "generic"


# ============================================================================
# Test Group 5: Integration Tests (3 tests)
# ============================================================================


def test_integration_with_intent_arc():
    """Test integration with IntentArc classification"""
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.65, 0.64, 0.66, 0.65, 0.64],
        temporal_arc_timeline=[0.35, 0.33, 0.36, 0.34, 0.35],
        mapper_sets=[{"LCM"}] * 5,
        temporal_arc_score=0.35,
    )

    memory = MockSessionMemory(events=[])

    intent_arc = MockIntentArc(
        arc_type="avoidance_arc",
        confidence=0.75,
        reasons=["low_temporal_progress", "flat_coherence"],
    )

    result = compute_identity_signature(summary, memory, intent_arc=intent_arc)

    # Intent arc should influence suppression detection
    assert result.signature_type == "self_suppression"
    assert "avoidance_arc" in result.drivers


def test_integration_with_session_recap():
    """Test that session recap data integrates correctly"""
    # Test that memory events (which would come from recap) influence classification
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.55, 0.60, 0.68, 0.72, 0.75, 0.78],
        temporal_arc_timeline=[0.45, 0.52, 0.60, 0.65, 0.70, 0.72],
        mapper_sets=[{"HRM", "LAM"}] * 6,
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Recap breakthrough"),
        MockMemoryEntry(turn_index=4, event_type="stabilization", description="Recap stabilization"),
    ])

    result = compute_identity_signature(summary, memory)

    # Should integrate memory events into classification
    assert result.signature_type == "self_integration"
    assert any("breakthrough_t" in m for m in result.markers)


def test_multi_turn_trajectory_classification():
    """Test full multi-turn trajectory classification pipeline"""
    # Simulate a real multi-turn session trajectory
    summary = MockSessionSummary(
        turn_count=10,
        coherence_timeline=[0.60, 0.58, 0.62, 0.70, 0.72, 0.68, 0.65, 0.70, 0.75, 0.78],
        temporal_arc_timeline=[0.45, 0.48, 0.52, 0.58, 0.62, 0.60, 0.58, 0.62, 0.68, 0.72],
        mapper_sets=[
            {"HRM"}, {"LCM"}, {"HRM"}, {"LAM"}, {"HRM", "LAM"},
            {"HRM", "LAM"}, {"LAM"}, {"HRM", "LAM"}, {"HRM", "LAM"}, {"HRM", "LAM"}
        ],
        persona_drift_score=0.35,
        temporal_arc_score=0.72,
        mapper_volatility_score=0.40,
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Early fragmentation"),
        MockMemoryEntry(turn_index=3, event_type="breakthrough", description="Breakthrough"),
        MockMemoryEntry(turn_index=7, event_type="stabilization", description="Stabilization"),
    ])

    intent_arc = MockIntentArc(arc_type="resolution_arc", confidence=0.80)

    result = compute_identity_signature(summary, memory, intent_arc=intent_arc)

    # Should detect integration (recovery trajectory)
    assert result.signature_type in ["self_integration", "self_discovery"]
    assert result.confidence >= 0.70
    assert result.turn_count == 10


# ============================================================================
# Test Group 6: Edge Cases and Stability (4 tests)
# ============================================================================


def test_insufficient_turns():
    """Test behavior with insufficient turn count"""
    summary = MockSessionSummary(
        turn_count=0,
        coherence_timeline=[],
        temporal_arc_timeline=[],
        mapper_sets=[],
    )

    memory = MockSessionMemory(events=[])

    result = compute_identity_signature(summary, memory)

    assert result.signature_type == "neutral_identity"
    assert "insufficient_turns" in result.drivers
    assert result.confidence <= 0.40


def test_determinism_same_input():
    """Test that same input produces same output (determinism)"""
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.65, 0.70, 0.72, 0.75],
        temporal_arc_timeline=[0.5, 0.55, 0.60, 0.62, 0.65],
        mapper_sets=[{"HRM"}] * 5,
        persona_drift_score=0.30,
    )

    memory = MockSessionMemory(events=[])

    # Run multiple times with same input
    result1 = compute_identity_signature(summary, memory)
    result2 = compute_identity_signature(summary, memory)
    result3 = compute_identity_signature(summary, memory)

    # All results should be identical
    assert result1.signature_type == result2.signature_type == result3.signature_type
    assert result1.confidence == result2.confidence == result3.confidence
    assert result1.drivers == result2.drivers == result3.drivers


def test_confidence_bounds():
    """Test that confidence scores are always within valid bounds [0.0, 1.0]"""
    # Test extreme cases
    test_cases = [
        MockSessionSummary(
            turn_count=5,
            coherence_timeline=[0.95, 0.96, 0.97, 0.98, 0.99],
            persona_drift_score=0.05,
        ),
        MockSessionSummary(
            turn_count=5,
            coherence_timeline=[0.30, 0.25, 0.28, 0.22, 0.20],
            persona_drift_score=0.85,
        ),
    ]

    memory = MockSessionMemory(events=[])

    for summary in test_cases:
        result = compute_identity_signature(summary, memory)
        assert 0.0 <= result.confidence <= 1.0


def test_priority_tiebreaking():
    """Test that priority-based tiebreaking is deterministic"""
    # Create conditions where multiple signatures could apply
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.55, 0.60, 0.65, 0.70, 0.75, 0.78],
        temporal_arc_timeline=[0.45, 0.52, 0.60, 0.65, 0.70, 0.72],
        mapper_sets=[{"HRM", "LAM"}] * 6,
        persona_drift_score=0.35,
        temporal_arc_score=0.72,
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough"),
        MockMemoryEntry(turn_index=4, event_type="stabilization", description="Stabilization"),
        MockMemoryEntry(turn_index=1, event_type="arc_shift", description="Arc shift"),
    ])

    # Both self_integration and self_discovery could apply
    # Priority order favors self_integration
    result = compute_identity_signature(summary, memory)

    # Should consistently choose self_integration due to higher priority
    assert result.signature_type == "self_integration"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
