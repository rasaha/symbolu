"""
Symbol-U Session Management Tests

Comprehensive test suite for the session management layer.
All tests are deterministic and verify:
- Session creation and storage
- Turn-by-turn state accumulation
- Multi-turn coherence tracking
- Summary statistics computation
- API endpoint wiring
- Error handling

Test Categories:
    1. Session Creation (3 tests)
    2. Single Turn State (4 tests)
    3. Multi-Turn Retention (4 tests)
    4. Error Handling (2 tests)
    5. API Integration (1 test)
"""

import pytest
from uuid import UUID
from datetime import datetime
from fastapi.testclient import TestClient

from symbolu.service.sessions import SessionStore, compute_session_summary, SessionState
from symbolu.service.api_server import create_app


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def session_store():
    """Provide a fresh SessionStore for each test."""
    return SessionStore()


@pytest.fixture
def sample_unified_output():
    """Provide a sample unified output for testing."""
    return {
        "coherence": {
            "stability": 0.85,
            "persona_drift": 0.12,
            "grounding_status": "stable",
        },
        "temporal_arc": {
            "arc_score": 0.72,
            "trajectory": "ascending",
        },
        "routing": {
            "tier": "UPPER",
            "domain": "therapy",
            "intent": "WHY",
        },
        "mappers": {
            "hrm": {"activated": True, "depth": 0.8},
            "lcm": {"activated": False},
            "lam": {"activated": True, "arc_length": 3},
        },
        "metadata": {
            "pipeline_version": "3.0",
        }
    }


@pytest.fixture
def api_client():
    """Provide a FastAPI test client."""
    try:
        app = create_app()
        return TestClient(app)
    except RuntimeError:
        pytest.skip("FastAPI not available")


# ============================================================================
# SESSION CREATION TESTS
# ============================================================================

def test_can_create_session(session_store):
    """Test 1: Can create session."""
    session = session_store.create_session(domain="generic")

    assert session is not None
    assert session.session_id is not None
    assert session.created_at is not None
    assert isinstance(session.created_at, datetime)


def test_session_has_correct_domain(session_store):
    """Test 2: Session has correct domain."""
    session = session_store.create_session(domain="trading")

    assert session.domain == "trading"


def test_session_id_is_uuid(session_store):
    """Test 3: Session ID is UUID."""
    session = session_store.create_session()

    # Verify it's a valid UUID
    try:
        uuid_obj = UUID(session.session_id)
        assert str(uuid_obj) == session.session_id
    except ValueError:
        pytest.fail("Session ID is not a valid UUID")


# ============================================================================
# SINGLE TURN STATE TESTS
# ============================================================================

def test_append_turn_adds_to_turns_list(session_store, sample_unified_output):
    """Test 4: POST analyze appends turn."""
    session = session_store.create_session()

    # Initially empty
    assert len(session.turns) == 0

    # Append turn
    session_store.append_turn(session.session_id, sample_unified_output)

    # Now has one turn
    assert len(session.turns) == 1
    assert session.turns[0] == sample_unified_output


def test_coherence_history_grows(session_store, sample_unified_output):
    """Test 5: Coherence history grows."""
    session = session_store.create_session()

    # Initially empty
    assert len(session.coherence_history) == 0

    # Append turn
    session_store.append_turn(session.session_id, sample_unified_output)

    # Coherence history should have one entry
    assert len(session.coherence_history) == 1
    assert session.coherence_history[0] == sample_unified_output["coherence"]


def test_routing_history_grows(session_store, sample_unified_output):
    """Test 6: Routing history grows."""
    session = session_store.create_session()

    # Initially empty
    assert len(session.routing_history) == 0

    # Append turn
    session_store.append_turn(session.session_id, sample_unified_output)

    # Routing history should have one entry
    assert len(session.routing_history) == 1
    assert session.routing_history[0] == sample_unified_output["routing"]


def test_mapper_history_grows(session_store, sample_unified_output):
    """Test 7: Mapper history grows."""
    session = session_store.create_session()

    # Initially empty
    assert len(session.mapper_history) == 0

    # Append turn
    session_store.append_turn(session.session_id, sample_unified_output)

    # Mapper history should have one entry
    assert len(session.mapper_history) == 1
    assert session.mapper_history[0] == sample_unified_output["mappers"]


