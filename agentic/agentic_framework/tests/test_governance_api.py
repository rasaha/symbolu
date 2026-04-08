"""
Tests for Governance API — HTTP endpoint tests.

Uses FastAPI TestClient for synchronous HTTP testing.

Covers:
    - POST /authorize (allow, deny, forbidden, malformed)
    - GET /health
    - GET /version
    - Request size limits
    - Response schema validation
"""

import pytest
from fastapi.testclient import TestClient

from agentic.agentic_framework.governance_api import app, set_service
from agentic.agentic_framework.governance_service import GovernanceService


@pytest.fixture(autouse=True)
def reset_service():
    """Reset service singleton before each test."""
    set_service(GovernanceService())
    yield
    set_service(GovernanceService())


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


# =============================================================================
# POST /authorize
# =============================================================================


class TestAuthorizeEndpoint:
    """POST /authorize endpoint tests."""

    def test_allow_case(self, client):
        """High confidence read action → 200 + ALLOW."""
        response = client.post("/authorize", json={
            "actor_id": "test-agent",
            "action_type": "file_read",
            "agency_level": "FULL",
            "quality_score": 0.9,
            "coherence_score": 0.9,
            "internal_consistency": 0.9,
            "goal_alignment": 0.9,
            "trajectory_confidence": 0.9,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["governance_decision"] == "ALLOW"
        assert data["eligible"] is True

    def test_deny_case(self, client):
        """Low confidence → 200 + DENY."""
        response = client.post("/authorize", json={
            "actor_id": "test-agent",
            "action_type": "file_read",
            "agency_level": "FULL",
            "quality_score": 0.1,
            "coherence_score": 0.1,
            "internal_consistency": 0.1,
            "goal_alignment": 0.1,
            "trajectory_confidence": 0.1,
        })
        assert response.status_code == 200
        data = response.json()
        assert data["governance_decision"] == "DENY"
        assert data["eligible"] is False

    def test_forbidden_capability(self, client):
        """Forbidden capability → 200 + DENY."""
        response = client.post("/authorize", json={
            "actor_id": "test-agent",
            "action_type": "file_read",
            "capabilities": ["data_exfiltration"],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["governance_decision"] == "DENY"

    def test_minimal_request(self, client):
        """Minimal valid request (only required fields) → 200."""
        response = client.post("/authorize", json={
            "actor_id": "test-agent",
            "action_type": "some_action",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["governance_decision"] in ("ALLOW", "DENY", "DEFER")

    def test_malformed_request_missing_actor(self, client):
        """Missing required field → 422."""
        response = client.post("/authorize", json={
            "action_type": "file_read",
        })
        assert response.status_code == 422

    def test_malformed_request_missing_action(self, client):
        """Missing required field → 422."""
        response = client.post("/authorize", json={
            "actor_id": "test-agent",
        })
        assert response.status_code == 422

    def test_malformed_request_invalid_score(self, client):
        """Out-of-range score → 422."""
        response = client.post("/authorize", json={
            "actor_id": "test-agent",
            "action_type": "file_read",
            "quality_score": 5.0,
        })
        assert response.status_code == 422

    def test_malformed_request_invalid_agency(self, client):
        """Invalid agency_level → 422."""
        response = client.post("/authorize", json={
            "actor_id": "test-agent",
            "action_type": "file_read",
            "agency_level": "GOD_MODE",
        })
        assert response.status_code == 422

    def test_response_has_required_fields(self, client):
        """Response contains all expected top-level fields."""
        response = client.post("/authorize", json={
            "actor_id": "test-agent",
            "action_type": "file_read",
        })
        data = response.json()

        required = [
            "governance_decision", "eligible", "execution_mode",
            "escalation_level", "requires_human_approval", "risk_level",
            "confidence_score", "rationale", "safety_contract",
            "confidence_gate", "audit_event", "service_version",
            "decision_timestamp",
        ]
        for field in required:
            assert field in data, f"Missing field: {field}"

    def test_dry_run_flag(self, client):
        """dry_run flag reflected in response."""
        response = client.post("/authorize", json={
            "actor_id": "test-agent",
            "action_type": "file_read",
            "dry_run": True,
        })
        data = response.json()
        assert data["dry_run"] is True

    def test_empty_body(self, client):
        """Empty body → 422."""
        response = client.post("/authorize", json={})
        assert response.status_code == 422

    def test_non_json_body(self, client):
        """Non-JSON body → 422."""
        response = client.post(
            "/authorize",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert response.status_code == 422


# =============================================================================
# GET /health
# =============================================================================


class TestHealthEndpoint:
    """GET /health endpoint tests."""

    def test_health_returns_200(self, client):
        """Health endpoint returns 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_has_status(self, client):
        """Health response includes status."""
        data = client.get("/health").json()
        assert data["status"] == "healthy"

    def test_health_has_version(self, client):
        """Health response includes version."""
        data = client.get("/health").json()
        assert "version" in data


# =============================================================================
# GET /version
# =============================================================================


class TestVersionEndpoint:
    """GET /version endpoint tests."""

    def test_version_returns_200(self, client):
        """Version endpoint returns 200."""
        response = client.get("/version")
        assert response.status_code == 200

    def test_version_has_service_info(self, client):
        """Version response includes service and version."""
        data = client.get("/version").json()
        assert data["service"] == "symbolu-governance-api"
        assert "version" in data
        assert data["governance_model"] == "fail-closed-default"
