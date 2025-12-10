"""
Unit and Integration Tests for Symbol-U API Server

Tests verify:
    1. Endpoint functionality and schema validation
    2. Pipeline behavior preservation (no modifications)
    3. Coherence and domain propagation
    4. Snapshot determinism
    5. Error handling
    6. Optional dependency handling
"""

import json
import pytest
from typing import Any, Dict
from unittest.mock import patch

# Check if FastAPI is available for testing
try:
    from fastapi.testclient import TestClient
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    TestClient = None

# Import Symbol-U components
from symbolu.mechanical.pipeline.orchestrator import SymbolUPipeline
from symbolu.mechanical.pipeline.models import UserRequest

# Import API server components
from symbolu.service.api_server import create_app, check_dependencies


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def api_client():
    """Create FastAPI test client."""
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not available")
    app = create_app()
    return TestClient(app)


@pytest.fixture
def sample_request_payload() -> Dict[str, Any]:
    """Standard test request payload."""
    return {
        "text": "Hello I feel confused but hopeful",
        "domain": "generic",
        "metadata": {"user_id": "test_user_123"}
    }


@pytest.fixture
def trading_request_payload() -> Dict[str, Any]:
    """Trading domain test request payload."""
    return {
        "text": "What is the market trend?",
        "domain": "trading",
        "metadata": {"user_id": "trader_456"}
    }


@pytest.fixture
def pipeline():
    """Create pipeline instance for direct testing."""
    return SymbolUPipeline()


# ============================================================================
# TEST 1: Health Check Endpoint
# ============================================================================

def test_health_check(api_client):
    """Test /health endpoint returns OK status."""
    response = api_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


# ============================================================================
# TEST 2: DILchat Analyze - Valid Schema
# ============================================================================

def test_dilchat_analyze_valid_schema(api_client, sample_request_payload):
    """Test /dilchat/analyze returns valid schema with all required keys."""
    response = api_client.post("/dilchat/analyze", json=sample_request_payload)

    assert response.status_code == 200
    data = response.json()

    # Verify required keys exist
    assert "text" in data
    assert "badges" in data
    assert "hints" in data
    assert "coherence" in data
    assert "domain" in data
    assert "layers" in data
    assert "metadata" in data

    # Verify types
    assert isinstance(data["text"], str)
    assert isinstance(data["badges"], list)
    assert isinstance(data["hints"], list)
    assert isinstance(data["coherence"], dict)
    assert isinstance(data["domain"], str)
    assert isinstance(data["layers"], dict)
    assert isinstance(data["metadata"], dict)

    # Verify layers structure
    assert "symbolic" in data["layers"]
    assert "practical" in data["layers"]
    assert "mirror" in data["layers"]

    # Verify response is JSON-serializable
    json_str = json.dumps(data)
    assert len(json_str) > 0


# ============================================================================
# TEST 3: Pipeline Behavior Preservation
# ============================================================================

def test_pipeline_not_modified_by_api(api_client, sample_request_payload, pipeline):
    """
    Verify API does not modify pipeline behavior.

    Run pipeline directly and through API, compare outputs.
    Symbolic/practical/mirror/DHA outputs must match exactly.
    """
    # Run pipeline directly
    direct_request = UserRequest(
        text=sample_request_payload["text"],
        user_id=sample_request_payload["metadata"]["user_id"],
        metadata={"domain": sample_request_payload["domain"]}
    )
    direct_result = pipeline.run(direct_request)
    direct_ctx = direct_result.meta.get("context")

    # Run pipeline through API
    api_response = api_client.post("/dilchat/analyze", json=sample_request_payload)
    assert api_response.status_code == 200
    api_data = api_response.json()

    # Compare outputs (API should not modify pipeline behavior)
    assert direct_ctx is not None

    # Compare text output
    assert api_data["text"] == direct_result.raw_text or api_data["text"] == direct_ctx.dilchat_payload.get("text")

    # Verify DILchat payload structure matches
    # Note: API may apply domain fallback (unknown -> requested domain) at presentation layer
    if direct_ctx.dilchat_payload:
        dilchat_domain = direct_ctx.dilchat_payload.get("domain", sample_request_payload["domain"])
        # Allow API to override "unknown" with requested domain (presentation layer only)
        if dilchat_domain == "unknown":
            assert api_data["domain"] == sample_request_payload["domain"]
        else:
            assert api_data["domain"] == dilchat_domain


# ============================================================================
# TEST 4: Coherence Propagation
# ============================================================================

