"""
S5 Rollback Monitor Integration Tests
========================================

Tests for Phase S5-safety: RollbackMonitor lifecycle-preparatory integration.

Test categories:
1. Adapter contract — resolution shape, frozen, serialization
2. Deterministic behavior — same inputs → identical outputs
3. Fail-safe — no monitor → no snapshot, no effect
4. Watch lifecycle — start, check degradation, check stable, expiry
5. Signal snapshot — correct signals captured from governance state
6. Consumer-level — GovernanceService.authorize() captures snapshots
7. Regression — existing behavior unchanged when no monitor configured
"""

from __future__ import annotations

import pytest

from agentic.safety.governance_patterns.rollback_monitor import (
    RollbackConfig,
    RollbackMonitor,
    RollbackVerdict,
    RollbackWatch,
)
from agentic.agentic_framework.signal_adapters.rollback_adapter import (
    RollbackSnapshotResolution,
    resolve_rollback_snapshot,
)


# =============================================================================
# 1. Adapter Contract Tests
# =============================================================================

class TestRollbackAdapterContract:
    """RollbackSnapshotResolution has correct shape and is frozen."""

    def test_resolution_is_frozen(self):
        res = resolve_rollback_snapshot(
            monitor=None,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
        )
        with pytest.raises(AttributeError):
            res.watch_started = True  # type: ignore[misc]

    def test_resolution_fields_present(self):
        res = resolve_rollback_snapshot(
            monitor=None,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
        )
        assert hasattr(res, "watch_started")
        assert hasattr(res, "decision_id")
        assert hasattr(res, "agent_id")
        assert hasattr(res, "action_type")
        assert hasattr(res, "pre_action_signals")
        assert hasattr(res, "watch_id")
        assert hasattr(res, "available")
        assert hasattr(res, "source_detail")

    def test_to_audit_dict_serializable(self):
        monitor = RollbackMonitor()
        res = resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
            confidence=0.75,
        )
        d = res.to_audit_dict()
        assert isinstance(d, dict)
        assert "watch_started" in d
        assert "pre_action_signals" in d
        assert isinstance(d["pre_action_signals"], dict)
        # All values must be JSON-serializable primitives or dicts/lists
        for k, v in d.items():
            assert isinstance(v, (int, float, bool, str, list, dict, type(None))), (
                f"Non-serializable value for key {k}: {type(v)}"
            )

    def test_available_when_monitor_present(self):
        monitor = RollbackMonitor()
        res = resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
        )
        assert res.available is True

    def test_unavailable_when_no_monitor(self):
        res = resolve_rollback_snapshot(
            monitor=None,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
        )
        assert res.available is False


# =============================================================================
# 2. Determinism Tests
# =============================================================================

class TestRollbackDeterminism:
    """Same inputs produce consistent outputs (modulo watch registration)."""

    def test_no_monitor_deterministic(self):
        """Without a monitor, resolution is fully deterministic."""
        results = []
        for _ in range(50):
            res = resolve_rollback_snapshot(
                monitor=None,
                decision_id="dec-1",
                agent_id="agent-1",
                action_type="tool_execution",
            )
            results.append((
                res.watch_started, res.available,
                res.decision_id, res.agent_id,
            ))
        assert len(set(results)) == 1

    def test_with_monitor_fields_consistent(self):
        """With a monitor, core fields are consistent across calls."""
        monitor = RollbackMonitor()
        for _ in range(10):
            res = resolve_rollback_snapshot(
                monitor=monitor,
                decision_id="dec-same",
                agent_id="agent-same",
                action_type="tool_execution",
                confidence=0.80,
                plasticity=0.60,
            )
            assert res.watch_started is True
            assert res.decision_id == "dec-same"
            assert res.agent_id == "agent-same"
            assert res.pre_action_signals["confidence"] == 0.80
            assert res.pre_action_signals["plasticity"] == 0.60


# =============================================================================
# 3. Fail-Safe Tests
# =============================================================================

class TestRollbackFailSafe:
    """No monitor → no snapshot, no effect."""

    def test_no_monitor_no_watch(self):
        res = resolve_rollback_snapshot(
            monitor=None,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
        )
        assert res.watch_started is False
        assert res.available is False
        assert res.watch_id is None
        assert len(res.pre_action_signals) == 0
        assert res.source_detail == "no_rollback_monitor"

    def test_no_monitor_does_not_crash(self):
        """Should never raise, even with unusual inputs."""
        res = resolve_rollback_snapshot(
            monitor=None,
            decision_id="",
            agent_id="",
            action_type="",
            confidence=-1.0,
        )
        assert res.available is False


# =============================================================================
# 4. Watch Lifecycle Tests
# =============================================================================