# ============================================================================
# MULTI-TURN RETENTION TESTS
# ============================================================================

def test_multi_turn_conversation_retains_state(session_store):
    """Test 8: Multi-turn conversation retains state."""
    session = session_store.create_session()

    # Add multiple turns
    for i in range(5):
        output = {
            "coherence": {"stability": 0.8 + i * 0.01},
            "temporal_arc": {"arc_score": 0.7 + i * 0.02},
            "routing": {"tier": "UPPER", "domain": "generic"},
            "mappers": {"hrm": {"activated": True}},
        }
        session_store.append_turn(session.session_id, output)

    # Verify all turns are retained
    assert len(session.turns) == 5
    assert len(session.coherence_history) == 5
    assert len(session.temporal_history) == 5
    assert len(session.routing_history) == 5
    assert len(session.mapper_history) == 5


def test_temporal_arc_is_accumulated(session_store):
    """Test 9: Temporal arc is accumulated."""
    session = session_store.create_session()

    # Add turns with temporal arc data
    temporal_arcs = [0.5, 0.6, 0.7, 0.75, 0.8]
    for arc_score in temporal_arcs:
        output = {
            "temporal_arc": {"arc_score": arc_score},
            "coherence": {},
            "routing": {},
            "mappers": {},
        }
        session_store.append_turn(session.session_id, output)

    # Verify temporal history
    assert len(session.temporal_history) == 5
    for i, arc_score in enumerate(temporal_arcs):
        assert session.temporal_history[i]["arc_score"] == arc_score


def test_persona_drift_is_detectable(session_store):
    """Test 10: Persona drift is detectable across turns."""
    session = session_store.create_session()

    # Add turns with persona drift data
    drifts = [0.1, 0.15, 0.2, 0.25, 0.3]
    for drift in drifts:
        output = {
            "coherence": {"stability": 0.8, "persona_drift": drift},
            "temporal_arc": {},
            "routing": {},
            "mappers": {},
        }
        session_store.append_turn(session.session_id, output)

    # Compute summary
    summary = compute_session_summary(session)

    # Verify persona drift average
    expected_avg = sum(drifts) / len(drifts)
    assert abs(summary.persona_drift_avg - expected_avg) < 0.001


def test_session_summary_computes_correct_averages(session_store):
    """Test 11: Session summary computes correct averages."""
    session = session_store.create_session()

    # Add turns with known values
    stabilities = [0.8, 0.85, 0.9, 0.95, 1.0]
    arcs = [0.5, 0.6, 0.7, 0.8, 0.9]
    drifts = [0.1, 0.15, 0.2, 0.25, 0.3]

    for i in range(5):
        output = {
            "coherence": {
                "stability": stabilities[i],
                "persona_drift": drifts[i],
            },
            "temporal_arc": {"arc_score": arcs[i]},
            "routing": {"tier": "HYBRID", "domain": "generic"},
            "mappers": {},
        }
        session_store.append_turn(session.session_id, output)

    # Compute summary
    summary = compute_session_summary(session)

    # Verify averages
    assert abs(summary.coherence_trend - sum(stabilities) / len(stabilities)) < 0.001
    assert abs(summary.temporal_arc_avg - sum(arcs) / len(arcs)) < 0.001
    assert abs(summary.persona_drift_avg - sum(drifts) / len(drifts)) < 0.001
    assert summary.total_turns == 5
    assert summary.last_tier == "HYBRID"
    assert summary.last_domain == "generic"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================

def test_404_on_invalid_session(session_store):
    """Test 12: 404 on invalid session."""
    # Try to get non-existent session
    session = session_store.get("invalid-session-id")
    assert session is None


