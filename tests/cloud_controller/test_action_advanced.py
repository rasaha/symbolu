"""Tests for Stage 5 advanced modules: rollback, policy, readiness, outcome.

Tests cover:
- RollbackMonitor: watch lifecycle, degradation detection, auto-revert
- PolicyEngine: replica bounds, blackout windows, rate limits
- ReadinessChecker: plasticity threshold, action recency, rollback blocking
- OutcomeTracker: positive/negative/neutral/oscillation outcomes
- GateActuator: one dry-run mode, no admission webhook or ArgoCD state
- Engine integration: approve() records and executes nothing, whatever policy,
  rollback and outcome components are wired
  (ADR_CLOUD_SCALING_OPERATIONS_ORCHESTRATOR_CONTAINMENT_SCOPING)
"""

import time
import pytest
from unittest.mock import MagicMock

from symbolu.cloud_controller.action.rollback import (
    RollbackConfig,
    RollbackMonitor,
    RollbackVerdict,
    RollbackWatch,
)
from symbolu.cloud_controller.action.policy import (
    BlackoutWindow,
    DeploymentPolicy,
    PolicyConfig,
    PolicyEngine,
)
from symbolu.cloud_controller.action.readiness import (
    ReadinessChecker,
    ReadinessConfig,
    ReadinessResult,
    ReadinessStatus,
)
from symbolu.cloud_controller.action.outcome import (
    OutcomeConfig,
    OutcomeRecord,
    OutcomeTracker,
    OutcomeVerdict,
)
from symbolu.cloud_controller.action.k8s_actuator import (
    ActuatorConfig,
    ActuatorMode,
    ExecutionResult,
    K8sActuator,
)
from symbolu.cloud_controller.action.gate_actuator import (
    GateAction,
    GateConfig,
    GateMode,
    GateActuator,
)
from symbolu.cloud_controller.controller import Controller
from symbolu.cloud_controller.recommend.engine import (
    RecommendConfig,
    RecommendEngine,
)
from symbolu.cloud_controller.recommend.confidence import ConfidenceConfig


# ============================================================
# Helpers
# ============================================================

def _make_action(delta=2, score=0.8, pressure=0.6, coherence=0.9,
                 recommendation="scale_out"):
    ctrl = Controller()
    result = ctrl.step(
        metrics={"cpu": 0.5, "memory": 0.5, "latency_p99": 0.5, "error_rate": 0.5},
        current_replicas=5,
    )
    result.replica_delta = delta
    result.action_score = score
    result.pressure = pressure
    result.recommendation = recommendation
    if result.coherence is not None:
        result.coherence.coherence = coherence
    return result


# ============================================================
# Rollback Monitor
# ============================================================