class TestRollbackWatchLifecycle:
    """RollbackMonitor start_watch → check → verdict lifecycle."""

    def test_start_watch_creates_active_watch(self):
        monitor = RollbackMonitor()
        res = resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-lc-1",
            agent_id="agent-1",
            action_type="deploy",
            confidence=0.85,
        )
        assert res.watch_started is True
        assert monitor.active_count == 1

    def test_check_detects_degradation(self):
        """Post-action check with degraded signals → DEGRADED verdict."""
        config = RollbackConfig(
            degradation_threshold=0.15,
            grace_period_seconds=0.0,
            watch_window_seconds=60.0,
            execute_rollback=False,  # no rollback fn
        )
        monitor = RollbackMonitor(config=config)

        # Capture pre-action snapshot
        resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-deg",
            agent_id="agent-1",
            action_type="deploy",
            confidence=0.85,
            coherence=0.80,
        )

        # Simulate post-action check with degraded signals
        import time
        now = time.time()
        resolved = monitor.check(
            current_signals={"confidence": 0.50, "coherence": 0.50},
            current_time=now + 1.0,
        )
        assert len(resolved) == 1
        assert resolved[0].verdict == RollbackVerdict.DEGRADED

    def test_check_stable_after_window(self):
        """Post-action check after window → STABLE verdict."""
        config = RollbackConfig(
            watch_window_seconds=10.0,
            grace_period_seconds=0.0,
        )
        monitor = RollbackMonitor(config=config)

        resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-stb",
            agent_id="agent-1",
            action_type="deploy",
            confidence=0.85,
        )

        # Check after window has passed
        import time
        now = time.time()
        resolved = monitor.check(
            current_signals={"confidence": 0.85},
            current_time=now + 20.0,
        )
        assert len(resolved) == 1
        assert resolved[0].verdict == RollbackVerdict.STABLE

    def test_check_within_grace_period_stays_monitoring(self):
        """Check during grace period → no resolution."""
        config = RollbackConfig(
            grace_period_seconds=30.0,
            watch_window_seconds=180.0,
        )
        monitor = RollbackMonitor(config=config)

        resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-gp",
            agent_id="agent-1",
            action_type="deploy",
            confidence=0.85,
        )

        import time
        now = time.time()
        resolved = monitor.check(
            current_signals={"confidence": 0.10},  # very degraded
            current_time=now + 5.0,  # still in grace period
        )
        assert len(resolved) == 0
        assert monitor.active_count == 1

    def test_multiple_watches_independent(self):
        """Multiple watches resolve independently."""
        config = RollbackConfig(
            grace_period_seconds=0.0,
            watch_window_seconds=60.0,
            execute_rollback=False,
            degradation_threshold=0.15,
        )
        monitor = RollbackMonitor(config=config)

        # Start two watches
        resolve_rollback_snapshot(
            monitor=monitor, decision_id="dec-a",
            agent_id="agent-a", action_type="deploy",
            confidence=0.90,
        )
        resolve_rollback_snapshot(
            monitor=monitor, decision_id="dec-b",
            agent_id="agent-b", action_type="query",
            confidence=0.50,
        )
        assert monitor.active_count == 2

        import time
        now = time.time()
        # Only confidence degrades for dec-a (0.90 → 0.50 = -44%)
        # dec-b stays stable (0.50 → 0.50 = 0%)
        resolved = monitor.check(
            current_signals={"confidence": 0.50},
            current_time=now + 1.0,
        )
        assert len(resolved) == 1
        assert resolved[0].decision_id == "dec-a"
        assert resolved[0].verdict == RollbackVerdict.DEGRADED
        assert monitor.active_count == 1


# =============================================================================
# 5. Signal Snapshot Tests
# =============================================================================

class TestRollbackSignalSnapshot:
    """Correct signals captured from governance state."""

    def test_confidence_always_captured(self):
        monitor = RollbackMonitor()
        res = resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
            confidence=0.75,
        )
        assert "confidence" in res.pre_action_signals
        assert res.pre_action_signals["confidence"] == 0.75

    def test_plasticity_captured_when_available(self):
        monitor = RollbackMonitor()
        res = resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
            confidence=0.80,
            plasticity=0.65,
        )
        assert "plasticity" in res.pre_action_signals
        assert res.pre_action_signals["plasticity"] == 0.65

    def test_coherence_captured_when_available(self):
        monitor = RollbackMonitor()
        res = resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
            confidence=0.80,
            coherence=0.70,
        )
        assert "coherence" in res.pre_action_signals
        assert res.pre_action_signals["coherence"] == 0.70

    def test_governance_strength_computed(self):
        """governance_strength is average of available sub-signals."""
        monitor = RollbackMonitor()
        res = resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
            confidence=0.80,
            plasticity=0.60,
            coherence=0.80,
        )
        assert "governance_strength" in res.pre_action_signals
        expected = round((0.60 + 0.80) / 2, 4)
        assert res.pre_action_signals["governance_strength"] == expected

    def test_no_governance_strength_without_sub_signals(self):
        """governance_strength not computed when only confidence present."""
        monitor = RollbackMonitor()
        res = resolve_rollback_snapshot(
            monitor=monitor,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
            confidence=0.80,
        )
        assert "governance_strength" not in res.pre_action_signals

    def test_no_signals_when_no_monitor(self):
        res = resolve_rollback_snapshot(
            monitor=None,
            decision_id="dec-1",
            agent_id="agent-1",
            action_type="tool_execution",
            confidence=0.80,
            plasticity=0.60,
        )
        assert len(res.pre_action_signals) == 0


