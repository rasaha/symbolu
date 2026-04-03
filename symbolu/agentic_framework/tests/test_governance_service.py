"""
Tests for GovernanceService — the decision-only authorization layer.

Covers:
    - Allow case (high confidence, safe action)
    - Deny case (low confidence, unsafe action)
    - Forbidden capability hard block
    - Unknown tool fail-closed (classified as WRITE, not READ_ONLY)
    - Low-confidence path (execution blocked)
    - Escalation / DEFER path
    - Agency level gating
    - Blocking factors deny
    - Malformed / edge-case inputs
    - Audit event generation
    - Error handling (fail-closed)
"""

import pytest

from symbolu.agentic_framework.governance_models import (
    APIGovernanceDecision,
    APIExecutionMode,
    APIEscalationLevel,
    APIToolRiskLevel,
    AuthorizationRequest,
)
from symbolu.agentic_framework.governance_service import (
    GovernanceService,
    FORBIDDEN_CAPABILITIES,
)


@pytest.fixture
def service():
    """Create a standard governance service."""
    return GovernanceService()


@pytest.fixture
def strict_service():
    """Create a strict governance service."""
    return GovernanceService(strict=True)


# =============================================================================
# Helper to build requests
# =============================================================================


def make_request(**overrides) -> AuthorizationRequest:
    """Build a request with sensible defaults, overridable."""
    defaults = {
        "actor_id": "test-agent",
        "action_type": "file_read",
        "agency_level": "FULL",
        "quality_score": 0.9,
        "coherence_score": 0.9,
        "internal_consistency": 0.9,
        "goal_alignment": 0.9,
        "trajectory_confidence": 0.9,
    }
    defaults.update(overrides)
    return AuthorizationRequest(**defaults)


# =============================================================================
# Test: Allow Case
# =============================================================================


class TestAllowCase:
    """High-confidence, safe action should be ALLOWED."""

    def test_allow_read_only_action(self, service):
        """READ_ONLY action with high confidence → ALLOW."""
        request = make_request(action_type="file_read")
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.ALLOW
        assert response.eligible is True
        assert response.risk_level == APIToolRiskLevel.READ_ONLY
        assert response.confidence_score > 0.7

    def test_allow_search_action(self, service):
        """Search action with high confidence → ALLOW."""
        request = make_request(action_type="search_documents")
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.ALLOW
        assert response.eligible is True

    def test_allow_write_action_high_confidence(self, service):
        """WRITE action with high confidence → ALLOW."""
        request = make_request(action_type="file_write")
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.ALLOW
        assert response.risk_level == APIToolRiskLevel.WRITE

    def test_allow_has_audit_event(self, service):
        """Every ALLOW decision should produce an audit event."""
        request = make_request()
        response = service.authorize(request)

        assert response.audit_event is not None
        assert response.audit_event.decision == APIGovernanceDecision.ALLOW
        assert response.audit_event.actor_id == "test-agent"
        assert response.audit_reference is not None

    def test_allow_safety_contract_satisfied(self, service):
        """ALLOW case should show all preconditions satisfied."""
        request = make_request()
        response = service.authorize(request)

        assert response.safety_contract.eligible is True
        assert len(response.safety_contract.violated_preconditions) == 0
        assert len(response.safety_contract.satisfied_preconditions) > 0


# =============================================================================
# Test: Deny Case
# =============================================================================


class TestDenyCase:
    """Low-confidence or unsafe action should be DENIED."""

    def test_deny_low_consistency(self, service):
        """Low internal consistency → DENY."""
        request = make_request(internal_consistency=0.2)
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.DENY
        assert response.eligible is False
        assert "precondition_1_internal_consistency" in response.safety_contract.violated_preconditions

    def test_deny_low_goal_alignment(self, service):
        """Low goal alignment → DENY."""
        request = make_request(goal_alignment=0.2)
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.DENY
        assert response.eligible is False

    def test_deny_inform_agency_level(self, service):
        """INFORM agency level → DENY (cannot execute actions)."""
        request = make_request(agency_level="INFORM")
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.DENY
        assert response.eligible is False
        assert "precondition_6_agency_permits" in response.safety_contract.violated_preconditions

    def test_deny_with_blocking_factors(self, service):
        """Blocking factors → DENY."""
        request = make_request(blocking_factors=["P6_MISSING", "P7_MISSING"])
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.DENY
        assert response.eligible is False

    def test_deny_has_blocking_reasons(self, service):
        """DENY should include blocking reasons."""
        request = make_request(internal_consistency=0.1, goal_alignment=0.1)
        response = service.authorize(request)

        assert len(response.blocked_reasons) > 0
        assert len(response.rationale_codes) > 0
        assert "DENY" in response.rationale or "denied" in response.rationale.lower()


