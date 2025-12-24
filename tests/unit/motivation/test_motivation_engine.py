"""
Test Suite for Motivation Flow Engine v1.0

This test suite provides comprehensive coverage of the Motivation Flow Engine:
- Core classification logic (8 motivation types)
- Mixed-signal classification tests
- Integration with session components (SessionSummary, SessionMemory, IntentArc, IdentitySignature)
- Stability/determinism tests
- Edge case handling

Total: 28 tests ensuring full deterministic behavior
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Set, Optional, Any


# Import the motivation flow engine
from symbolu.motivation.motivation_engine import (
    MotivationProfile,
    compute_motivation_flow,
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
class MockSessionPolicyFlags:
    """Mock SessionPolicyFlags for testing"""
    needs_grounding: bool = False
    allow_deep_reflection: bool = False
    prefer_concrete: bool = False
    prefer_arc_mode: bool = False


@dataclass
class MockIntentArc:
    """Mock IntentArc for testing"""
    arc_type: str
    confidence: float
    reasons: List[str] = field(default_factory=list)
    turn_count: int = 0
    domain: str = "generic"


@dataclass
class MockIdentitySignature:
    """Mock IdentitySignature for testing"""
    signature_type: str
    confidence: float
    drivers: List[str] = field(default_factory=list)
    markers: List[str] = field(default_factory=list)
    turn_count: int = 0
    domain: str = "generic"


# ============================================================================
# Test Group 1: Core Classification Logic (8 tests - one per motivation type)
# ============================================================================


def test_hope_driven_detection():
    """Test hope_driven motivation with upward trajectory and breakthrough"""
    # Create mock session with upward coherence, breakthrough events, low volatility
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.55, 0.60, 0.65, 0.70, 0.75],  # Strong upward trajectory
        temporal_arc_timeline=[0.50, 0.55, 0.58, 0.60, 0.63],
        mapper_sets=[{"HRM"}, {"HRM", "LAM"}, {"HRM"}, {"HRM", "LAM"}, {"HRM"}],
        mapper_volatility_score=0.30,  # Low volatility
        last_domain="therapy",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough moment"),
        MockMemoryEntry(turn_index=4, event_type="breakthrough", description="Another breakthrough"),
    ])

    result = compute_motivation_flow(summary, memory)

    assert result.motivation_type == "hope_driven"
    assert result.confidence >= 0.75
    assert "upward_coherence" in result.drivers
    assert "breakthrough_events" in result.drivers
    assert "low_volatility" in result.drivers
    assert any("coherence_delta" in m for m in result.markers)
    assert any("breakthrough_t2" in m for m in result.markers)


def test_fear_driven_detection():
    """Test fear_driven motivation with fragmentation and high volatility"""
    # Create mock session with fragmentation, high volatility, defensive patterns
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.60, 0.55, 0.50, 0.52, 0.48, 0.45],
        temporal_arc_timeline=[0.50, 0.48, 0.45, 0.46, 0.44, 0.42],
        mapper_sets=[{"LCM"}, {"LCM"}, {"LCM"}, {"LCM", "HRM"}, {"LCM"}, {"LCM"}],  # LCM dominant
        mapper_volatility_score=0.65,  # High volatility
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Fragmented"),
        MockMemoryEntry(turn_index=3, event_type="fragmentation", description="More fragmentation"),
    ])

    intent_arc = MockIntentArc(arc_type="dissonance_arc", confidence=0.75)

    result = compute_motivation_flow(summary, memory, intent_arc=intent_arc)

    assert result.motivation_type == "fear_driven"
    assert result.confidence >= 0.65
    assert "fragmentation_events" in result.drivers
    assert "high_volatility" in result.drivers
    assert "defensive_patterns" in result.drivers


def test_avoidance_driven_detection():
    """Test avoidance_driven motivation with flat coherence and LCM bias"""
    # Create mock session with flat coherence, LCM bias, prefer_concrete
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.62, 0.63, 0.62, 0.63, 0.62],  # Very flat
        temporal_arc_timeline=[0.35, 0.36, 0.35, 0.36, 0.35],
        mapper_sets=[{"LCM"}, {"LCM"}, {"LCM", "HRM"}, {"LCM"}, {"LCM"}],  # LCM dominant
        mapper_volatility_score=0.25,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    policy = MockSessionPolicyFlags(prefer_concrete=True)

    intent_arc = MockIntentArc(arc_type="avoidance_arc", confidence=0.70)

    result = compute_motivation_flow(summary, memory, session_policy=policy, intent_arc=intent_arc)

    assert result.motivation_type == "avoidance_driven"
    assert result.confidence >= 0.60
    assert "flat_coherence" in result.drivers
    assert "lcm_bias" in result.drivers
    assert "suppressed_expression" in result.drivers or "avoidance_arc" in result.drivers


def test_expansion_driven_detection():
    """Test expansion_driven motivation with LAM activity and rising temporal arc"""
    # Create mock session with LAM dominance, rising temporal arc, identity expansion
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.62, 0.65, 0.67, 0.70],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.70],  # Strong rise
        mapper_sets=[{"LAM"}, {"LAM", "HRM"}, {"LAM"}, {"LAM", "HRM"}, {"LAM"}],  # LAM dominant
        mapper_volatility_score=0.35,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="arc_shift", description="Arc shifted"),
    ])

    identity_sig = MockIdentitySignature(signature_type="self_expansion", confidence=0.85)

    result = compute_motivation_flow(summary, memory, identity_signature=identity_sig)

    assert result.motivation_type == "expansion_driven"
    assert result.confidence >= 0.70
    assert "lam_active" in result.drivers
    assert "rising_temporal_arc" in result.drivers
    assert "identity_expansion" in result.drivers or "arc_shift_events" in result.drivers


def test_stabilization_driven_detection():
    """Test stabilization_driven motivation with recovery pattern"""
    # Create mock session with valley pattern and stabilization
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.70, 0.60, 0.55, 0.58, 0.62, 0.65],  # Valley pattern
        temporal_arc_timeline=[0.60, 0.55, 0.52, 0.55, 0.58, 0.60],
        mapper_sets=[{"HRM"}, {"HRM", "LCM"}, {"LCM"}, {"HRM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.30,  # Low volatility
        last_domain="therapy",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=3, event_type="stabilization", description="Stabilizing"),
        MockMemoryEntry(turn_index=5, event_type="stabilization", description="More stabilization"),
    ])

    result = compute_motivation_flow(summary, memory)

    assert result.motivation_type == "stabilization_driven"
    assert result.confidence >= 0.70
    assert "stabilization_events" in result.drivers
    assert "recovery_pattern" in result.drivers
    assert "low_volatility" in result.drivers
    assert "no_recent_fragmentation" in result.drivers


def test_overcorrection_detection():
    """Test overcorrection motivation with oscillations and rapid flips"""
    # Create mock session with sharp oscillations and mapper flips
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.70, 0.60, 0.68, 0.58, 0.66, 0.56],  # Strong oscillations
        temporal_arc_timeline=[0.55, 0.50, 0.54, 0.49, 0.53, 0.48],
        mapper_sets=[{"HRM"}, {"LCM"}, {"HRM", "LAM"}, {"LCM"}, {"LAM"}, {"LCM"}],
        mapper_volatility_score=0.70,  # Very high volatility
        persona_drift_score=0.55,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="mapper_flip", description="Flipped to LCM"),
        MockMemoryEntry(turn_index=2, event_type="mapper_flip", description="Flipped to HRM"),
        MockMemoryEntry(turn_index=4, event_type="mapper_flip", description="Flipped to LAM"),
    ])

    result = compute_motivation_flow(summary, memory)

    assert result.motivation_type == "overcorrection"
    assert result.confidence >= 0.65
    assert "sharp_oscillations" in result.drivers
    assert "rapid_mapper_flips" in result.drivers
    assert "high_volatility" in result.drivers


def test_assertion_driven_detection():
    """Test assertion_driven motivation with HRM dominance and high coherence"""
    # Create mock session with HRM dominance, high coherence, low drift
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.68, 0.70, 0.72, 0.74, 0.76],
        temporal_arc_timeline=[0.55, 0.57, 0.59, 0.61, 0.63],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM", "LAM"}, {"HRM"}],  # HRM dominant
        persona_drift_score=0.25,  # Low drift
        temporal_arc_score=0.63,  # No avoidance
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    result = compute_motivation_flow(summary, memory)

    assert result.motivation_type == "assertion_driven"
    assert result.confidence >= 0.70
    assert "hrm_dominant" in result.drivers
    assert "high_coherence" in result.drivers
    assert "low_drift" in result.drivers
    assert "no_avoidance" in result.drivers


def test_ambiguous_motivation_fallback():
    """Test ambiguous_motivation fallback when no clear pattern"""
    # Create mock session with mixed signals and no clear pattern
    summary = MockSessionSummary(
        turn_count=3,
        coherence_timeline=[0.60, 0.62, 0.61],  # Minimal change
        temporal_arc_timeline=[0.50, 0.51, 0.50],
        mapper_sets=[{"HRM"}, {"LCM"}, {"LAM"}],
        mapper_volatility_score=0.45,
        persona_drift_score=0.45,
        temporal_arc_score=0.50,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    result = compute_motivation_flow(summary, memory)

    assert result.motivation_type == "ambiguous_motivation"
    assert "no_motivation_detected" in result.drivers


# ============================================================================
# Test Group 2: Mixed Signal Tests (8 tests)
# ============================================================================


def test_hope_vs_stabilization_prioritization():
    """Test that hope_driven wins over stabilization_driven when both qualify"""
    # Create conditions that satisfy both hope and stabilization
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.55, 0.50, 0.52, 0.60, 0.68, 0.75],  # Valley + strong rise
        temporal_arc_timeline=[0.50, 0.48, 0.50, 0.55, 0.60, 0.65],
        mapper_sets=[{"HRM"}, {"LCM"}, {"HRM"}, {"HRM", "LAM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.35,  # Low volatility
        last_domain="therapy",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=3, event_type="stabilization", description="Stabilizing"),
        MockMemoryEntry(turn_index=4, event_type="breakthrough", description="Breakthrough"),
    ])

    result = compute_motivation_flow(summary, memory)

    # hope_driven has higher priority than stabilization_driven
    assert result.motivation_type == "hope_driven"
    assert result.confidence >= 0.75


def test_fear_vs_avoidance_with_fragmentation():
    """Test that fear_driven wins over avoidance when fragmentation present"""
    # Create conditions that could satisfy both
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.61, 0.60, 0.61, 0.60],  # Flat
        temporal_arc_timeline=[0.35, 0.36, 0.35, 0.36, 0.35],
        mapper_sets=[{"LCM"}, {"LCM"}, {"LCM"}, {"LCM"}, {"LCM"}],  # LCM dominant
        mapper_volatility_score=0.60,  # High enough for fear
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="fragmentation", description="Fragmented"),
    ])

    policy = MockSessionPolicyFlags(prefer_concrete=True)
    intent_arc = MockIntentArc(arc_type="avoidance_arc", confidence=0.70)

    result = compute_motivation_flow(summary, memory, session_policy=policy, intent_arc=intent_arc)

    # fear_driven should be detected due to fragmentation + high volatility
    assert result.motivation_type == "fear_driven"


def test_expansion_vs_assertion_with_lam():
    """Test expansion_driven vs assertion_driven when LAM is active"""
    # Create conditions with both LAM and HRM
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.68, 0.70, 0.72, 0.74, 0.76],
        temporal_arc_timeline=[0.55, 0.60, 0.63, 0.66, 0.70],  # Strong rise
        mapper_sets=[{"HRM", "LAM"}, {"HRM", "LAM"}, {"LAM"}, {"HRM", "LAM"}, {"LAM"}],
        persona_drift_score=0.30,
        temporal_arc_score=0.70,
        mapper_volatility_score=0.30,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="arc_shift", description="Arc shifted"),
    ])

    identity_sig = MockIdentitySignature(signature_type="self_expansion", confidence=0.85)

    result = compute_motivation_flow(summary, memory, identity_signature=identity_sig)

    # expansion_driven should win with LAM > 40%, rising arc, and identity expansion
    assert result.motivation_type == "expansion_driven"


def test_overcorrection_vs_fear_with_high_volatility():
    """Test overcorrection vs fear_driven when both have high volatility"""
    # Create conditions with high volatility but different patterns
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.70, 0.55, 0.68, 0.52, 0.66, 0.50],  # Oscillating
        temporal_arc_timeline=[0.50, 0.45, 0.49, 0.44, 0.48, 0.43],
        mapper_sets=[{"HRM"}, {"LCM"}, {"LAM"}, {"HRM"}, {"LCM"}, {"LAM"}],
        mapper_volatility_score=0.75,  # Very high
        persona_drift_score=0.50,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="mapper_flip", description="Flip 1"),
        MockMemoryEntry(turn_index=2, event_type="mapper_flip", description="Flip 2"),
        MockMemoryEntry(turn_index=4, event_type="mapper_flip", description="Flip 3"),
    ])

    result = compute_motivation_flow(summary, memory)

    # overcorrection should win due to oscillations + rapid flips
    assert result.motivation_type == "overcorrection"


def test_stabilization_requires_valley_pattern():
    """Test that stabilization requires actual valley, not just stabilization events"""
    # Create mock with stabilization events but NO valley pattern
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.62, 0.64, 0.66, 0.68],  # Steady rise, no valley
        temporal_arc_timeline=[0.50, 0.52, 0.54, 0.56, 0.58],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.25,  # Low volatility
        last_domain="therapy",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=3, event_type="stabilization", description="Stabilizing"),
    ])

    result = compute_motivation_flow(summary, memory)

    # Should NOT be stabilization_driven (no valley pattern)
    # Might be hope_driven or another type
    assert result.motivation_type != "stabilization_driven"


def test_assertion_blocked_by_low_temporal_arc():
    """Test that assertion_driven requires temporal_arc > 0.45 (no avoidance)"""
    # Create mock with HRM dominance but low temporal arc
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.68, 0.70, 0.72, 0.74, 0.76],
        temporal_arc_timeline=[0.35, 0.36, 0.37, 0.38, 0.39],  # Low temporal arc
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],  # HRM dominant
        persona_drift_score=0.25,  # Low drift
        temporal_arc_score=0.39,  # Below threshold
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    result = compute_motivation_flow(summary, memory)

    # Should NOT be assertion_driven (temporal arc too low = avoidance pattern)
    assert result.motivation_type != "assertion_driven"


def test_expansion_requires_lam_threshold():
    """Test that expansion_driven requires LAM > 40%"""
    # Create mock with rising temporal arc but insufficient LAM
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.62, 0.65, 0.67, 0.70],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.70],  # Strong rise
        mapper_sets=[{"HRM"}, {"HRM", "LAM"}, {"HRM"}, {"HRM"}, {"HRM"}],  # Only 20% LAM
        mapper_volatility_score=0.30,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[])

    identity_sig = MockIdentitySignature(signature_type="self_expansion", confidence=0.85)

    result = compute_motivation_flow(summary, memory, identity_signature=identity_sig)

    # Should NOT be expansion_driven (LAM ratio too low)
    assert result.motivation_type != "expansion_driven"


def test_hope_requires_coherence_threshold():
    """Test that hope_driven requires coherence delta > 0.12"""
    # Create mock with breakthrough but insufficient coherence rise
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.62, 0.64, 0.66, 0.68],  # Only 0.08 delta
        temporal_arc_timeline=[0.50, 0.52, 0.54, 0.56, 0.58],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.30,  # Low volatility
        last_domain="therapy",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=3, event_type="breakthrough", description="Breakthrough"),
    ])

    result = compute_motivation_flow(summary, memory)

    # Should NOT be hope_driven (coherence delta too small)
    assert result.motivation_type != "hope_driven"


# ============================================================================
# Test Group 3: Integration Tests (5 tests)
# ============================================================================


def test_full_integration_with_all_components():
    """Test motivation computation with all session components present"""
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.55, 0.60, 0.65, 0.70, 0.75, 0.80],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.70, 0.75],
        mapper_sets=[{"HRM"}, {"HRM", "LAM"}, {"LAM"}, {"LAM", "HRM"}, {"LAM"}, {"LAM"}],
        mapper_volatility_score=0.35,
        persona_drift_score=0.40,
        temporal_arc_score=0.75,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough 1"),
        MockMemoryEntry(turn_index=4, event_type="arc_shift", description="Arc shift"),
        MockMemoryEntry(turn_index=5, event_type="breakthrough", description="Breakthrough 2"),
    ])

    policy = MockSessionPolicyFlags(allow_deep_reflection=True)
    intent_arc = MockIntentArc(arc_type="expansion_arc", confidence=0.85)
    identity_sig = MockIdentitySignature(signature_type="self_expansion", confidence=0.90)

    result = compute_motivation_flow(
        summary,
        memory,
        session_policy=policy,
        intent_arc=intent_arc,
        identity_signature=identity_sig,
    )

    # Should detect strong positive motivation (hope or expansion)
    assert result.motivation_type in ["hope_driven", "expansion_driven"]
    assert result.confidence >= 0.70
    assert result.turn_count == 6
    assert result.domain == "identity"


def test_integration_with_minimal_components():
    """Test motivation computation with minimal session components"""
    summary = MockSessionSummary(
        turn_count=3,
        coherence_timeline=[0.60, 0.62, 0.64],
        temporal_arc_timeline=[0.50, 0.51, 0.52],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.30,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    result = compute_motivation_flow(summary, memory)

    # Should return some classification even with minimal data
    assert result.motivation_type is not None
    assert 0.0 <= result.confidence <= 1.0
    assert isinstance(result.drivers, list)
    assert isinstance(result.markers, list)


def test_integration_with_therapy_domain_amplification():
    """Test that therapy domain amplifies stabilization patterns"""
    summary = MockSessionSummary(
        turn_count=6,
        coherence_timeline=[0.70, 0.60, 0.55, 0.58, 0.62, 0.65],  # Valley pattern
        temporal_arc_timeline=[0.60, 0.55, 0.52, 0.55, 0.58, 0.60],
        mapper_sets=[{"HRM"}, {"HRM", "LCM"}, {"LCM"}, {"HRM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.30,
        last_domain="therapy",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=3, event_type="stabilization", description="Stabilizing"),
        MockMemoryEntry(turn_index=5, event_type="stabilization", description="More stabilization"),
    ])

    result = compute_motivation_flow(summary, memory)

    assert result.motivation_type == "stabilization_driven"
    assert result.domain == "therapy"


def test_integration_serialization():
    """Test that MotivationProfile can be serialized to JSON"""
    summary = MockSessionSummary(
        turn_count=4,
        coherence_timeline=[0.60, 0.65, 0.70, 0.75],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.30,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough"),
    ])

    result = compute_motivation_flow(summary, memory)

    # Test serialization
    serialized = result.serialize()

    assert isinstance(serialized, dict)
    assert "motivation_type" in serialized
    assert "confidence" in serialized
    assert "drivers" in serialized
    assert "markers" in serialized
    assert "turn_count" in serialized
    assert "domain" in serialized


def test_integration_with_identity_signature_cross_validation():
    """Test that motivation aligns with identity signature when present"""
    # self_expansion identity should correlate with expansion_driven motivation
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.62, 0.65, 0.67, 0.70],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.70],  # Strong rise
        mapper_sets=[{"LAM"}, {"LAM", "HRM"}, {"LAM"}, {"LAM"}, {"LAM"}],  # LAM dominant
        mapper_volatility_score=0.35,
        temporal_arc_score=0.70,
        last_domain="identity",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="arc_shift", description="Arc shifted"),
    ])

    identity_sig = MockIdentitySignature(signature_type="self_expansion", confidence=0.85)

    result = compute_motivation_flow(summary, memory, identity_signature=identity_sig)

    # Expansion identity should align with expansion motivation
    assert result.motivation_type == "expansion_driven"
    assert "identity_expansion" in result.drivers


# ============================================================================
# Test Group 4: Stability and Determinism Tests (3 tests)
# ============================================================================


def test_determinism_same_input_same_output():
    """Test that same input produces same output (determinism)"""
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.65, 0.70, 0.75, 0.80],
        temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.70],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.30,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough"),
    ])

    # Run 5 times and check results are identical
    results = [compute_motivation_flow(summary, memory) for _ in range(5)]

    # All results should be identical
    for i in range(1, len(results)):
        assert results[i].motivation_type == results[0].motivation_type
        assert results[i].confidence == results[0].confidence
        assert results[i].drivers == results[0].drivers
        assert results[i].markers == results[0].markers


def test_confidence_bounds():
    """Test that all confidence scores are within valid range [0.0, 1.0]"""
    # Test various scenarios
    test_scenarios = [
        # Scenario 1: Hope driven
        (
            MockSessionSummary(
                turn_count=5,
                coherence_timeline=[0.55, 0.60, 0.65, 0.70, 0.75],
                temporal_arc_timeline=[0.50, 0.55, 0.60, 0.65, 0.70],
                mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],
                mapper_volatility_score=0.30,
            ),
            MockSessionMemory(events=[
                MockMemoryEntry(turn_index=2, event_type="breakthrough", description="Breakthrough"),
            ]),
        ),
        # Scenario 2: Fear driven
        (
            MockSessionSummary(
                turn_count=5,
                coherence_timeline=[0.60, 0.55, 0.50, 0.48, 0.45],
                temporal_arc_timeline=[0.50, 0.45, 0.40, 0.38, 0.35],
                mapper_sets=[{"LCM"}, {"LCM"}, {"LCM"}, {"LCM"}, {"LCM"}],
                mapper_volatility_score=0.70,
            ),
            MockSessionMemory(events=[
                MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Fragmented"),
            ]),
        ),
        # Scenario 3: Ambiguous
        (
            MockSessionSummary(
                turn_count=2,
                coherence_timeline=[0.60, 0.61],
                temporal_arc_timeline=[0.50, 0.51],
                mapper_sets=[{"HRM"}, {"LCM"}],
                mapper_volatility_score=0.45,
            ),
            MockSessionMemory(events=[]),
        ),
    ]

    for summary, memory in test_scenarios:
        result = compute_motivation_flow(summary, memory)
        assert 0.0 <= result.confidence <= 1.0, f"Confidence {result.confidence} out of bounds"


def test_edge_case_insufficient_turns():
    """Test handling of edge case with insufficient turns"""
    summary = MockSessionSummary(
        turn_count=0,
        coherence_timeline=[],
        temporal_arc_timeline=[],
        mapper_sets=[],
        mapper_volatility_score=0.5,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    result = compute_motivation_flow(summary, memory)

    assert result.motivation_type == "ambiguous_motivation"
    assert "insufficient_turns" in result.drivers
    assert result.confidence > 0.0  # Should have some minimal confidence


# ============================================================================
# Test Group 5: Edge Case Tests (4 additional tests)
# ============================================================================


def test_edge_case_single_turn():
    """Test handling of single-turn session"""
    summary = MockSessionSummary(
        turn_count=1,
        coherence_timeline=[0.70],
        temporal_arc_timeline=[0.60],
        mapper_sets=[{"HRM"}],
        mapper_volatility_score=0.30,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    result = compute_motivation_flow(summary, memory)

    # Should return some classification, likely ambiguous due to insufficient data
    assert result.motivation_type is not None
    assert result.turn_count == 1


def test_edge_case_empty_memory():
    """Test handling of empty session memory"""
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.60, 0.62, 0.64, 0.66, 0.68],
        temporal_arc_timeline=[0.50, 0.52, 0.54, 0.56, 0.58],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.30,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])  # Empty memory

    result = compute_motivation_flow(summary, memory)

    # Should still classify based on timeline patterns
    assert result.motivation_type is not None
    # Won't be hope (no breakthrough), fear (no fragmentation), stabilization (no events)
    # Likely assertion or ambiguous


def test_edge_case_missing_optional_components():
    """Test handling when optional components are None"""
    summary = MockSessionSummary(
        turn_count=4,
        coherence_timeline=[0.60, 0.62, 0.64, 0.66],
        temporal_arc_timeline=[0.50, 0.52, 0.54, 0.56],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}, {"HRM"}],
        mapper_volatility_score=0.30,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[])

    result = compute_motivation_flow(
        summary,
        memory,
        session_policy=None,  # None
        intent_arc=None,      # None
        identity_signature=None,  # None
    )

    # Should still work without optional components
    assert result.motivation_type is not None
    assert isinstance(result.confidence, float)


def test_edge_case_extreme_values():
    """Test handling of extreme metric values"""
    summary = MockSessionSummary(
        turn_count=5,
        coherence_timeline=[0.10, 0.20, 0.30, 0.40, 0.50],  # Low coherence values
        temporal_arc_timeline=[0.05, 0.10, 0.15, 0.20, 0.25],  # Very low temporal
        mapper_sets=[{"LCM"}, {"LCM"}, {"LCM"}, {"LCM"}, {"LCM"}],
        mapper_volatility_score=0.90,  # Very high volatility
        persona_drift_score=0.85,  # Very high drift
        temporal_arc_score=0.25,
        last_domain="generic",
    )

    memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation", description="Fragmented"),
        MockMemoryEntry(turn_index=2, event_type="fragmentation", description="More fragmentation"),
    ])

    result = compute_motivation_flow(summary, memory)

    # Should classify as fear_driven given extreme fragmentation signals
    assert result.motivation_type in ["fear_driven", "overcorrection", "ambiguous_motivation"]
    assert 0.0 <= result.confidence <= 1.0