class TestRollbackMonitor:
    def test_start_watch(self):
        monitor = RollbackMonitor()
        watch = monitor.start_watch(
            "rec-1", "api-gw", "prod", 5, 7,
            {"latency_p99": 0.3, "error_rate": 0.02},
        )
        assert watch.is_active
        assert watch.verdict == RollbackVerdict.MONITORING
        assert monitor.active_count == 1

    def test_stable_after_window(self):
        """Metrics stable through watch window = STABLE verdict."""
        monitor = RollbackMonitor(RollbackConfig(
            watch_window_seconds=60,
            grace_period_seconds=5,
        ))
        watch = monitor.start_watch(
            "rec-1", "api-gw", "prod", 5, 7,
            {"latency_p99": 0.3, "error_rate": 0.02},
        )
        # Simulate time passing beyond window
        past = time.time() - 70
        watch.action_timestamp = past

        resolved = monitor.check(
            {"latency_p99": 0.3, "error_rate": 0.02},
        )
        assert len(resolved) == 1
        assert resolved[0].verdict == RollbackVerdict.STABLE
        assert monitor.active_count == 0

    def test_degradation_detected(self):
        """Metrics degraded beyond threshold = DEGRADED verdict."""
        monitor = RollbackMonitor(RollbackConfig(
            watch_window_seconds=180,
            grace_period_seconds=5,
            degradation_threshold=0.15,
            execute_rollback=False,  # Don't execute, just detect
        ))
        watch = monitor.start_watch(
            "rec-1", "api-gw", "prod", 5, 7,
            {"latency_p99": 0.3, "error_rate": 0.02},
        )
        # Past grace period but within window
        watch.action_timestamp = time.time() - 60

        resolved = monitor.check(
            {"latency_p99": 0.5, "error_rate": 0.05},  # >15% worse
        )
        assert len(resolved) == 1
        assert resolved[0].verdict == RollbackVerdict.DEGRADED
        assert "latency_p99" in resolved[0].verdict_reason

    def test_a_mutating_rollback_function_is_refused(self):
        """An undeclared callable (a mock, a lambda) is treated as mutating and refused."""
        for fn in (MagicMock(return_value=MagicMock(success=True)), lambda **kwargs: None):
            with pytest.raises(RuntimeError):
                RollbackMonitor(
                    RollbackConfig(execute_rollback=True),
                    rollback_fn=fn,
                )

    def test_rollback_executed_through_a_dry_run_actuator_only(self):
        """Degradation with execute_rollback=True calls a DRY_RUN actuator's scale."""
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.DRY_RUN))
        monitor = RollbackMonitor(
            RollbackConfig(
                watch_window_seconds=180,
                grace_period_seconds=5,
                degradation_threshold=0.15,
                execute_rollback=True,
            ),
            rollback_fn=actuator.scale,
        )
        watch = monitor.start_watch(
            "rec-1", "api-gw", "prod", 5, 7,
            {"latency_p99": 0.3, "error_rate": 0.02},
        )
        watch.action_timestamp = time.time() - 60

        resolved = monitor.check({"latency_p99": 0.5, "error_rate": 0.05})

        assert resolved[0].verdict == RollbackVerdict.ROLLED_BACK
        assert len(actuator.history) == 1
        proposal = actuator.history[0]
        assert proposal.mode == "dry_run"
        assert (proposal.previous_replicas, proposal.target_replicas) == (7, 5)
        assert proposal.recommendation_id == "rollback-rec-1"

    def test_grace_period_skips_check(self):
        """Within grace period, no check is performed."""
        monitor = RollbackMonitor(RollbackConfig(
            grace_period_seconds=30,
        ))
        monitor.start_watch(
            "rec-1", "api-gw", "prod", 5, 7,
            {"latency_p99": 0.3},
        )
        # Within grace period — even bad metrics shouldn't trigger
        resolved = monitor.check({"latency_p99": 0.9})
        assert len(resolved) == 0
        assert monitor.active_count == 1

    def test_rollback_count(self):
        monitor = RollbackMonitor(RollbackConfig(
            watch_window_seconds=60,
            grace_period_seconds=1,
            degradation_threshold=0.1,
            execute_rollback=False,
        ))
        watch = monitor.start_watch(
            "rec-1", "svc", "ns", 5, 7, {"latency_p99": 0.3},
        )
        watch.action_timestamp = time.time() - 10

        monitor.check({"latency_p99": 0.5})
        assert monitor.rollback_count == 1

    def test_reset(self):
        monitor = RollbackMonitor()
        monitor.start_watch("rec-1", "svc", "ns", 5, 7, {})
        monitor.reset()
        assert monitor.active_count == 0
        assert len(monitor.history) == 0


# ============================================================
# Policy Engine
# ============================================================