# =============================================================================
# Test: Forbidden Capability Block
# =============================================================================


class TestForbiddenCapability:
    """Forbidden capabilities must always be DENIED regardless of confidence."""

    def test_deny_data_exfiltration(self, service):
        """data_exfiltration capability → hard DENY."""
        request = make_request(capabilities=["data_exfiltration"])
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.DENY
        assert response.eligible is False
        assert any("forbidden" in r.lower() for r in response.blocked_reasons)

    def test_deny_credential_access(self, service):
        """credential_access capability → hard DENY."""
        request = make_request(capabilities=["credential_access"])
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.DENY

    def test_deny_privilege_escalation(self, service):
        """privilege_escalation capability → hard DENY."""
        request = make_request(capabilities=["privilege_escalation"])
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.DENY

    def test_deny_all_forbidden_capabilities(self, service):
        """Every forbidden capability should be denied."""
        for cap in FORBIDDEN_CAPABILITIES:
            request = make_request(capabilities=[cap])
            response = service.authorize(request)
            assert response.governance_decision == APIGovernanceDecision.DENY, (
                f"Expected DENY for forbidden capability '{cap}', got {response.governance_decision}"
            )

    def test_forbidden_overrides_high_confidence(self, service):
        """Forbidden capability DENY even with perfect confidence scores."""
        request = make_request(
            capabilities=["malware_execution"],
            quality_score=1.0,
            coherence_score=1.0,
            internal_consistency=1.0,
            goal_alignment=1.0,
            trajectory_confidence=1.0,
        )
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.DENY


# =============================================================================
# Test: Unknown Tool Fail-Closed
# =============================================================================


class TestUnknownToolFailClosed:
    """Unknown tools should be classified conservatively (WRITE, not READ_ONLY)."""

    def test_unknown_tool_classified_as_write(self, service):
        """Unknown tool name → WRITE risk level (not READ_ONLY)."""
        request = make_request(action_type="xyzzy_unknown_tool_123")
        response = service.authorize(request)

        # Unknown tools classified as WRITE by ToolRiskClassifier default
        assert response.risk_level == APIToolRiskLevel.WRITE

    def test_unknown_tool_with_high_confidence_still_allowed(self, service):
        """Unknown tool with high confidence can still be allowed (not blocked)."""
        request = make_request(action_type="xyzzy_unknown_tool_123")
        response = service.authorize(request)

        # High confidence + WRITE risk = should still be allowed
        assert response.governance_decision == APIGovernanceDecision.ALLOW


# =============================================================================
# Test: Low Confidence Path
# =============================================================================


class TestLowConfidence:
    """Low confidence should block or require confirmation."""

    def test_very_low_confidence_blocked(self, service):
        """Very low confidence scores → execution blocked."""
        request = make_request(
            quality_score=0.1,
            coherence_score=0.1,
            internal_consistency=0.1,
            goal_alignment=0.1,
            trajectory_confidence=0.1,
        )
        response = service.authorize(request)

        assert response.governance_decision == APIGovernanceDecision.DENY
        assert response.eligible is False

    def test_low_confidence_escalation(self, service):
        """Low-ish confidence → should trigger escalation."""
        request = make_request(
            quality_score=0.4,
            coherence_score=0.4,
            internal_consistency=0.7,
            goal_alignment=0.7,
            trajectory_confidence=0.4,
        )
        response = service.authorize(request)

        # Should have some escalation level
        assert response.escalation_level != APIEscalationLevel.NONE or \
               response.execution_mode != APIExecutionMode.FULL


# =============================================================================
# Test: Escalation / DEFER Path
# =============================================================================


class TestEscalation:
    """DEFER decision when human approval is needed."""

    def test_destructive_action_risk(self, service):
        """Destructive action should be high risk."""
        request = make_request(action_type="delete_all_records")
        response = service.authorize(request)

        assert response.risk_level == APIToolRiskLevel.DESTRUCTIVE

    def test_privileged_action_risk(self, service):
        """Privileged action should be highest risk."""
        request = make_request(action_type="admin_grant_permissions")
        response = service.authorize(request)

        assert response.risk_level == APIToolRiskLevel.PRIVILEGED


# =============================================================================
# Test: Dry Run
# =============================================================================


class TestDryRun:
    """dry_run flag should be reflected in response."""

    def test_dry_run_flag_preserved(self, service):
        """dry_run=True should be in response."""
        request = make_request(dry_run=True)
        response = service.authorize(request)

        assert response.dry_run is True

    def test_dry_run_false_by_default(self, service):
        """dry_run defaults to False."""
        request = make_request()
        response = service.authorize(request)

        assert response.dry_run is False


