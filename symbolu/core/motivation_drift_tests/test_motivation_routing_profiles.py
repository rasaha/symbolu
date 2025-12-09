"""
test_motivation_routing_profiles.py

Profile-based integration drift tests for Motivation Flow Engine.
Tests realistic user scenarios to lock in v1.0 routing behavior.

IMPORTANT: These tests verify ACTUAL engine behavior as of v1.0 to detect drift.

Zero-LLM, fully deterministic.
"""

import pytest
from typing import List, Set, Dict
from dataclasses import dataclass, field


# Mock data structures (matching existing motivation test pattern)
@dataclass
class MockMemoryEntry:
    """Mock MemoryEntry for testing"""
    turn_index: int
    event_type: str
    description: str
    metrics: Dict[str, float] = field(default_factory=dict)


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


# Import the real Motivation Flow Engine
from symbolu.motivation.motivation_engine import compute_motivation_flow


# ============================================================================
# PROFILE-BASED ROUTING DRIFT TESTS
# ============================================================================

def test_profile_hope_driven_with_breakthrough():
    """
    Drift Test: Hope-driven profile with upward trajectory and breakthrough.
    Locks in v1.0 hope_driven classification behavior.
    """
    coherence_timeline = [0.50, 0.58, 0.65, 0.72]  # Delta 0.22 (strong upward)

    session_summary = MockSessionSummary(
        turn_count=4,
        coherence_score=0.72,
        persona_drift_score=0.40,  # Higher drift to reduce assertion_driven confidence
        temporal_arc_score=0.65,
        mapper_volatility_score=0.38,  # Higher volatility (still < 0.45)
        coherence_timeline=coherence_timeline,
        temporal_arc_timeline=[0.55, 0.60, 0.63, 0.65],  # Rising
        mapper_sets=[{"HRM"}] * 4,
    )

    session_memory = MockSessionMemory(events=[
        MockMemoryEntry(
            turn_index=3,
            event_type="breakthrough",
            description="Major breakthrough",
            metrics={"coherence": 0.72}
        )
    ])

    intent_arc = MockIntentArc(
        arc_type="insight_arc",
        confidence=0.80,
        reasons=["upward_trajectory", "breakthrough"],
        turn_count=4
    )

    result = compute_motivation_flow(
        session_summary=session_summary,
        session_memory=session_memory,
        intent_arc=intent_arc
    )

    assert result.motivation_type == "hope_driven", (
        f"Hope profile should be hope_driven, got {result.motivation_type}"
    )
    assert result.confidence >= 0.70


def test_profile_fear_driven_with_fragmentation():
    """
    Drift Test: Fear-driven profile with fragmentation and high volatility.
    Locks in v1.0 fear_driven classification behavior.
    """
    coherence_timeline = [0.55, 0.40, 0.38, 0.42, 0.40]

    session_summary = MockSessionSummary(
        turn_count=5,
        coherence_score=0.40,
        persona_drift_score=0.70,
        temporal_arc_score=0.35,
        mapper_volatility_score=0.75,
        coherence_timeline=coherence_timeline,
        temporal_arc_timeline=[0.35] * 5,
        mapper_sets=[{"LCM"}, {"HRM"}, {"LCM"}, {"LCM"}, {"HRM"}],
    )

    session_memory = MockSessionMemory(events=[
        MockMemoryEntry(
            turn_index=1,
            event_type="fragmentation",
            description="Fragmentation event",
            metrics={"volatility": 0.75, "drift": 0.70}
        ),
        MockMemoryEntry(
            turn_index=3,
            event_type="fragmentation",
            description="Continued fragmentation",
            metrics={"volatility": 0.75}
        ),
    ])

    intent_arc = MockIntentArc(
        arc_type="chaotic_arc",
        confidence=0.80,
        reasons=["high_volatility", "fragmentation"],
        turn_count=5
    )

    result = compute_motivation_flow(
        session_summary=session_summary,
        session_memory=session_memory,
        intent_arc=intent_arc
    )

    assert result.motivation_type == "fear_driven", (
        f"Fear profile should be fear_driven, got {result.motivation_type}"
    )
    assert result.confidence >= 0.65


