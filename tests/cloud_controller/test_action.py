"""Unit tests for Stage 5 — Action Layer (K8s Actuator + Gate Actuator).

Tests cover:
- K8sActuator: dry_run, scale_patch through an injected client only, history, retries
- GateActuator: dry_run, its one mode; no ArgoCD access, no token
- Engine integration: approve() records the decision and executes nothing; a
  mutating actuator is refused at engine construction
  (ADR_CLOUD_SCALING_OPERATIONS_ORCHESTRATOR_CONTAINMENT_SCOPING)
"""

import time
import pytest
from unittest.mock import MagicMock

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
    GateResult,
    GateActuator,
)
from symbolu.cloud_controller.action import (
    K8sActuator as K8sActuatorImport,
    GateActuator as GateActuatorImport,
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
    """Create an ActionResult for testing."""
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
# K8s Actuator — Dry Run
# ============================================================

class TestK8sActuatorDryRun:
    def test_dry_run_scale_out(self):
        """Dry run should succeed and log without K8s client."""
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.DRY_RUN))
        result = actuator.scale(
            deployment="api-gateway",
            namespace="prod",
            current_replicas=5,
            target_replicas=7,
        )
        assert result.success is True
        assert result.mode == "dry_run"
        assert result.deployment == "api-gateway"
        assert result.namespace == "prod"
        assert result.previous_replicas == 5
        assert result.target_replicas == 7
        assert result.delta == 2

    def test_dry_run_scale_in(self):
        """Dry run should handle scale-in correctly."""
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.DRY_RUN))
        result = actuator.scale(
            deployment="worker",
            namespace="staging",
            current_replicas=10,
            target_replicas=8,
        )
        assert result.success is True
        assert result.delta == -2

    def test_no_change_returns_success(self):
        """Delta=0 should return success immediately."""
        actuator = K8sActuator()
        result = actuator.scale(
            deployment="svc",
            namespace="ns",
            current_replicas=5,
            target_replicas=5,
        )
        assert result.success is True
        assert result.delta == 0

    def test_recommendation_id_recorded(self):
        """Recommendation ID should be preserved in result."""
        actuator = K8sActuator()
        result = actuator.scale(
            deployment="svc",
            namespace="ns",
            current_replicas=3,
            target_replicas=5,
            recommendation_id="rec-abc123",
        )
        assert result.recommendation_id == "rec-abc123"


# ============================================================
# K8s Actuator — History
# ============================================================

class TestK8sActuatorHistory:
    def test_history_records_results(self):
        """Each scale() call should be recorded in history."""
        actuator = K8sActuator()
        actuator.scale("svc1", "ns", 5, 7)
        actuator.scale("svc2", "ns", 3, 1)
        assert len(actuator.history) == 2
        assert actuator.history[0].deployment == "svc1"
        assert actuator.history[1].deployment == "svc2"

    def test_recent_successes_filters_by_time(self):
        """recent_successes should only return results from last 10 minutes."""
        actuator = K8sActuator()
        # Add an old result
        old_result = ExecutionResult(
            success=True, mode="dry_run", deployment="old",
            namespace="ns", previous_replicas=5, target_replicas=7,
            delta=2, timestamp=time.time() - 700,  # > 10 min ago
        )
        actuator._history.append(old_result)
        # Add a recent result
        actuator.scale("new", "ns", 5, 7)
        recent = actuator.recent_successes
        assert len(recent) == 1
        assert recent[0].deployment == "new"

    def test_history_truncation(self):
        """History should be capped at max_history."""
        actuator = K8sActuator()
        actuator._max_history = 5
        for i in range(10):
            actuator.scale(f"svc-{i}", "ns", 5, 6)
        assert len(actuator.history) == 5

    def test_reset_clears_state(self):
        """Reset should clear history."""
        actuator = K8sActuator()
        actuator.scale("svc", "ns", 5, 7)
        assert len(actuator.history) == 1
        actuator.reset()
        assert len(actuator.history) == 0


# ============================================================
# K8s Actuator — Scale Patch (injected client only)
# ============================================================