# =============================================================================
# Test: Audit Events
# =============================================================================


class TestAuditEvents:
    """Audit event generation and tracking."""

    def test_audit_log_grows(self, service):
        """Each authorize call adds an audit event."""
        assert service.get_audit_count() == 0

        service.authorize(make_request())
        assert service.get_audit_count() == 1

        service.authorize(make_request())
        assert service.get_audit_count() == 2

    def test_audit_event_has_required_fields(self, service):
        """Audit events have all required fields."""
        response = service.authorize(make_request())
        event = response.audit_event

        assert event.decision_id is not None
        assert event.timestamp is not None
        assert event.actor_id == "test-agent"
        assert event.action_type == "file_read"
        assert event.decision is not None
        assert event.risk_level is not None
        assert event.request_snapshot is not None

    def test_audit_log_retrievable(self, service):
        """Audit log can be retrieved."""
        service.authorize(make_request())
        log = service.get_audit_log()
        assert len(log) == 1
        assert log[0].actor_id == "test-agent"

    def test_deny_also_produces_audit(self, service):
        """DENY decisions also produce audit events."""
        request = make_request(capabilities=["data_exfiltration"])
        response = service.authorize(request)

        assert service.get_audit_count() == 1
        assert response.audit_event.decision == APIGovernanceDecision.DENY


# =============================================================================
# Test: Response Contract
# =============================================================================


class TestResponseContract:
    """Response model should always have complete structure."""

    def test_response_has_all_required_fields(self, service):
        """Response includes all required top-level fields."""
        response = service.authorize(make_request())

        assert response.governance_decision is not None
        assert response.eligible is not None
        assert response.execution_mode is not None
        assert response.escalation_level is not None
        assert response.requires_human_approval is not None
        assert response.risk_level is not None
        assert response.confidence_score is not None
        assert response.rationale is not None
        assert response.safety_contract is not None
        assert response.confidence_gate is not None
        assert response.audit_event is not None
        assert response.service_version is not None
        assert response.decision_timestamp is not None

    def test_response_serializable(self, service):
        """Response should be JSON-serializable via Pydantic."""
        response = service.authorize(make_request())
        d = response.model_dump()

        assert isinstance(d, dict)
        assert "governance_decision" in d
        assert "safety_contract" in d
        assert "confidence_gate" in d
        assert "audit_event" in d

    def test_confidence_score_bounded(self, service):
        """Confidence score should be in [0.0, 1.0]."""
        response = service.authorize(make_request())
        assert 0.0 <= response.confidence_score <= 1.0

    def test_rationale_is_nonempty(self, service):
        """Rationale string should never be empty."""
        for req in [make_request(), make_request(internal_consistency=0.1)]:
            response = service.authorize(req)
            assert len(response.rationale) > 0


# =============================================================================
# Test: Strict Mode
# =============================================================================


class TestStrictMode:
    """Strict mode should have higher thresholds."""

    def test_strict_mode_more_conservative(self, strict_service):
        """Medium confidence in strict mode → more likely to deny/defer."""
        request = make_request(
            quality_score=0.6,
            coherence_score=0.6,
            internal_consistency=0.7,
            goal_alignment=0.7,
            trajectory_confidence=0.6,
        )
        response = strict_service.authorize(request)

        # Strict mode should be more restrictive
        assert response.execution_mode != APIExecutionMode.FULL or \
               response.escalation_level != APIEscalationLevel.NONE


# =============================================================================
# Test: Request Validation
# =============================================================================


class TestRequestValidation:
    """Pydantic validation should reject invalid requests."""

    def test_reject_empty_actor_id(self):
        """Empty actor_id should be rejected."""
        with pytest.raises(Exception):
            AuthorizationRequest(actor_id="", action_type="read")

    def test_reject_empty_action_type(self):
        """Empty action_type should be rejected."""
        with pytest.raises(Exception):
            AuthorizationRequest(actor_id="agent", action_type="")

    def test_reject_invalid_agency_level(self):
        """Invalid agency_level should be rejected."""
        with pytest.raises(Exception):
            AuthorizationRequest(
                actor_id="agent", action_type="read", agency_level="ADMIN"
            )

    def test_reject_out_of_range_scores(self):
        """Scores outside [0.0, 1.0] should be rejected."""
        with pytest.raises(Exception):
            AuthorizationRequest(
                actor_id="agent", action_type="read", quality_score=2.0
            )

    def test_reject_invalid_readiness_level(self):
        """Invalid readiness_level should be rejected."""
        with pytest.raises(Exception):
            AuthorizationRequest(
                actor_id="agent", action_type="read", readiness_level="INVALID"
            )
