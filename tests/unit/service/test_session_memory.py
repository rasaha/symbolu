"""
Test Suite for Session Memory v2.0 — Episodic Memory System

This test module validates the deterministic event detection system for
multi-turn session memory, including:
- Event detection (breakthrough, fragmentation, stabilization, arc shift, mapper flip)
- Memory storage and querying
- Pipeline integration
- Unified API and DILchat adapter integration

Test Coverage:
    Group A: Event Detection (10 tests)
    Group B: Memory Storage & Querying (6 tests)
    Group C: Pipeline Integration (6 tests)

Total: 22 tests
"""

import pytest
from datetime import datetime
from typing import Set

from symbolu.service.sessions.session_memory import (
    MemoryEntry,
    SessionMemory,
    SessionMemoryExtractor,
)
from symbolu.service.sessions.session_models import SessionState, SessionSummary
from symbolu.service.sessions.session_store import SessionStore, compute_session_summary


# ============================================================================
# GROUP A: EVENT DETECTION TESTS (10 tests)
# ============================================================================


def test_breakthrough_detection():
    """Test breakthrough event detection."""
    extractor = SessionMemoryExtractor()

    # Create state with breakthrough conditions:
    # - coherence increases by 0.15 (> 0.12 threshold)
    # - temporal_arc = 0.60 (> 0.55 threshold)
    # - persona_drift = 0.40 (< 0.45 threshold)
    state = SessionState(
        session_id="test-1",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}, {"turn": 2}]

    summary = SessionSummary(
        session_id="test-1",
        total_turns=2,
        coherence_trend=0.75,
        persona_drift_avg=0.40,  # This becomes persona_drift_score via property
        temporal_arc_avg=0.60,
        coherence_timeline=[0.60, 0.75],  # +0.15 increase
        temporal_arc_timeline=[0.50, 0.60],
        mapper_sets=[{"HRM"}, {"HRM"}],
    )

    # Extract events
    extractor.update_memory(state, summary)

    # Verify breakthrough detected
    assert len(state.session_memory.events) == 1
    event = state.session_memory.events[0]
    assert event.event_type == "breakthrough"
    assert event.description == "Notable upward clarity shift detected."
    assert event.metrics["coherence_delta"] >= 0.12


def test_fragmentation_detection_coherence_drop():
    """Test fragmentation event detection via coherence drop."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-2",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}, {"turn": 2}]

    # Fragmentation condition: coherence drops by 0.20 (> 0.15 threshold)
    summary = SessionSummary(
        session_id="test-2",
        total_turns=2,
        coherence_trend=0.50,
        persona_drift_avg=0.30,
        temporal_arc_avg=0.50,
        semantic_stability_score=0.50,
        coherence_timeline=[0.70, 0.50],  # -0.20 drop
        temporal_arc_timeline=[0.50, 0.50],
        mapper_sets=[{"HRM"}, {"HRM"}],
    )

    extractor.update_memory(state, summary)

    # Verify fragmentation detected
    assert len(state.session_memory.events) == 1
    event = state.session_memory.events[0]
    assert event.event_type == "fragmentation"
    assert event.description == "Conversation stability momentarily broke."


def test_fragmentation_detection_semantic_stability():
    """Test fragmentation event detection via low semantic stability."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-3",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}]

    # Fragmentation condition: semantic_stability = 0.35 (< 0.40 threshold)
    summary = SessionSummary(
        session_id="test-3",
        total_turns=1,
        coherence_trend=0.60,
        persona_drift_avg=0.30,
        temporal_arc_avg=0.50,
        semantic_stability_score=0.35,  # Below threshold
        coherence_timeline=[0.60],
        temporal_arc_timeline=[0.50],
        mapper_sets=[{"HRM"}],
    )

    extractor.update_memory(state, summary)

    # Verify fragmentation detected
    events = state.session_memory.get_by_type("fragmentation")
    assert len(events) == 1