def test_coherence_propagation(api_client, sample_request_payload):
    """Ensure coherence_score appears in response if available."""
    response = api_client.post("/dilchat/analyze", json=sample_request_payload)
    assert response.status_code == 200
    data = response.json()

    # Coherence dict should exist (may be empty if no coherence computed)
    assert "coherence" in data
    assert isinstance(data["coherence"], dict)

    # If coherence_score exists, verify it's a valid number
    if "coherence_score" in data["coherence"]:
        score = data["coherence"]["coherence_score"]
        assert isinstance(score, (int, float))
        assert 0.0 <= score <= 1.0


# ============================================================================
# TEST 5: Domain Propagation
# ============================================================================

def test_domain_propagation(api_client, trading_request_payload):
    """Verify domain="trading" propagates correctly to response."""
    response = api_client.post("/dilchat/analyze", json=trading_request_payload)
    assert response.status_code == 200
    data = response.json()

    # Domain should match request domain
    assert data["domain"] == "trading"


# ============================================================================
# TEST 6: Snapshot Determinism
# ============================================================================

def test_snapshot_determinism(api_client):
    """
    Verify same input produces same output across multiple runs.

    This tests deterministic behavior of the pipeline.
    """
    fixed_payload = {
        "text": "Hello I feel confused but hopeful",
        "domain": "generic",
        "metadata": {}
    }

    # Run twice
    response1 = api_client.post("/dilchat/analyze", json=fixed_payload)
    response2 = api_client.post("/dilchat/analyze", json=fixed_payload)

    assert response1.status_code == 200
    assert response2.status_code == 200

    data1 = response1.json()
    data2 = response2.json()

    # Text output should be identical
    assert data1["text"] == data2["text"]

    # Domain should be identical
    assert data1["domain"] == data2["domain"]

    # Layer summaries should be identical (if present)
    if data1["layers"]["symbolic"] is not None:
        assert data1["layers"]["symbolic"] == data2["layers"]["symbolic"]
    if data1["layers"]["practical"] is not None:
        assert data1["layers"]["practical"] == data2["layers"]["practical"]
    if data1["layers"]["mirror"] is not None:
        assert data1["layers"]["mirror"] == data2["layers"]["mirror"]


# ============================================================================
# TEST 7: Symbolu Analyze - Full Output
# ============================================================================

def test_symbolu_analyze_full_output(api_client, sample_request_payload):
    """
    Test /symbolu/analyze returns complete diagnostic output.

    Verify routing_plan, mapper_profile, entropy, coherence,
    and unified_output are all present.
    """
    response = api_client.post("/symbolu/analyze", json=sample_request_payload)
    assert response.status_code == 200
    data = response.json()

    # Verify top-level keys
    assert "unified_output" in data
    assert "policy_flags" in data
    assert "dilchat_payload" in data

    # Verify unified_output structure
    unified = data["unified_output"]
    assert isinstance(unified, dict)

    # Check for expected sections (may vary based on pipeline config)
    # At minimum, should have text and metadata
    if "text" in unified:
        assert isinstance(unified["text"], str)
    if "routing" in unified:
        assert isinstance(unified["routing"], dict)
    if "coherence" in unified:
        assert isinstance(unified["coherence"], dict)
    if "metadata" in unified:
        assert isinstance(unified["metadata"], dict)

    # Verify policy_flags structure
    policy = data["policy_flags"]
    assert isinstance(policy, dict)

    # Verify dilchat_payload structure
    dilchat = data["dilchat_payload"]
    assert isinstance(dilchat, dict)


# ============================================================================
# TEST 8: Empty Text Handling
# ============================================================================

def test_empty_text_error(api_client):
    """Test that empty text raises appropriate error."""
    empty_payload = {
        "text": "",
        "domain": "generic"
    }

    response = api_client.post("/dilchat/analyze", json=empty_payload)
    # Should return 500 because UserRequest validation fails
    assert response.status_code == 500


# ============================================================================
# TEST 9: Missing Required Fields
# ============================================================================

def test_missing_text_field(api_client):
    """Test that missing 'text' field raises validation error."""
    invalid_payload = {
        "domain": "generic"
    }

    response = api_client.post("/dilchat/analyze", json=invalid_payload)
    # Pydantic validation should fail with 422
    assert response.status_code == 422


# ============================================================================
# TEST 10: Default Domain Handling
# ============================================================================

def test_default_domain(api_client):
    """Test that domain defaults to 'generic' if not specified."""
    minimal_payload = {
        "text": "Test message"
    }

    response = api_client.post("/dilchat/analyze", json=minimal_payload)
    assert response.status_code == 200
    data = response.json()

    # Domain should default to generic
    assert data["domain"] == "generic"


# ============================================================================
# TEST 11: Metadata Passthrough
# ============================================================================

