"""
S3 Readiness Checker Integration Tests
========================================

Tests for Phase S3-safety: ReadinessChecker promotion into governance.

Test categories:
1. Adapter contract — resolution shape, frozen, serialization
2. Deterministic behavior — same inputs → identical outputs
3. Fail-closed — missing plasticity → unavailable, zero penalty
4. Bounded penalty — NOT_READY max 0.03, DEGRADED 0.02, READY 0.0
5. Escalation logic — only NOT_READY triggers escalation
6. Status transitions — correct status for various input combinations
7. Consumer-level — GovernanceService.authorize() uses readiness signal
8. Regression — existing behavior unchanged when readiness unavailable
"""

from __future__ import annotations

import pytest

from agentic.safety.governance_patterns.readiness_checker import (
    ReadinessChecker,
    ReadinessConfig,
    ReadinessResult,
    ReadinessStatus,
)
from agentic.agentic_framework.signal_adapters.readiness_adapter import (
    ReadinessResolution,
    resolve_readiness_signal,
    _MAX_PENALTY_NOT_READY,
    _PENALTY_DEGRADED,
)


# =============================================================================
# 1. Adapter Contract Tests
# =============================================================================

class TestReadinessAdapterContract:
    """ReadinessResolution has correct shape and is frozen."""

    def test_resolution_is_frozen(self):
        res = resolve_readiness_signal(plasticity=0.8)
        with pytest.raises(AttributeError):
            res.ready = False  # type: ignore[misc]

    def test_resolution_fields_present(self):
        res = resolve_readiness_signal(plasticity=0.8)
        assert hasattr(res, "status")
        assert hasattr(res, "ready")
        assert hasattr(res, "plasticity")
        assert hasattr(res, "stability")
        assert hasattr(res, "pending_escalations")
        assert hasattr(res, "confidence_penalty")
        assert hasattr(res, "escalation_bias")
        assert hasattr(res, "reason_codes")
        assert hasattr(res, "readiness_reason")
        assert hasattr(res, "available")
        assert hasattr(res, "source_detail")

    def test_to_audit_dict_serializable(self):
        res = resolve_readiness_signal(
            plasticity=0.6,
            coherence_score=0.7,
        )
        d = res.to_audit_dict()
        assert isinstance(d, dict)
        assert "status" in d
        assert "ready" in d
        assert "reason_codes" in d
        assert isinstance(d["reason_codes"], list)
        for v in d.values():
            assert isinstance(v, (int, float, bool, str, list, type(None)))

    def test_available_when_plasticity_present(self):
        res = resolve_readiness_signal(plasticity=0.5)
        assert res.available is True

    def test_unavailable_when_no_plasticity(self):
        res = resolve_readiness_signal()
        assert res.available is False


# =============================================================================
# 2. Determinism Tests
# =============================================================================

class TestReadinessDeterminism:
    """Same inputs produce identical outputs."""

    def test_deterministic_100_runs(self):
        results = []
        for _ in range(100):
            res = resolve_readiness_signal(
                plasticity=0.6,
                coherence_score=0.7,
                escalation_level="none",
            )
            results.append((
                res.status, res.ready, res.confidence_penalty,
                res.escalation_bias, res.pending_escalations,
            ))
        assert len(set(results)) == 1

    def test_deterministic_unavailable(self):
        results = []
        for _ in range(100):
            res = resolve_readiness_signal()
            results.append((res.available, res.confidence_penalty))
        assert len(set(results)) == 1


# =============================================================================
# 3. Fail-Closed Tests
# =============================================================================

class TestReadinessFailClosed:
    """Missing plasticity → unavailable, zero penalty."""

    def test_no_inputs_zero_penalty(self):
        res = resolve_readiness_signal()
        assert res.confidence_penalty == 0.0
        assert res.escalation_bias is False
        assert res.available is False

    def test_none_plasticity_zero_penalty(self):
        res = resolve_readiness_signal(
            plasticity=None,
            coherence_score=0.8,
        )
        assert res.available is False
        assert res.confidence_penalty == 0.0

    def test_plasticity_only_still_available(self):
        """Plasticity alone is enough."""
        res = resolve_readiness_signal(plasticity=0.5)
        assert res.available is True