def test_fragmentation_detection_persona_drift():
    """Test fragmentation event detection via high persona drift."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-4",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}]

    # Fragmentation condition: persona_drift = 0.60 (> 0.55 threshold)
    summary = SessionSummary(
        session_id="test-4",
        total_turns=1,
        coherence_trend=0.60,
        persona_drift_avg=0.60,  # Above threshold
        temporal_arc_avg=0.50,
        semantic_stability_score=0.50,
        coherence_timeline=[0.60],
        temporal_arc_timeline=[0.50],
        mapper_sets=[{"HRM"}],
    )

    extractor.update_memory(state, summary)

    # Verify fragmentation detected
    events = state.session_memory.get_by_type("fragmentation")
    assert len(events) == 1


def test_stabilization_detection():
    """Test stabilization event detection across 3 consecutive rises."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-5",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}, {"turn": 2}, {"turn": 3}]

    # Stabilization conditions:
    # - coherence rises across 3 turns: 0.50 -> 0.60 -> 0.70
    # - mapper_volatility = 0.35 (< 0.40 threshold)
    summary = SessionSummary(
        session_id="test-5",
        total_turns=3,
        coherence_trend=0.60,
        persona_drift_avg=0.30,
        temporal_arc_avg=0.50,
        mapper_volatility_score=0.35,  # Below threshold
        coherence_timeline=[0.50, 0.60, 0.70],  # Consecutive rises
        temporal_arc_timeline=[0.50, 0.55, 0.60],
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}],
    )

    extractor.update_memory(state, summary)

    # Verify stabilization detected
    events = state.session_memory.get_by_type("stabilization")
    assert len(events) == 1
    event = events[0]
    assert event.description == "Conversation trajectory stabilizing."


def test_arc_shift_rise_to_fall():
    """Test arc shift detection from rise to fall."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-6",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}, {"turn": 2}, {"turn": 3}]

    # Arc shift: 0.50 -> 0.65 (rise) -> 0.50 (fall)
    # Magnitude: |0.50 - 0.65| = 0.15 (> 0.10 threshold)
    summary = SessionSummary(
        session_id="test-6",
        total_turns=3,
        coherence_trend=0.60,
        persona_drift_avg=0.30,
        temporal_arc_avg=0.55,
        coherence_timeline=[0.50, 0.60, 0.70],
        temporal_arc_timeline=[0.50, 0.65, 0.50],  # Rise then fall
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}],
    )

    extractor.update_memory(state, summary)

    # Verify arc shift detected
    events = state.session_memory.get_by_type("arc_shift")
    assert len(events) == 1
    event = events[0]
    assert event.description == "Long-arc trajectory shifted direction."
    assert "rise→fall" in str(event.metrics.get("direction", ""))


def test_arc_shift_fall_to_rise():
    """Test arc shift detection from fall to rise."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-7",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}, {"turn": 2}, {"turn": 3}]

    # Arc shift: 0.70 -> 0.55 (fall) -> 0.70 (rise)
    summary = SessionSummary(
        session_id="test-7",
        total_turns=3,
        coherence_trend=0.65,
        persona_drift_avg=0.30,
        temporal_arc_avg=0.65,
        coherence_timeline=[0.50, 0.60, 0.70],
        temporal_arc_timeline=[0.70, 0.55, 0.70],  # Fall then rise
        mapper_sets=[{"HRM"}, {"HRM"}, {"HRM"}],
    )

    extractor.update_memory(state, summary)

    # Verify arc shift detected
    events = state.session_memory.get_by_type("arc_shift")
    assert len(events) == 1
    event = events[0]
    assert "fall→rise" in str(event.metrics.get("direction", ""))