class TestK8sActuatorScalePatch:
    def test_scale_patch_success(self):
        """A successful call through the injected client returns success."""
        mock_api = MagicMock()
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH), apps_api=mock_api)

        result = actuator.scale("api-gw", "prod", 5, 7)
        assert result.success is True
        assert result.mode == "scale_patch"
        assert result.retries == 0
        mock_api.patch_namespaced_deployment_scale.assert_called_once()

    def test_scale_patch_retry_on_failure(self):
        """Should retry on transient K8s API failure."""
        config = ActuatorConfig(
            mode=ActuatorMode.SCALE_PATCH,
            max_retries=2,
            retry_delay_seconds=0.01,  # Fast for tests
        )
        mock_api = MagicMock()
        # Fail first, succeed second
        mock_api.patch_namespaced_deployment_scale.side_effect = [
            ConnectionError("timeout"),
            None,  # success
        ]
        actuator = K8sActuator(config, apps_api=mock_api)

        result = actuator.scale("api-gw", "prod", 5, 7)
        assert result.success is True
        assert result.retries == 1

    def test_scale_patch_all_retries_exhausted(self):
        """Should fail after all retries exhausted."""
        config = ActuatorConfig(
            mode=ActuatorMode.SCALE_PATCH,
            max_retries=1,
            retry_delay_seconds=0.01,
        )
        mock_api = MagicMock()
        mock_api.patch_namespaced_deployment_scale.side_effect = ConnectionError("down")
        actuator = K8sActuator(config, apps_api=mock_api)

        result = actuator.scale("api-gw", "prod", 5, 7)
        assert result.success is False
        assert "Failed after" in result.error
        assert result.retries == 1

    def test_scale_patch_without_injected_client_fails_closed(self):
        """No client is ever discovered: without one, scale_patch fails closed."""
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH))
        assert actuator.has_client is False

        result = actuator.scale("api-gw", "prod", 5, 7)
        assert result.success is False
        assert "injected" in result.error

    def test_actuator_config_refuses_credential_discovery_fields(self):
        """kubeconfig_path / context no longer exist: the actuator discovers nothing."""
        for field in ("kubeconfig_path", "context"):
            with pytest.raises(TypeError):
                ActuatorConfig(**{field: "anything"})

    def test_mutates_reflects_mode(self):
        assert K8sActuator().mutates is False
        assert K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH)).mutates is True


# ============================================================
# K8s Actuator — HPA Metric Mode
# ============================================================

class TestK8sActuatorHPAMetric:
    def test_hpa_metric_mode_succeeds(self):
        """HPA metric mode should succeed (logs action_score for HPA)."""
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.HPA_METRIC))
        result = actuator.scale("api-gw", "prod", 5, 7)
        assert result.success is True
        assert result.mode == "hpa_metric"


# ============================================================
# K8s Actuator — ExecutionResult formatting
# ============================================================

class TestExecutionResult:
    def test_format_log_success(self):
        result = ExecutionResult(
            success=True, mode="scale_patch", deployment="api-gw",
            namespace="prod", previous_replicas=5, target_replicas=7,
            delta=2, timestamp=time.time(),
        )
        log = result.format_log()
        assert "EXECUTE" in log
        assert "scale_patch" in log
        assert "5 -> 7" in log
        assert "+2" in log
        assert "OK" in log

    def test_format_log_failure(self):
        result = ExecutionResult(
            success=False, mode="scale_patch", deployment="api-gw",
            namespace="prod", previous_replicas=5, target_replicas=7,
            delta=2, timestamp=time.time(), error="K8s client not available",
        )
        log = result.format_log()
        assert "FAILED" in log
        assert "K8s client not available" in log


# ============================================================
# Gate Actuator — Dry Run
# ============================================================

class TestGateActuatorDryRun:
    def test_dry_run_allow(self):
        gate = GateActuator()
        result = gate.execute(GateAction.ALLOW, "api-gateway", "prod")
        assert result.success is True
        assert result.mode == "dry_run"
        assert result.action == "allow"

    def test_dry_run_hold(self):
        gate = GateActuator()
        result = gate.execute(GateAction.HOLD, "api-gateway", "prod")
        assert result.success is True
        assert result.action == "hold"

    def test_dry_run_sync(self):
        gate = GateActuator()
        result = gate.execute(GateAction.SYNC, "api-gateway", "prod")
        assert result.success is True
        assert result.action == "sync"

    def test_recommendation_id(self):
        gate = GateActuator()
        result = gate.execute(
            GateAction.ALLOW, "app", "ns", recommendation_id="rec-xyz",
        )
        assert result.recommendation_id == "rec-xyz"


# ============================================================
# Gate Actuator — History
# ============================================================