# =============================================================================
# 6. Consumer-Level Tests: GovernanceService.authorize()
# =============================================================================

class TestRollbackGovernanceConsumer:
    """GovernanceService.authorize() captures rollback snapshots."""

    def test_authorize_no_monitor_no_effect(self):
        """Without monitor, authorize works normally (no rollback audit)."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        service = GovernanceService()  # no rollback_monitor
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="test no rollback",
        )

        response = service.authorize(request)
        assert response is not None
        snapshot = response.audit_event.request_snapshot
        assert snapshot["rollback_available"] is False
        assert snapshot["rollback_watch_started"] is False
        assert snapshot["rollback_watch_id"] is None
        # No structured rollback_watch in audit event
        assert response.audit_event.rollback_watch is None

    def test_authorize_with_monitor_captures_snapshot(self):
        """Monitor configured → pre-action snapshot captured in audit."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        monitor = RollbackMonitor()
        service = GovernanceService(rollback_monitor=monitor)
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="test rollback snapshot",
        )

        response = service.authorize(request)
        snapshot = response.audit_event.request_snapshot
        assert snapshot["rollback_available"] is True
        assert snapshot["rollback_watch_started"] is True
        assert snapshot["rollback_watch_id"] is not None

        # Structured rollback_watch dict present in audit event
        assert response.audit_event.rollback_watch is not None
        rw = response.audit_event.rollback_watch
        assert rw["watch_started"] is True
        assert "confidence" in rw["pre_action_signals"]

    def test_authorize_monitor_registers_active_watch(self):
        """Authorize with monitor → one active watch in monitor."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        monitor = RollbackMonitor()
        service = GovernanceService(rollback_monitor=monitor)

        assert monitor.active_count == 0

        request = AuthorizationRequest(
            action_type="deploy_model",
            actor_id="agent-7",
            confidence_score=0.9,
            context_summary="deploy test",
        )
        service.authorize(request)
        assert monitor.active_count == 1

        # Second authorize → second watch
        service.authorize(request)
        assert monitor.active_count == 2

    def test_authorize_monitor_does_not_affect_decision(self):
        """Rollback monitor is purely observational — does not change ALLOW/DENY."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        # Without monitor
        service_no_mon = GovernanceService()
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="comparison test",
        )
        resp_no = service_no_mon.authorize(request)

        # With monitor
        monitor = RollbackMonitor()
        service_with_mon = GovernanceService(rollback_monitor=monitor)
        resp_yes = service_with_mon.authorize(request)

        # Governance decision, eligibility, and confidence should match
        assert resp_no.governance_decision == resp_yes.governance_decision
        assert resp_no.eligible == resp_yes.eligible

    def test_authorize_then_external_check_degradation(self):
        """Full lifecycle: authorize → external check with degraded signals."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        config = RollbackConfig(
            degradation_threshold=0.15,
            grace_period_seconds=0.0,
            watch_window_seconds=60.0,
            execute_rollback=False,
        )
        monitor = RollbackMonitor(config=config)
        service = GovernanceService(rollback_monitor=monitor)

        request = AuthorizationRequest(
            action_type="deploy_model",
            actor_id="agent-deploy",
            confidence_score=0.9,
            context_summary="deploy lifecycle test",
        )
        response = service.authorize(request)

        # Verify watch was registered
        assert monitor.active_count == 1

        # External caller checks with degraded signals
        import time
        now = time.time()
        resolved = monitor.check(
            current_signals={"confidence": 0.10},
            current_time=now + 1.0,
        )
        assert len(resolved) == 1
        assert resolved[0].verdict == RollbackVerdict.DEGRADED
        assert monitor.active_count == 0


# =============================================================================
# 7. Regression Tests
# =============================================================================

class TestRollbackRegression:
    """Existing behavior unchanged when no monitor configured."""

    def test_default_service_no_rollback_in_audit(self):
        """Default GovernanceService has no rollback_watch in audit."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        service = GovernanceService()
        request = AuthorizationRequest(
            action_type="read_file",
            actor_id="normal-agent",
            confidence_score=0.7,
            context_summary="regression test",
        )
        response = service.authorize(request)
        assert response.audit_event.rollback_watch is None

    def test_all_previous_audit_fields_still_present(self):
        """Ensure rollback addition didn't break existing audit fields."""
        from agentic.agentic_framework.governance_service import GovernanceService
        from agentic.agentic_framework.governance_models import AuthorizationRequest

        service = GovernanceService()
        request = AuthorizationRequest(
            action_type="tool_execution",
            actor_id="test-actor",
            confidence_score=0.8,
            context_summary="regression audit check",
        )
        response = service.authorize(request)
        snapshot = response.audit_event.request_snapshot

        # Verify key pre-existing fields still present
        assert "actor_id" in snapshot
        assert "action_type" in snapshot
        assert "agent_policy_available" in snapshot
        assert "readiness_available" in snapshot
        assert "plasticity_available" in snapshot
        assert "rollback_available" in snapshot