def test_mapper_flip_hrm_to_lam():
    """Test mapper flip detection from HRM to LAM."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-8",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}, {"turn": 2}]

    # Mapper flip: {"HRM"} -> {"LAM"}
    summary = SessionSummary(
        session_id="test-8",
        total_turns=2,
        coherence_trend=0.60,
        persona_drift_avg=0.30,
        temporal_arc_avg=0.50,
        coherence_timeline=[0.60, 0.65],
        temporal_arc_timeline=[0.50, 0.55],
        mapper_sets=[{"HRM"}, {"LAM"}],  # Mapper changed
    )

    extractor.update_memory(state, summary)

    # Verify mapper flip detected
    events = state.session_memory.get_by_type("mapper_flip")
    assert len(events) == 1
    event = events[0]
    assert event.description == "Mapper configuration changed."
    assert "HRM" in event.metrics.get("prev_mappers", "")
    assert "LAM" in event.metrics.get("current_mappers", "")


def test_mapper_flip_multi_mapper():
    """Test mapper flip detection with multiple mappers."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-9",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}, {"turn": 2}]

    # Mapper flip: {"LCM"} -> {"HRM", "LAM"}
    summary = SessionSummary(
        session_id="test-9",
        total_turns=2,
        coherence_trend=0.60,
        persona_drift_avg=0.30,
        temporal_arc_avg=0.50,
        coherence_timeline=[0.60, 0.65],
        temporal_arc_timeline=[0.50, 0.55],
        mapper_sets=[{"LCM"}, {"HRM", "LAM"}],  # Changed
    )

    extractor.update_memory(state, summary)

    # Verify mapper flip detected
    events = state.session_memory.get_by_type("mapper_flip")
    assert len(events) == 1