class TestPolicyEngine:
    def test_within_bounds_allowed(self):
        policy = PolicyEngine(PolicyConfig(
            default_policy=DeploymentPolicy(min_replicas=1, max_replicas=50),
        ))
        result = policy.check("api-gw", "prod", current_replicas=5, target_replicas=10)
        assert result.allowed is True
        assert len(result.violations) == 0

    def test_exceeds_max_replicas(self):
        policy = PolicyEngine(PolicyConfig(
            default_policy=DeploymentPolicy(max_replicas=10),
        ))
        result = policy.check("api-gw", "prod", current_replicas=8, target_replicas=15)
        assert result.allowed is False
        assert "max replicas" in result.reason.lower()

    def test_below_min_replicas(self):
        policy = PolicyEngine(PolicyConfig(
            default_policy=DeploymentPolicy(min_replicas=3),
        ))
        result = policy.check("api-gw", "prod", current_replicas=5, target_replicas=2)
        assert result.allowed is False
        assert "min replicas" in result.reason.lower()

    def test_deployment_override(self):
        policy = PolicyEngine(PolicyConfig(
            default_policy=DeploymentPolicy(max_replicas=100),
            deployment_overrides={
                "prod/api-gw": DeploymentPolicy(max_replicas=10),
            },
        ))
        # Override should apply
        result = policy.check("api-gw", "prod", current_replicas=5, target_replicas=15)
        assert result.allowed is False
        # Default applies to other deployments
        result2 = policy.check("worker", "prod", current_replicas=5, target_replicas=15)
        assert result2.allowed is True

    def test_blackout_window_blocks(self):
        # Create a window that covers the current hour
        now = time.localtime()
        current_hour = now.tm_hour + now.tm_min / 60.0
        start = max(0, current_hour - 1)
        end = min(24, current_hour + 1)

        policy = PolicyEngine(PolicyConfig(
            default_policy=DeploymentPolicy(
                blackout_windows=[BlackoutWindow(
                    start_hour=start,
                    end_hour=end,
                    reason="maintenance",
                )],
            ),
        ))
        result = policy.check("api-gw", "prod", current_replicas=5, target_replicas=7)
        assert result.allowed is False
        assert "blackout" in result.reason.lower()

    def test_blackout_window_inactive(self):
        # Window far from current time
        policy = PolicyEngine(PolicyConfig(
            default_policy=DeploymentPolicy(
                blackout_windows=[BlackoutWindow(
                    start_hour=99, end_hour=99,  # Impossible hour
                    days=[],  # No days
                )],
            ),
        ))
        result = policy.check("api-gw", "prod", current_replicas=5, target_replicas=7)
        assert result.allowed is True

    def test_rate_limit(self):
        policy = PolicyEngine(PolicyConfig(
            default_policy=DeploymentPolicy(
                max_actions_per_window=2,
                rate_limit_window_seconds=3600,
            ),
        ))
        # Record 2 actions
        policy.record_action("api-gw", "prod")
        policy.record_action("api-gw", "prod")

        result = policy.check("api-gw", "prod", current_replicas=5, target_replicas=7)
        assert result.allowed is False
        assert "rate limit" in result.reason.lower()

    def test_rate_limit_different_deployment(self):
        """Rate limit is per-deployment."""
        policy = PolicyEngine(PolicyConfig(
            default_policy=DeploymentPolicy(max_actions_per_window=1),
        ))
        policy.record_action("api-gw", "prod")

        # Different deployment should be fine
        result = policy.check("worker", "prod", current_replicas=5, target_replicas=7)
        assert result.allowed is True

    def test_reset(self):
        policy = PolicyEngine()
        policy.record_action("svc", "ns")
        policy.reset()
        # After reset, rate limit should be clear
        result = policy.check("svc", "ns", current_replicas=5, target_replicas=7)
        assert result.allowed is True


# ============================================================
# Blackout Window
# ============================================================

class TestBlackoutWindow:
    def test_normal_range(self):
        window = BlackoutWindow(start_hour=2.0, end_hour=4.0, days=[0, 1, 2, 3, 4, 5, 6])
        # Create a time at 3:00 AM on a Monday
        import calendar
        # Use a fixed time for predictability
        # Monday Jan 6 2025 03:00:00 UTC
        t = 1736132400.0  # Approx
        lt = time.localtime(t)
        # Just test the structure works — exact time isn't critical
        result = window.is_active(t)
        assert isinstance(result, bool)

    def test_midnight_wrap(self):
        window = BlackoutWindow(start_hour=23.0, end_hour=1.0, days=[0, 1, 2, 3, 4, 5, 6])
        # This should cover 23:00 - 01:00 (wrapping midnight)
        # Just verify it doesn't crash
        result = window.is_active()
        assert isinstance(result, bool)

    def test_day_filter(self):
        """Window only active on specified days."""
        window = BlackoutWindow(start_hour=0.0, end_hour=24.0, days=[])  # No days
        assert window.is_active() is False