def test_profile_stabilization_driven_with_recovery():
    """
    Drift Test: Stabilization profile with valley pattern and recovery.
    Locks in v1.0 stabilization_driven classification behavior.
    """
    coherence_timeline = [0.60, 0.40, 0.50, 0.65]

    session_summary = MockSessionSummary(
        turn_count=4,
        coherence_score=0.65,
        persona_drift_score=0.35,
        temporal_arc_score=0.50,
        mapper_volatility_score=0.30,
        coherence_timeline=coherence_timeline,
        temporal_arc_timeline=[0.45, 0.48, 0.50, 0.50],
        mapper_sets=[{"HRM"}] * 4,
    )

    session_memory = MockSessionMemory(events=[
        MockMemoryEntry(
            turn_index=1,
            event_type="fragmentation",
            description="Early fragmentation",
            metrics={"coherence": 0.40}
        ),
        MockMemoryEntry(
            turn_index=3,
            event_type="stabilization",
            description="Stabilization achieved",
            metrics={"coherence": 0.65, "delta": 0.25}
        )
    ])

    result = compute_motivation_flow(
        session_summary=session_summary,
        session_memory=session_memory
    )

    assert result.motivation_type == "stabilization_driven", (
        f"Stabilization profile should be stabilization_driven, got {result.motivation_type}"
    )
    assert result.confidence >= 0.65


def test_profile_overcorrection_with_oscillations():
    """
    Drift Test: Overcorrection profile with oscillations and mapper flips.
    Locks in v1.0 overcorrection classification behavior.
    """
    coherence_timeline = [0.50, 0.65, 0.40, 0.60, 0.38, 0.55]
    mapper_sets = [{"LCM"}, {"HRM"}, {"LCM"}, {"HRM"}, {"LCM"}, {"HRM"}]

    session_summary = MockSessionSummary(
        turn_count=6,
        coherence_score=0.50,
        persona_drift_score=0.60,
        temporal_arc_score=0.40,
        mapper_volatility_score=0.75,
        coherence_timeline=coherence_timeline,
        temporal_arc_timeline=[0.40] * 6,
        mapper_sets=mapper_sets,
    )

    session_memory = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="mapper_flip",
                       description="Flip 1", metrics={"volatility": 0.75}),
        MockMemoryEntry(turn_index=2, event_type="mapper_flip",
                       description="Flip 2", metrics={"volatility": 0.75}),
        MockMemoryEntry(turn_index=4, event_type="mapper_flip",
                       description="Flip 3", metrics={"volatility": 0.75}),
    ])

    intent_arc = MockIntentArc(
        arc_type="chaotic_arc",
        confidence=0.75,
        reasons=["oscillating", "high_volatility"],
        turn_count=6
    )

    result = compute_motivation_flow(
        session_summary=session_summary,
        session_memory=session_memory,
        intent_arc=intent_arc
    )

    assert result.motivation_type == "overcorrection", (
        f"Overcorrection profile should be overcorrection, got {result.motivation_type}"
    )
    assert result.confidence >= 0.65


def test_profile_ambiguous_with_weak_signals():
    """
    Drift Test: Ambiguous profile with weak/mixed signals.
    Locks in v1.0 ambiguous_motivation classification behavior.
    """
    coherence_timeline = [0.50, 0.52, 0.49, 0.51]

    session_summary = MockSessionSummary(
        turn_count=4,
        coherence_score=0.51,
        persona_drift_score=0.40,
        temporal_arc_score=0.45,
        mapper_volatility_score=0.40,
        coherence_timeline=coherence_timeline,
        temporal_arc_timeline=[0.45] * 4,
        mapper_sets=[{"HRM"}, {"LCM"}, {"HRM"}, {"LCM"}],
    )

    session_memory = MockSessionMemory(events=[])

    result = compute_motivation_flow(
        session_summary=session_summary,
        session_memory=session_memory
    )

    assert result.motivation_type == "ambiguous_motivation", (
        f"Ambiguous profile should be ambiguous_motivation, got {result.motivation_type}"
    )
    assert result.confidence <= 0.50


# ============================================================================
# CROSS-MOTIVATION CONSISTENCY TESTS
# ============================================================================