def test_domain_override_not_allowed_after_creation(api_client):
    """Test 13: Domain override not allowed after creation.

    Once a session is created with a domain, that domain should be
    used for all subsequent analyze calls, regardless of what domain
    is passed in the request.
    """
    if api_client is None:
        pytest.skip("FastAPI not available")

    # Create session with "trading" domain
    response = api_client.post(
        "/session/start",
        json={"domain": "trading"},
        headers={"X-API-Key": "test-key-12345"}
    )
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    assert response.json()["domain"] == "trading"

    # Try to analyze with different domain (should be ignored)
    # The session's domain (trading) should be used, not the request domain
    response = api_client.post(
        f"/session/{session_id}/analyze",
        json={
            "text": "What should I invest in?",
            "domain": "therapy",  # This should be ignored
        },
        headers={"X-API-Key": "test-key-12345"}
    )
    assert response.status_code == 200
    # The domain in the response should be the session's domain (trading)
    assert response.json()["domain"] == "trading"


# ============================================================================
# API INTEGRATION TESTS
# ============================================================================

def test_end_to_end_session_workflow(api_client):
    """Test 14: End-to-end: start → analyze → summary → all valid."""
    if api_client is None:
        pytest.skip("FastAPI not available")

    # Step 1: Create session
    response = api_client.post(
        "/session/start",
        json={"domain": "generic"},
        headers={"X-API-Key": "test-key-12345"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "session_id" in data
    assert "created_at" in data
    assert data["domain"] == "generic"

    session_id = data["session_id"]

    # Step 2: Analyze multiple turns
    texts = [
        "Why do I feel stuck?",
        "What should I do about it?",
        "How can I move forward?",
    ]

    for text in texts:
        response = api_client.post(
            f"/session/{session_id}/analyze",
            json={"text": text},
            headers={"X-API-Key": "test-key-12345"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "text" in data
        assert "coherence" in data
        assert "metadata" in data
        assert data["metadata"]["session_id"] == session_id

    # Step 3: Get session summary
    response = api_client.get(
        f"/session/{session_id}/summary",
        headers={"X-API-Key": "test-key-12345"}
    )
    assert response.status_code == 200
    summary = response.json()

    # Verify summary
    assert summary["session_id"] == session_id
    assert summary["total_turns"] == 3
    assert "coherence_trend" in summary
    assert "persona_drift_avg" in summary
    assert "temporal_arc_avg" in summary
    assert "last_tier" in summary
    assert "last_domain" in summary
    # Domain can be "generic" or "unknown" depending on MLCR detection
    assert summary["last_domain"] in ["generic", "unknown"]


def test_session_not_found_returns_404(api_client):
    """Test that accessing non-existent session returns 404."""
    if api_client is None:
        pytest.skip("FastAPI not available")

    # Try to analyze with non-existent session
    response = api_client.post(
        "/session/nonexistent-id/analyze",
        json={"text": "Hello"},
        headers={"X-API-Key": "test-key-12345"}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()

    # Try to get summary for non-existent session
    response = api_client.get(
        "/session/nonexistent-id/summary",
        headers={"X-API-Key": "test-key-12345"}
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


# ============================================================================
# SESSION STORE TESTS
# ============================================================================

def test_session_store_thread_safety(session_store):
    """Test that SessionStore operations are thread-safe."""
    import threading

    sessions_created = []

    def create_sessions():
        for _ in range(10):
            session = session_store.create_session()
            sessions_created.append(session.session_id)

    threads = [threading.Thread(target=create_sessions) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All sessions should be unique
    assert len(sessions_created) == 50
    assert len(set(sessions_created)) == 50


def test_delete_session(session_store):
    """Test session deletion."""
    session = session_store.create_session()
    session_id = session.session_id

    # Verify session exists
    assert session_store.get(session_id) is not None

    # Delete session
    result = session_store.delete_session(session_id)
    assert result is True

    # Verify session is gone
    assert session_store.get(session_id) is None

    # Delete non-existent session
    result = session_store.delete_session("nonexistent")
    assert result is False


def test_session_count(session_store):
    """Test session count tracking."""
    assert session_store.session_count() == 0

    session_store.create_session()
    assert session_store.session_count() == 1

    session_store.create_session()
    assert session_store.session_count() == 2


def test_get_all_sessions(session_store):
    """Test getting all session IDs."""
    assert len(session_store.get_all_sessions()) == 0

    s1 = session_store.create_session()
    s2 = session_store.create_session()

    all_sessions = session_store.get_all_sessions()
    assert len(all_sessions) == 2
    assert s1.session_id in all_sessions
    assert s2.session_id in all_sessions