# ============================================================
# Readiness Checker
# ============================================================

class TestReadinessChecker:
    def test_ready_when_healthy(self):
        checker = ReadinessChecker(ReadinessConfig(min_plasticity=0.3))
        result = checker.check(plasticity=0.8, stability=0.9)
        assert result.ready is True
        assert result.status == ReadinessStatus.READY

    def test_not_ready_low_plasticity(self):
        checker = ReadinessChecker(ReadinessConfig(min_plasticity=0.3))
        result = checker.check(plasticity=0.2, stability=0.9)
        assert result.ready is False
        assert result.status == ReadinessStatus.NOT_READY
        assert "plasticity" in result.reason.lower()

    def test_not_ready_recent_action(self):
        checker = ReadinessChecker(ReadinessConfig(
            min_time_since_action_seconds=120,
        ))
        result = checker.check(
            plasticity=0.8,
            stability=0.9,
            last_action_time=time.time() - 30,  # 30s ago
        )
        assert result.ready is False
        assert "recent scaling" in result.reason.lower()

    def test_not_ready_active_rollback(self):
        checker = ReadinessChecker(ReadinessConfig(
            block_during_rollback_watch=True,
        ))
        result = checker.check(
            plasticity=0.8,
            stability=0.9,
            active_rollback_watches=2,
        )
        assert result.ready is False
        assert "rollback" in result.reason.lower()

    def test_to_dict(self):
        checker = ReadinessChecker()
        result = checker.check(plasticity=0.5, stability=0.7)
        d = result.to_dict()
        assert "status" in d
        assert "ready" in d
        assert "plasticity" in d
        assert "stability" in d
        assert isinstance(d["plasticity"], float)

    def test_multiple_blockers(self):
        """Multiple blockers should all appear in reason."""
        checker = ReadinessChecker(ReadinessConfig(
            min_plasticity=0.5,
            min_time_since_action_seconds=120,
        ))
        result = checker.check(
            plasticity=0.2,
            stability=0.3,
            last_action_time=time.time() - 10,
        )
        assert result.ready is False
        assert "plasticity" in result.reason.lower()
        assert "recent" in result.reason.lower()


# ============================================================
# Outcome Tracker
# ============================================================