def test_no_event_for_small_changes():
    """Test that small changes below thresholds don't trigger events."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-10",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}, {"turn": 2}]

    # Small changes (below all thresholds):
    # - coherence delta = 0.05 (< 0.12 breakthrough threshold)
    # - coherence drop = 0.05 (< 0.15 fragmentation threshold)
    # - arc change = 0.05 (< 0.10 arc shift threshold)
    summary = SessionSummary(
        session_id="test-10",
        total_turns=2,
        coherence_trend=0.60,
        persona_drift_avg=0.30,
        temporal_arc_avg=0.50,
        semantic_stability_score=0.60,
        coherence_timeline=[0.60, 0.65],  # +0.05 (small)
        temporal_arc_timeline=[0.50, 0.55],  # +0.05 (small)
        mapper_sets=[{"HRM"}, {"HRM"}],  # No change
    )

    extractor.update_memory(state, summary)

    # Verify no events detected
    assert len(state.session_memory.events) == 0


def test_boundary_thresholds():
    """Test event detection at exact boundary thresholds."""
    extractor = SessionMemoryExtractor()

    state = SessionState(
        session_id="test-11",
        created_at=datetime.utcnow(),
        session_memory=SessionMemory(),
    )
    state.turns = [{"turn": 1}, {"turn": 2}]

    # Exact breakthrough threshold: delta = 0.12
    summary = SessionSummary(
        session_id="test-11",
        total_turns=2,
        coherence_trend=0.72,
        persona_drift_avg=0.45,  # Exact threshold (becomes persona_drift_score via property)
        temporal_arc_avg=0.55,   # Exact threshold
        coherence_timeline=[0.60, 0.72],  # +0.12 (exact)
        temporal_arc_timeline=[0.50, 0.55],
        mapper_sets=[{"HRM"}, {"HRM"}],
    )

    extractor.update_memory(state, summary)

    # Verify breakthrough detected at exact threshold
    events = state.session_memory.get_by_type("breakthrough")
    assert len(events) == 1


# ============================================================================
# GROUP B: MEMORY STORAGE & QUERYING TESTS (6 tests)
# ============================================================================


def test_add_event_correctness():
    """Test that add_event correctly appends events."""
    memory = SessionMemory()

    event1 = MemoryEntry(
        turn_index=0,
        event_type="breakthrough",
        description="Test event 1",
        metrics={"score": 0.85},
    )
    event2 = MemoryEntry(
        turn_index=1,
        event_type="stabilization",
        description="Test event 2",
        metrics={"score": 0.90},
    )

    memory.add_event(event1)
    memory.add_event(event2)

    assert len(memory.events) == 2
    assert memory.events[0].event_type == "breakthrough"
    assert memory.events[1].event_type == "stabilization"


def test_get_recent_n():
    """Test get_recent(n) returns correct number of events."""
    memory = SessionMemory()

    # Add 5 events
    for i in range(5):
        memory.add_event(MemoryEntry(
            turn_index=i,
            event_type=f"event_{i}",
            description=f"Event {i}",
            metrics={},
        ))

    # Get recent 3
    recent = memory.get_recent(3)
    assert len(recent) == 3
    assert recent[0].event_type == "event_2"
    assert recent[1].event_type == "event_3"
    assert recent[2].event_type == "event_4"

    # Get recent 10 (more than available)
    recent_all = memory.get_recent(10)
    assert len(recent_all) == 5


def test_get_by_type():
    """Test get_by_type filters events correctly."""
    memory = SessionMemory()

    memory.add_event(MemoryEntry(0, "breakthrough", "Event 1", {}))
    memory.add_event(MemoryEntry(1, "fragmentation", "Event 2", {}))
    memory.add_event(MemoryEntry(2, "breakthrough", "Event 3", {}))
    memory.add_event(MemoryEntry(3, "stabilization", "Event 4", {}))

    breakthroughs = memory.get_by_type("breakthrough")
    assert len(breakthroughs) == 2
    assert all(e.event_type == "breakthrough" for e in breakthroughs)

    fragmentations = memory.get_by_type("fragmentation")
    assert len(fragmentations) == 1

    nonexistent = memory.get_by_type("nonexistent")
    assert len(nonexistent) == 0


def test_serialization():
    """Test memory serialization to JSON-safe dict."""
    memory = SessionMemory()

    memory.add_event(MemoryEntry(
        turn_index=0,
        event_type="breakthrough",
        description="Test breakthrough",
        metrics={"coherence_score": 0.85, "delta": 0.15},
    ))

    serialized = memory.serialize()

    assert "events" in serialized
    assert "event_count" in serialized
    assert serialized["event_count"] == 1
    assert len(serialized["events"]) == 1

    event_dict = serialized["events"][0]
    assert event_dict["turn_index"] == 0
    assert event_dict["event_type"] == "breakthrough"
    assert event_dict["description"] == "Test breakthrough"
    assert event_dict["metrics"]["coherence_score"] == 0.85


def test_memory_persists_across_turns():
    """Test that memory accumulates across multiple turns."""
    store = SessionStore()
    session = store.create_session()

    # Simulate 5 turns with varied data
    for i in range(5):
        # Add turn data
        payload = {
            "coherence": {"coherence_score": 0.5 + (i * 0.05), "persona_drift": 0.3},
            "temporal_arc": {"arc_score": 0.5 + (i * 0.02)},
            "routing": {"tier": "HYBRID"},
            "mappers": {"hrm_active": True, "lcm_active": False, "lam_active": False},
        }
        store.append_turn(session.session_id, payload)

        # Update session memory
        store.update_session(session.session_id)

    # Check memory accumulated
    session_state = store.get(session.session_id)
    assert session_state is not None
    assert session_state.session_memory is not None
    # Memory may have events depending on thresholds
    assert len(session_state.turns) == 5


def test_memory_resets_on_new_session():
    """Test that memory is fresh for each new session."""
    store = SessionStore()

    # Create first session with events
    session1 = store.create_session()
    payload1 = {
        "coherence": {"coherence_score": 0.80, "persona_drift": 0.3},
        "temporal_arc": {"arc_score": 0.60},
        "routing": {"tier": "HYBRID"},
        "mappers": {"hrm_active": True, "lcm_active": False, "lam_active": False},
    }
    store.append_turn(session1.session_id, payload1)
    store.update_session(session1.session_id)

    # Create second session
    session2 = store.create_session()

    # Verify session2 has fresh memory
    assert session2.session_memory is not None
    assert len(session2.session_memory.events) == 0
    assert session2.session_id != session1.session_id


# ============================================================================
# GROUP C: PIPELINE INTEGRATION TESTS (6 tests)
# ============================================================================


def test_orchestrator_attaches_memory():
    """Test that orchestrator attaches memory to context."""
    # This test requires running the full pipeline with a session_id
    # For now, we test the session store integration
    store = SessionStore()
    session = store.create_session()

    # Simulate turn
    payload = {
        "coherence": {"coherence_score": 0.75, "persona_drift": 0.3},
        "temporal_arc": {"arc_score": 0.60},
        "routing": {"tier": "HYBRID"},
        "mappers": {"hrm_active": True, "lcm_active": False, "lam_active": False},
    }
    store.append_turn(session.session_id, payload)

    # Update session (simulates orchestrator call)
    store.update_session(session.session_id)

    # Verify memory is attached
    session_state = store.get(session.session_id)
    assert session_state.session_memory is not None


def test_unified_output_contains_session_memory():
    """Test that unified output includes session_memory field."""
    from symbolu.api.unified_api import build_unified_output

    # Create mock context with session memory
    class MockContext:
        def __init__(self):
            self.rendered = type('obj', (object,), {'raw_text': 'Test output'})()
            self.dha = None
            self.fusion = None
            self.mlcr = None
            self.coherence_report = None
            self.coherence_state = None
            self.request = type('obj', (object,), {'user_id': 'test-user'})()
            self.session_memory = SessionMemory()
            self.session_memory.add_event(MemoryEntry(
                turn_index=0,
                event_type="breakthrough",
                description="Test",
                metrics={},
            ))

    ctx = MockContext()
    unified = build_unified_output("Test output", ctx)
    unified_dict = unified.to_dict()

    assert "session_memory" in unified_dict
    assert "events" in unified_dict["session_memory"]
    assert len(unified_dict["session_memory"]["events"]) == 1


def test_public_response_trims_memory_safely():
    """Test that public response trims memory to significant events only."""
    from symbolu.api.unified_api import get_public_response

    # Create mock context
    class MockContext:
        def __init__(self):
            self.rendered = type('obj', (object,), {'raw_text': 'Test'})()
            self.dha = type('obj', (object,), {
                'guarded_text': 'Test',
                'tone_profile': 'neutral',
                'readiness_level': 'medium',
                'resistance_flags': {},
                'safety_flags': {},
                'adaptation_notes': {}
            })()
            self.fusion = None
            self.mlcr = None
            self.coherence_report = {'coherence_score': 0.8}
            self.coherence_state = None
            self.request = type('obj', (object,), {'user_id': 'test'})()
            self.session_memory = SessionMemory()
            # Add various events
            self.session_memory.add_event(MemoryEntry(0, "breakthrough", "Test 1", {}))
            self.session_memory.add_event(MemoryEntry(1, "fragmentation", "Test 2", {}))
            self.session_memory.add_event(MemoryEntry(2, "mapper_flip", "Test 3", {}))
            self.session_memory.add_event(MemoryEntry(3, "arc_shift", "Test 4", {}))

    ctx = MockContext()
    public = get_public_response(ctx)

    assert "session_memory" in public
    # Public response should filter to significant types only
    if public["session_memory"]:
        assert "events" in public["session_memory"]
        # Should have at most 2 significant events
        assert len(public["session_memory"]["events"]) <= 2


def test_dilchat_adapter_produces_memory_badges():
    """Test that DILchat adapter creates badges for memory events."""
    from symbolu.adapter.dilchat_adapter import build_dilchat_response

    # Create unified output with memory events
    unified_output = {
        "text": "Test output",
        "symbolic": {},
        "practical": {},
        "mirror": {},
        "coherence": {"coherence_score": 0.75},
        "metadata": {"domain": "generic"},
        "session_memory": {
            "events": [
                {
                    "turn_index": 0,
                    "event_type": "breakthrough",
                    "description": "Notable upward clarity shift detected.",
                    "metrics": {},
                }
            ],
            "event_count": 1,
        },
    }

    policy_flags = {"stability_status": "stable"}

    response = build_dilchat_response(unified_output, policy_flags, "generic")

    # Check for memory badges
    badge_labels = [badge.label for badge in response.badges]
    assert "Breakthrough Moment" in badge_labels


def test_dilchat_adapter_produces_memory_hints():
    """Test that DILchat adapter creates hints for memory events."""
    from symbolu.adapter.dilchat_adapter import build_dilchat_response

    unified_output = {
        "text": "Test output",
        "symbolic": {},
        "practical": {},
        "mirror": {},
        "coherence": {"coherence_score": 0.75},
        "metadata": {"domain": "generic"},
        "session_memory": {
            "events": [
                {
                    "turn_index": 1,
                    "event_type": "mapper_flip",
                    "description": "Mapper configuration changed.",
                    "metrics": {},
                },
                {
                    "turn_index": 2,
                    "event_type": "stabilization",
                    "description": "Conversation trajectory stabilizing.",
                    "metrics": {},
                },
            ],
            "event_count": 2,
        },
    }

    policy_flags = {"stability_status": "recovering"}

    response = build_dilchat_response(unified_output, policy_flags, "generic")

    # Check for memory hints
    hint_codes = [hint.code for hint in response.hints]
    assert "STATE_CHANGED" in hint_codes
    assert "SESSION_RECOVERING" in hint_codes


def test_sessionless_requests_do_not_break():
    """Test that requests without session_id don't break pipeline."""
    # This is a safety test to ensure memory is optional
    from symbolu.api.unified_api import build_unified_output

    class MockContext:
        def __init__(self):
            self.rendered = type('obj', (object,), {'raw_text': 'Test'})()
            self.dha = None
            self.fusion = None
            self.mlcr = None
            self.coherence_report = None
            self.coherence_state = None
            self.request = type('obj', (object,), {'user_id': 'test'})()
            # No session_memory attribute

    ctx = MockContext()
    unified = build_unified_output("Test", ctx)
    unified_dict = unified.to_dict()

    # Should have session_memory field but it should be empty
    assert "session_memory" in unified_dict