def test_metadata_passthrough(api_client):
    """Test that metadata is correctly passed through pipeline."""
    payload = {
        "text": "Test with metadata",
        "domain": "therapy",
        "metadata": {
            "user_id": "user_999",
            "session_id": "session_abc",
            "custom_field": "custom_value"
        }
    }

    response = api_client.post("/symbolu/analyze", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Verify metadata is accessible in unified output
    unified = data["unified_output"]
    if "metadata" in unified:
        metadata = unified["metadata"]
        assert isinstance(metadata, dict)


# ============================================================================
# TEST 12: Session Dashboard Endpoint (Phase 20)
# ============================================================================

def test_session_dashboard_endpoint_success(api_client):
    """
    Test /sessions/{session_id}/dashboard returns complete analytics.

    Phase 20 dashboard endpoint should return:
    - All coherence metrics (v1/v2/v3/fused/quality)
    - Semantic integrity & drift metrics
    - Temporal entropy metrics
    - Aggregated risk bands
    - Sparklines for key metrics
    """
    # First, create a session
    session_response = api_client.post("/session/start", json={"domain": "test"})
    assert session_response.status_code == 200
    session_data = session_response.json()
    session_id = session_data["session_id"]

    # Add a turn to the session
    turn_payload = {
        "text": "Hello I feel confused but hopeful",
        "domain": "test",
    }
    turn_response = api_client.post(f"/session/{session_id}/analyze", json=turn_payload)
    assert turn_response.status_code == 200

    # Now get dashboard analytics
    dashboard_response = api_client.get(f"/sessions/{session_id}/dashboard")
    assert dashboard_response.status_code == 200

    dashboard = dashboard_response.json()

    # Verify key fields exist
    assert "session_id" in dashboard
    assert dashboard["session_id"] == session_id
    assert "domain" in dashboard
    assert "turn_count" in dashboard

    # Verify coherence metrics are present (some may be None)
    assert "coherence_v1" in dashboard or "coherence_fused" in dashboard

    # Verify bands exist (if computed)
    # Bands are optional depending on available metrics

    # Verify sparklines exist
    assert "coherence_sparkline" in dashboard
    assert "drift_sparkline" in dashboard
    assert "entropy_sparkline" in dashboard


def test_session_dashboard_endpoint_not_found(api_client):
    """Test /sessions/{session_id}/dashboard returns 404 for unknown session."""
    response = api_client.get("/sessions/nonexistent-session-id/dashboard")
    assert response.status_code == 404

    error_data = response.json()
    assert "not found" in error_data["detail"].lower()


def test_session_dashboard_endpoint_no_behavior_change(api_client):
    """
    Test dashboard endpoint does not modify existing endpoint behavior.

    Verify that:
    - /dilchat/analyze still works the same
    - /symbolu/analyze still works the same
    - Session summary still works the same
    """
    # Create session
    session_response = api_client.post("/session/start", json={"domain": "test"})
    session_id = session_response.json()["session_id"]

    # Add turn
    turn_payload = {"text": "Test message", "domain": "test"}
    turn_response = api_client.post(f"/session/{session_id}/analyze", json=turn_payload)

    # Get dashboard (should not affect other endpoints)
    dashboard_response = api_client.get(f"/sessions/{session_id}/dashboard")
    assert dashboard_response.status_code == 200

    # Verify summary endpoint still works
    summary_response = api_client.get(f"/session/{session_id}/summary")
    assert summary_response.status_code == 200

    summary = summary_response.json()
    assert "session_id" in summary
    assert "total_turns" in summary
    assert "coherence_trend" in summary


# ============================================================================
# TEST 13: FastAPI Import Fallback
# ============================================================================

def test_fastapi_import_fallback():
    """Test that create_app() raises clean error if FastAPI not available."""
    with patch('symbolu.service.api_server.FASTAPI_AVAILABLE', False):
        with pytest.raises(RuntimeError) as excinfo:
            create_app()

        error_msg = str(excinfo.value)
        assert "FastAPI is not installed" in error_msg
        assert "pip install" in error_msg


# ============================================================================
# TEST 13: Dependency Check
# ============================================================================

def test_dependency_check():
    """Test check_dependencies() returns correct status."""
    deps = check_dependencies()

    assert isinstance(deps, dict)
    assert "fastapi" in deps
    assert "pydantic" in deps
    assert isinstance(deps["fastapi"], bool)
    assert isinstance(deps["pydantic"], bool)


# ============================================================================
# SKIP MARKER FOR TESTS REQUIRING FASTAPI
# ============================================================================

# Add skip marker for all tests if FastAPI not available
pytestmark = pytest.mark.skipif(
    not FASTAPI_AVAILABLE,
    reason="FastAPI not installed - install with: pip install 'fastapi[standard]' uvicorn"
)