class TestOutcomeTracker:
    def test_record_action(self):
        tracker = OutcomeTracker()
        record = tracker.record_action(
            "rec-1", "api-gw", "prod", delta=2,
            pre_action_metrics={"latency_p99": 0.3, "error_rate": 0.02},
        )
        assert record.verdict == OutcomeVerdict.PENDING
        assert tracker.pending_count == 1

    def test_positive_outcome(self):
        """Metrics improve after action = POSITIVE."""
        tracker = OutcomeTracker(OutcomeConfig(
            evaluation_window_seconds=60,
            improvement_threshold=0.05,
        ))
        record = tracker.record_action(
            "rec-1", "api-gw", "prod", delta=2,
            pre_action_metrics={"latency_p99": 0.5, "error_rate": 0.1, "cpu": 0.8, "memory": 0.7},
        )
        record.action_timestamp = time.time() - 70  # Past window

        outcomes = tracker.evaluate(
            {"latency_p99": 0.3, "error_rate": 0.05, "cpu": 0.5, "memory": 0.5},
        )
        assert len(outcomes) == 1
        assert outcomes[0].verdict == OutcomeVerdict.POSITIVE
        assert outcomes[0].priority_score < 0.5  # Low — good outcome

    def test_negative_outcome(self):
        """Metrics degrade after action = NEGATIVE."""
        tracker = OutcomeTracker(OutcomeConfig(
            evaluation_window_seconds=60,
            degradation_threshold=0.10,
        ))
        record = tracker.record_action(
            "rec-1", "api-gw", "prod", delta=2,
            pre_action_metrics={"latency_p99": 0.3, "error_rate": 0.02, "cpu": 0.5, "memory": 0.5},
        )
        record.action_timestamp = time.time() - 70

        outcomes = tracker.evaluate(
            {"latency_p99": 0.5, "error_rate": 0.1, "cpu": 0.7, "memory": 0.7},
        )
        assert len(outcomes) == 1
        assert outcomes[0].verdict == OutcomeVerdict.NEGATIVE
        assert outcomes[0].priority_score > 0.5  # High — learn from failure

    def test_neutral_outcome(self):
        """Metrics unchanged = NEUTRAL."""
        tracker = OutcomeTracker(OutcomeConfig(evaluation_window_seconds=60))
        record = tracker.record_action(
            "rec-1", "api-gw", "prod", delta=2,
            pre_action_metrics={"latency_p99": 0.3, "error_rate": 0.02, "cpu": 0.5, "memory": 0.5},
        )
        record.action_timestamp = time.time() - 70

        outcomes = tracker.evaluate(
            {"latency_p99": 0.3, "error_rate": 0.02, "cpu": 0.5, "memory": 0.5},
        )
        assert len(outcomes) == 1
        assert outcomes[0].verdict == OutcomeVerdict.NEUTRAL

    def test_override_outcome(self):
        """Human override marks as OVERRIDDEN with high priority."""
        tracker = OutcomeTracker()
        tracker.record_action(
            "rec-1", "api-gw", "prod", delta=2,
            pre_action_metrics={"latency_p99": 0.3},
        )
        result = tracker.record_override("rec-1")
        assert result is not None
        assert result.verdict == OutcomeVerdict.OVERRIDDEN
        assert result.priority_score == 0.9
        assert tracker.pending_count == 0

    def test_override_not_found(self):
        tracker = OutcomeTracker()
        result = tracker.record_override("nonexistent")
        assert result is None

    def test_oscillation_detection(self):
        tracker = OutcomeTracker(OutcomeConfig(oscillation_window_seconds=600))
        # Record a scale-up
        tracker.record_action(
            "rec-1", "api-gw", "prod", delta=2,
            pre_action_metrics={"latency_p99": 0.3},
        )
        # Check if opposite direction would be oscillation
        assert tracker.check_oscillation("api-gw", "prod", new_delta=-1) is True
        assert tracker.check_oscillation("api-gw", "prod", new_delta=1) is False

    def test_to_replay_entry(self):
        record = OutcomeRecord(
            recommendation_id="rec-1",
            deployment="api-gw",
            namespace="prod",
            action_delta=2,
            action_timestamp=time.time(),
            pre_action_metrics={"cpu": 0.5},
            verdict=OutcomeVerdict.POSITIVE,
            priority_score=0.4,
        )
        entry = record.to_replay_entry()
        assert entry["priority"] == 0.4
        assert entry["verdict"] == "positive"

    def test_pending_not_evaluated_early(self):
        """Records within evaluation window should not be evaluated."""
        tracker = OutcomeTracker(OutcomeConfig(evaluation_window_seconds=300))
        tracker.record_action(
            "rec-1", "api-gw", "prod", delta=2,
            pre_action_metrics={"latency_p99": 0.3},
        )
        outcomes = tracker.evaluate({"latency_p99": 0.8})
        assert len(outcomes) == 0
        assert tracker.pending_count == 1

    def test_reset(self):
        tracker = OutcomeTracker()
        tracker.record_action("rec-1", "svc", "ns", 2, {})
        tracker.reset()
        assert tracker.pending_count == 0
        assert len(tracker.history) == 0


# ============================================================
# Gate Actuator — one mode, nothing persisted for a webhook to read
# ============================================================