# =============================================================================
# 4. Bounded Penalty Tests
# =============================================================================

class TestReadinessBoundedPenalty:
    """Penalties are bounded per status."""

    def test_max_penalty_constants(self):
        assert _MAX_PENALTY_NOT_READY == 0.03
        assert _PENALTY_DEGRADED == 0.02

    def test_ready_zero_penalty(self):
        """READY → zero penalty."""
        res = resolve_readiness_signal(
            plasticity=0.6,
            coherence_score=0.8,
            escalation_level="none",
        )
        assert res.status == "ready"
        assert res.confidence_penalty == 0.0

    def test_not_ready_penalty(self):
        """Plasticity below min → NOT_READY → 0.03 penalty."""
        res = resolve_readiness_signal(
            plasticity=0.1,  # below default min_plasticity=0.30
            coherence_score=0.8,
            escalation_level="none",
        )
        assert res.status == "not_ready"
        assert res.confidence_penalty == _MAX_PENALTY_NOT_READY

    def test_degraded_penalty(self):
        """Pending escalation + above plasticity min → DEGRADED → 0.02."""
        res = resolve_readiness_signal(
            plasticity=0.6,
            coherence_score=0.8,
            escalation_level="confirm",  # treated as pending escalation
        )
        assert res.status == "degraded"
        assert res.confidence_penalty == _PENALTY_DEGRADED


# =============================================================================
# 5. Escalation Logic Tests
# =============================================================================

class TestReadinessEscalation:
    """Only NOT_READY triggers escalation."""

    def test_ready_no_escalation(self):
        res = resolve_readiness_signal(
            plasticity=0.6,
            escalation_level="none",
        )
        assert res.escalation_bias is False

    def test_not_ready_escalation(self):
        res = resolve_readiness_signal(
            plasticity=0.1,
            escalation_level="none",
        )
        assert res.status == "not_ready"
        assert res.escalation_bias is True

    def test_degraded_no_escalation(self):
        """DEGRADED adds penalty but NOT escalation."""
        res = resolve_readiness_signal(
            plasticity=0.6,
            escalation_level="confirm",
        )
        assert res.status == "degraded"
        assert res.escalation_bias is False

    def test_escalation_codes_present(self):
        res = resolve_readiness_signal(plasticity=0.1)
        assert "READINESS_NOT_READY" in res.reason_codes
        assert "READINESS_ESCALATION" in res.reason_codes


# =============================================================================
# 6. Status Transition Tests
# =============================================================================

class TestReadinessStatusTransitions:
    """Correct status for various input combinations."""

    def test_high_plasticity_no_escalations_ready(self):
        res = resolve_readiness_signal(
            plasticity=0.8,
            escalation_level="none",
        )
        assert res.ready is True
        assert res.status == "ready"

    def test_low_plasticity_not_ready(self):
        res = resolve_readiness_signal(
            plasticity=0.15,
            escalation_level="none",
        )
        assert res.ready is False
        assert res.status == "not_ready"

    def test_high_plasticity_halt_escalation_degraded(self):
        res = resolve_readiness_signal(
            plasticity=0.8,
            escalation_level="halt",
        )
        assert res.ready is False
        assert res.status == "degraded"

    def test_low_plasticity_plus_escalation_not_ready(self):
        """Low plasticity dominates over escalation."""
        res = resolve_readiness_signal(
            plasticity=0.1,
            escalation_level="confirm",
        )
        assert res.status == "not_ready"

    def test_notify_does_not_count_as_pending(self):
        """'notify' escalation is not a blocking pending escalation."""
        res = resolve_readiness_signal(
            plasticity=0.6,
            escalation_level="notify",
        )
        assert res.status == "ready"
        assert res.pending_escalations == 0

    def test_confirm_counts_as_pending(self):
        res = resolve_readiness_signal(
            plasticity=0.6,
            escalation_level="confirm",
        )
        assert res.pending_escalations == 1


# =============================================================================
# 7. Underlying ReadinessChecker Tests
# =============================================================================