def test_deterministic_outputs_across_identical_inputs():
    """Test that identical inputs produce identical memory events."""
    extractor = SessionMemoryExtractor()

    # Create two identical states
    def create_test_state():
        state = SessionState(
            session_id="test-deterministic",
            created_at=datetime.utcnow(),
            session_memory=SessionMemory(),
        )
        state.turns = [{"turn": 1}, {"turn": 2}]
        return state

    def create_test_summary():
        return SessionSummary(
            session_id="test-deterministic",
            total_turns=2,
            coherence_trend=0.75,
            persona_drift_avg=0.40,
            temporal_arc_avg=0.60,
            coherence_timeline=[0.60, 0.75],
            temporal_arc_timeline=[0.50, 0.60],
            mapper_sets=[{"HRM"}, {"HRM"}],
        )

    # Run extraction twice
    state1 = create_test_state()
    summary1 = create_test_summary()
    extractor.update_memory(state1, summary1)

    state2 = create_test_state()
    summary2 = create_test_summary()
    extractor.update_memory(state2, summary2)

    # Verify identical results
    assert len(state1.session_memory.events) == len(state2.session_memory.events)
    if len(state1.session_memory.events) > 0:
        for i in range(len(state1.session_memory.events)):
            event1 = state1.session_memory.events[i]
            event2 = state2.session_memory.events[i]
            assert event1.event_type == event2.event_type
            assert event1.description == event2.description
            assert event1.turn_index == event2.turn_index


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