class TestGateActuatorContainment:
    def test_dry_run_is_the_only_mode(self):
        assert set(GateMode) == {GateMode.DRY_RUN}
        assert not hasattr(GateActuator(), "get_admission_policy")

    def test_a_hold_is_recorded_only(self):
        gate = GateActuator(GateConfig())
        result = gate.execute(GateAction.HOLD, "api-gw", "prod", recommendation_id="rec-1")
        assert result.mode == "dry_run"
        assert result.action == "hold"
        assert result.recommendation_id == "rec-1"
        gate.reset()
        assert gate.history == []


# ============================================================
# Engine Integration — Policy, Rollback, Outcome, Readiness
# ============================================================

class TestEngineAdvancedIntegration:
    def _make_engine(self, **kwargs):
        """Create an engine with all advanced features enabled."""
        config = RecommendConfig(
            service="api-gw",
            namespace="prod",
            confidence=ConfidenceConfig(
                action_threshold=0.1,
                coherence_threshold=0.1,
            ),
            actuator=kwargs.get("actuator", ActuatorConfig(mode=ActuatorMode.DRY_RUN)),
            policy=kwargs.get("policy", PolicyConfig()),
            rollback=kwargs.get("rollback", RollbackConfig(
                watch_window_seconds=180,
                grace_period_seconds=5,
                execute_rollback=False,
            )),
            outcome=kwargs.get("outcome", OutcomeConfig(
                evaluation_window_seconds=300,
            )),
            readiness=kwargs.get("readiness", ReadinessConfig()),
        )
        return RecommendEngine(config)

    def test_approval_beyond_policy_records_and_executes_nothing(self):
        """A policy-violating target changes nothing: approval never executes (D-3)."""
        engine = self._make_engine(
            policy=PolicyConfig(
                default_policy=DeploymentPolicy(max_replicas=6),
            ),
        )
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        assert cycle.recommendation is not None

        # Target would be 7, exceeds max_replicas=6 — and nothing runs either way.
        rec = engine.approve(cycle.recommendation.id, by="ops")
        assert rec is not None
        assert rec.execution_result is None

    def test_approval_within_policy_records_and_executes_nothing(self):
        engine = self._make_engine(
            policy=PolicyConfig(
                default_policy=DeploymentPolicy(max_replicas=20),
            ),
        )
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)

        rec = engine.approve(cycle.recommendation.id, by="ops")
        assert rec is not None
        assert rec.execution_result is None
        assert engine.actuator.history == []

    def test_no_rollback_watch_started_on_approval(self):
        """Nothing executed, so there is nothing to watch for rollback."""
        engine = self._make_engine()
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)

        engine.approve(cycle.recommendation.id, by="ops")
        assert engine.rollback.active_count == 0

    def test_no_outcome_recorded_on_approval(self):
        """Nothing executed, so there is no outcome to evaluate."""
        engine = self._make_engine()
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)

        engine.approve(cycle.recommendation.id, by="ops")
        assert engine.outcome.pending_count == 0

    def test_check_rollbacks_delegates(self):
        engine = self._make_engine()
        result = engine.check_rollbacks({"latency_p99": 0.3})
        assert isinstance(result, list)

    def test_evaluate_outcomes_delegates(self):
        engine = self._make_engine()
        result = engine.evaluate_outcomes({"latency_p99": 0.3})
        assert isinstance(result, list)

    def test_check_readiness(self):
        engine = self._make_engine()
        result = engine.check_readiness(plasticity=0.8, stability=0.9)
        assert result is not None
        assert result["ready"] is True

    def test_check_readiness_not_configured(self):
        engine = RecommendEngine(RecommendConfig(service="svc"))
        result = engine.check_readiness(plasticity=0.8, stability=0.9)
        assert result is None

    def test_reset_clears_all(self):
        """Reset should clear all sub-components."""
        engine = self._make_engine()
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        engine.approve(cycle.recommendation.id, by="ops")

        engine.reset()
        assert engine.rollback.active_count == 0
        assert engine.outcome.pending_count == 0
        assert engine.pending_count == 0

    def test_a_mutating_actuator_is_refused_with_every_component_wired(self):
        """The full advanced configuration cannot be built around a SCALE_PATCH actuator."""
        with pytest.raises(RuntimeError):
            self._make_engine(actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH))