class TestGateActuatorHistory:
    def test_history_records(self):
        gate = GateActuator()
        gate.execute(GateAction.ALLOW, "app1", "ns")
        gate.execute(GateAction.HOLD, "app2", "ns")
        assert len(gate.history) == 2

    def test_reset(self):
        gate = GateActuator()
        gate.execute(GateAction.ALLOW, "app", "ns")
        gate.reset()
        assert len(gate.history) == 0


# ============================================================
# Gate Actuator — one mode, no ArgoCD access, no token
# ============================================================

class TestGateActuatorContainment:
    def test_dry_run_is_the_only_mode(self):
        assert set(GateMode) == {GateMode.DRY_RUN}

    def test_config_has_no_url_token_or_tls_switch(self):
        for field in ("argocd_url", "argocd_token", "argocd_insecure"):
            with pytest.raises(TypeError):
                GateConfig(**{field: "anything"})

    def test_sync_is_recorded_never_transmitted(self):
        gate = GateActuator(GateConfig(mode=GateMode.DRY_RUN))
        assert gate.mutates is False
        result = gate.execute(GateAction.SYNC, "my-app", "prod")
        assert result.success is True
        assert result.mode == "dry_run"
        assert result.action == "sync"


# ============================================================
# Gate Result formatting
# ============================================================

class TestGateResult:
    def test_format_log(self):
        result = GateResult(
            success=True, mode="argocd_sync", action="sync",
            application="my-app", namespace="prod",
            timestamp=time.time(),
        )
        log = result.format_log()
        assert "GATE" in log
        assert "argocd_sync" in log
        assert "my-app" in log
        assert "OK" in log


# ============================================================
# __init__.py Exports
# ============================================================

class TestActionExports:
    def test_k8s_actuator_importable(self):
        assert K8sActuatorImport is K8sActuator

    def test_gate_actuator_importable(self):
        assert GateActuatorImport is GateActuator


# ============================================================
# Engine Integration — approve() records, never executes
# ============================================================

class TestEngineActuatorIntegration:
    def _engine(self, **overrides):
        cfg = dict(
            service="api-gw",
            namespace="prod",
            confidence=ConfidenceConfig(
                action_threshold=0.1,
                coherence_threshold=0.1,
            ),
        )
        cfg.update(overrides)
        return RecommendEngine(RecommendConfig(**cfg))

    def test_approve_without_actuator(self):
        """Without actuator config, approve() records and executes nothing."""
        engine = self._engine()
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        assert cycle.recommendation is not None

        rec = engine.approve(cycle.recommendation.id, by="test")
        assert rec is not None
        assert rec.execution_result is None

    def test_approve_with_dry_run_actuator_executes_nothing(self):
        """A DRY_RUN actuator is accepted, and approve() still does not call it."""
        engine = self._engine(actuator=ActuatorConfig(mode=ActuatorMode.DRY_RUN))
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        assert cycle.recommendation is not None

        rec = engine.approve(cycle.recommendation.id, by="ops-team")
        assert rec is not None
        assert rec.execution_result is None
        assert engine.actuator.history == []

    def test_scale_patch_actuator_is_refused_at_engine_construction(self):
        """A mutating actuator cannot be held by the engine at all (D-1)."""
        with pytest.raises(RuntimeError):
            self._engine(actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH))

    def test_hpa_metric_actuator_is_refused_at_engine_construction(self):
        with pytest.raises(RuntimeError):
            self._engine(actuator=ActuatorConfig(mode=ActuatorMode.HPA_METRIC))

    def test_engine_reset_clears_actuator(self):
        """Engine reset should also reset actuator history."""
        engine = self._engine(actuator=ActuatorConfig(mode=ActuatorMode.DRY_RUN))
        engine.actuator.scale("api-gw", "prod", 5, 7)  # a direct dry-run proposal
        assert len(engine.actuator.history) == 1

        engine.reset()
        assert len(engine.actuator.history) == 0

    def test_engine_reset_without_actuator(self):
        """Engine reset should work fine when no actuator configured."""
        engine = RecommendEngine(RecommendConfig(service="svc"))
        engine.reset()  # Should not raise
        assert engine.actuator is None

    def test_approve_starts_cooldown_without_executing(self):
        """Cooldown starts on approval, so the same signal is not re-approved in a burst."""
        engine = self._engine(actuator=ActuatorConfig(mode=ActuatorMode.DRY_RUN))
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        assert cycle.recommendation is not None

        rec = engine.approve(cycle.recommendation.id, by="ops-team")
        assert rec is not None
        assert rec.execution_result is None
        assert engine.safety.last_action_time is not None