def test_hope_requires_both_trajectory_and_breakthrough():
    """
    Drift Test: Verify hope_driven requires BOTH upward trajectory AND breakthrough.
    Testing the AND logic doesn't drift to OR logic.
    """
    # Test 1: Good trajectory, NO breakthrough → NOT hope_driven
    coherence_timeline_1 = [0.55, 0.70]
    summary_1 = MockSessionSummary(
        turn_count=2,
        coherence_score=0.70,
        mapper_volatility_score=0.35,
        coherence_timeline=coherence_timeline_1,
        temporal_arc_timeline=[0.60, 0.60],
        mapper_sets=[{"HRM"}, {"HRM"}],
    )
    memory_1 = MockSessionMemory(events=[])

    result_1 = compute_motivation_flow(summary_1, memory_1)
    assert result_1.motivation_type != "hope_driven", (
        f"Good trajectory without breakthrough should NOT be hope_driven"
    )

    # Test 2: Flat trajectory, HAS breakthrough → NOT hope_driven
    coherence_timeline_2 = [0.70, 0.71]  # Only 0.01 delta (< 0.12 threshold)
    summary_2 = MockSessionSummary(
        turn_count=2,
        coherence_score=0.71,
        mapper_volatility_score=0.35,
        coherence_timeline=coherence_timeline_2,
        temporal_arc_timeline=[0.60, 0.60],
        mapper_sets=[{"HRM"}, {"HRM"}],
    )
    memory_2 = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="breakthrough",
                       description="Breakthrough", metrics={})
    ])

    result_2 = compute_motivation_flow(summary_2, memory_2)
    assert result_2.motivation_type != "hope_driven", (
        f"Breakthrough without strong trajectory should NOT be hope_driven"
    )

    # Test 3: BOTH conditions met → hope_driven
    coherence_timeline_3 = [0.55, 0.70]  # Delta 0.15 > 0.12
    summary_3 = MockSessionSummary(
        turn_count=2,
        coherence_score=0.70,
        mapper_volatility_score=0.35,
        coherence_timeline=coherence_timeline_3,
        temporal_arc_timeline=[0.60, 0.60],
        mapper_sets=[{"HRM"}, {"HRM"}],
    )
    memory_3 = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="breakthrough",
                       description="Breakthrough", metrics={})
    ])

    result_3 = compute_motivation_flow(summary_3, memory_3)
    assert result_3.motivation_type == "hope_driven", (
        f"Both conditions met should be hope_driven"
    )


def test_fear_requires_both_fragmentation_and_volatility():
    """
    Drift Test: Verify fear_driven requires BOTH fragmentation AND high volatility.
    Testing the AND logic doesn't drift.
    """
    # Test 1: High volatility, NO fragmentation → NOT fear_driven
    summary_1 = MockSessionSummary(
        turn_count=3,
        coherence_score=0.40,
        mapper_volatility_score=0.70,  # High
        coherence_timeline=[0.50, 0.40, 0.40],
        temporal_arc_timeline=[0.35] * 3,
        mapper_sets=[{"LCM"}] * 3,
    )
    memory_1 = MockSessionMemory(events=[])
    intent_1 = MockIntentArc(arc_type="chaotic_arc", confidence=0.70, turn_count=3)

    result_1 = compute_motivation_flow(summary_1, memory_1, intent_arc=intent_1)
    assert result_1.motivation_type != "fear_driven", (
        f"High volatility without fragmentation should NOT be fear_driven"
    )

    # Test 2: Fragmentation, LOW volatility → NOT fear_driven
    summary_2 = MockSessionSummary(
        turn_count=3,
        coherence_score=0.40,
        mapper_volatility_score=0.30,  # Low
        coherence_timeline=[0.50, 0.40, 0.40],
        temporal_arc_timeline=[0.35] * 3,
        mapper_sets=[{"LCM"}] * 3,
    )
    memory_2 = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation",
                       description="Fragmentation", metrics={})
    ])
    intent_2 = MockIntentArc(arc_type="chaotic_arc", confidence=0.70, turn_count=3)

    result_2 = compute_motivation_flow(summary_2, memory_2, intent_arc=intent_2)
    assert result_2.motivation_type != "fear_driven", (
        f"Fragmentation without high volatility should NOT be fear_driven"
    )

    # Test 3: BOTH conditions met → fear_driven
    summary_3 = MockSessionSummary(
        turn_count=3,
        coherence_score=0.40,
        mapper_volatility_score=0.70,  # High
        coherence_timeline=[0.50, 0.40, 0.40],
        temporal_arc_timeline=[0.35] * 3,
        mapper_sets=[{"LCM"}] * 3,
    )
    memory_3 = MockSessionMemory(events=[
        MockMemoryEntry(turn_index=1, event_type="fragmentation",
                       description="Fragmentation", metrics={})
    ])
    intent_3 = MockIntentArc(arc_type="chaotic_arc", confidence=0.70, turn_count=3)

    result_3 = compute_motivation_flow(summary_3, memory_3, intent_arc=intent_3)
    assert result_3.motivation_type == "fear_driven", (
        f"Both conditions met should be fear_driven"
    )


# ============================================================================
# SUMMARY
# ============================================================================
# Total tests: 7
# - 5 profile-based tests (hope, fear, stabilization, overcorrection, ambiguous)
# - 2 consistency tests (AND logic verification)
#
# These tests lock in v1.0 routing behavior to detect future drift.
# All tests are zero-LLM and fully deterministic.