class TestReadinessCheckerDirectly:
    """ReadinessChecker itself works correctly."""

    def test_all_clear(self):
        checker = ReadinessChecker()
        result = checker.check(plasticity=0.5, stability=0.8)
        assert result.status == ReadinessStatus.READY
        assert result.ready is True

    def test_low_plasticity_blocks(self):
        checker = ReadinessChecker()
        result = checker.check(plasticity=0.1, stability=0.8)
        assert result.status == ReadinessStatus.NOT_READY

    def test_pending_escalation_degrades(self):
        checker = ReadinessChecker()
        result = checker.check(
            plasticity=0.5,
            stability=0.8,
            pending_escalations=1,
        )
        assert result.status == ReadinessStatus.DEGRADED


# =============================================================================
# 8. Consumer-Level Tests: GovernanceService.authorize()
# =============================================================================

class TestReadinessGovernanceConsumer:
    """GovernanceService.authorize() materially uses readiness signal."""

    def test_authorize_includes_readiness_in_audit(self):
        """authorize() includes readiness provenance in audit metadata."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service = GovernanceService()
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="test readiness integration",
            metadata={
                "core_coherence_state": _MockCoherenceState(
                    coherence_score=0.7,
                    semantic_stability_score=0.7,
                    persona_drift_score=0.1,
                ),
            },
        )

        response = service.authorize(request)
        audit = response.audit_event
        assert audit is not None

        # Check flat provenance fields
        snapshot = audit.request_snapshot
        assert "readiness_available" in snapshot
        assert snapshot["readiness_available"] is True
        assert "readiness_status" in snapshot
        assert "readiness_ready" in snapshot
        assert "readiness_confidence_penalty" in snapshot
        assert "readiness_escalation_bias" in snapshot

        # Check structured audit dict
        assert audit.readiness_check is not None
        assert "status" in audit.readiness_check
        assert audit.readiness_check["available"] is True

    def test_authorize_readiness_unavailable_no_regression(self):
        """When no coherence state → no plasticity → no readiness, still works."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service = GovernanceService()
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="test no readiness",
            metadata={},
        )

        response = service.authorize(request)
        assert response is not None
        snapshot = response.audit_event.request_snapshot
        assert snapshot["readiness_available"] is False
        assert snapshot["readiness_confidence_penalty"] == 0.0

    def test_authorize_low_plasticity_readiness_not_ready(self):
        """Low coherence/high drift → low plasticity → NOT_READY → extra penalty."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        service = GovernanceService()
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="test not ready",
            metadata={
                "core_coherence_state": _MockCoherenceState(
                    coherence_score=0.05,
                    semantic_stability_score=0.05,
                    persona_drift_score=0.95,
                ),
            },
        )

        response = service.authorize(request)
        snapshot = response.audit_event.request_snapshot

        # Plasticity should be very low → readiness NOT_READY
        assert snapshot["readiness_available"] is True
        assert snapshot["readiness_status"] == "not_ready"
        assert snapshot["readiness_confidence_penalty"] == _MAX_PENALTY_NOT_READY
        assert snapshot["readiness_escalation_bias"] is True

    def test_authorize_readiness_penalty_reduces_confidence(self):
        """NOT_READY readiness should reduce effective confidence vs READY."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import (
            AuthorizationRequest,
        )

        # READY scenario: good coherence
        service_ready = GovernanceService()
        req_ready = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="ready scenario",
            metadata={
                "core_coherence_state": _MockCoherenceState(
                    coherence_score=0.9,
                    semantic_stability_score=0.9,
                    persona_drift_score=0.0,
                ),
            },
        )

        # NOT_READY scenario: bad coherence → low plasticity → not ready
        service_not_ready = GovernanceService()
        req_not_ready = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="not ready scenario",
            metadata={
                "core_coherence_state": _MockCoherenceState(
                    coherence_score=0.05,
                    semantic_stability_score=0.05,
                    persona_drift_score=0.95,
                ),
            },
        )

        resp_ready = service_ready.authorize(req_ready)
        resp_not_ready = service_not_ready.authorize(req_not_ready)

        # NOT_READY should have equal or lower confidence
        assert resp_not_ready.confidence_score <= resp_ready.confidence_score


# =============================================================================
# Mock helper
# =============================================================================

class _MockCoherenceState:
    """Minimal mock for CoherenceState duck-typed interface."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
