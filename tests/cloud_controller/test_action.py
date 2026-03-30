"""Unit tests for Stage 5 — Action Layer (K8s Actuator + Gate Actuator).

Tests cover:
- K8sActuator: dry_run, scale_patch (mocked), history, retry logic
- GateActuator: dry_run, ArgoCD sync (mocked), admission policy
- Engine integration: approve() triggers actuator execution
"""

import time
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

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
        """Reset should clear history and client state."""
        actuator = K8sActuator()
        actuator.scale("svc", "ns", 5, 7)
        assert len(actuator.history) == 1
        actuator.reset()
        assert len(actuator.history) == 0
        assert actuator._initialized is False


# ============================================================
# K8s Actuator — Scale Patch (mocked K8s client)
# ============================================================

class TestK8sActuatorScalePatch:
    def test_scale_patch_success(self):
        """Successful K8s API call should return success."""
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH))
        mock_api = MagicMock()
        actuator._apps_api = mock_api
        actuator._initialized = True

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
        actuator = K8sActuator(config)
        mock_api = MagicMock()
        # Fail first, succeed second
        mock_api.patch_namespaced_deployment_scale.side_effect = [
            ConnectionError("timeout"),
            None,  # success
        ]
        actuator._apps_api = mock_api
        actuator._initialized = True

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
        actuator = K8sActuator(config)
        mock_api = MagicMock()
        mock_api.patch_namespaced_deployment_scale.side_effect = ConnectionError("down")
        actuator._apps_api = mock_api
        actuator._initialized = True

        result = actuator.scale("api-gw", "prod", 5, 7)
        assert result.success is False
        assert "Failed after" in result.error
        assert result.retries == 1

    def test_scale_patch_no_client_fails(self):
        """Should fail gracefully when K8s client unavailable."""
        actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH))
        actuator._initialized = True
        actuator._apps_api = None

        result = actuator.scale("api-gw", "prod", 5, 7)
        assert result.success is False
        assert "not available" in result.error


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
# Gate Actuator — ArgoCD Sync
# ============================================================

class TestGateActuatorArgoCD:
    def test_argocd_no_url_fails(self):
        """ArgoCD mode without URL should fail."""
        gate = GateActuator(GateConfig(mode=GateMode.ARGOCD_SYNC))
        result = gate.execute(GateAction.SYNC, "app", "ns")
        assert result.success is False
        assert "URL not configured" in result.error

    def test_argocd_hold_succeeds(self):
        """HOLD action in ArgoCD mode should succeed (no API call)."""
        gate = GateActuator(GateConfig(
            mode=GateMode.ARGOCD_SYNC,
            argocd_url="https://argocd.test:8080",
        ))
        result = gate.execute(GateAction.HOLD, "app", "ns")
        assert result.success is True
        assert result.action == "hold"

    def test_argocd_allow_succeeds(self):
        """ALLOW action in ArgoCD mode should succeed (no API call)."""
        gate = GateActuator(GateConfig(
            mode=GateMode.ARGOCD_SYNC,
            argocd_url="https://argocd.test:8080",
        ))
        result = gate.execute(GateAction.ALLOW, "app", "ns")
        assert result.success is True
        assert result.action == "allow"

    @patch("urllib.request.urlopen")
    def test_argocd_sync_success(self, mock_urlopen):
        """Successful ArgoCD sync API call."""
        mock_urlopen.return_value = MagicMock()
        gate = GateActuator(GateConfig(
            mode=GateMode.ARGOCD_SYNC,
            argocd_url="https://argocd.test:8080",
            argocd_token="test-token",
        ))
        result = gate.execute(GateAction.SYNC, "my-app", "prod")
        assert result.success is True
        assert result.action == "sync"
        mock_urlopen.assert_called_once()

    @patch("urllib.request.urlopen")
    def test_argocd_sync_retry(self, mock_urlopen):
        """Should retry on ArgoCD API failure."""
        mock_urlopen.side_effect = [
            ConnectionError("timeout"),
            MagicMock(),  # success on retry
        ]
        gate = GateActuator(GateConfig(
            mode=GateMode.ARGOCD_SYNC,
            argocd_url="https://argocd.test:8080",
            argocd_token="test-token",
            retry_delay_seconds=0.01,
        ))
        result = gate.execute(GateAction.SYNC, "my-app", "prod")
        assert result.success is True
        assert result.retries == 1


# ============================================================
# Gate Actuator — Admission Webhook
# ============================================================

class TestGateActuatorAdmission:
    def test_admission_policy_allow(self):
        gate = GateActuator(GateConfig(mode=GateMode.ADMISSION_WEBHOOK))
        result = gate.execute(GateAction.ALLOW, "app", "ns")
        assert result.success is True
        assert result.mode == "admission_webhook"
        assert result.action == "allow"

    def test_admission_policy_hold(self):
        gate = GateActuator(GateConfig(mode=GateMode.ADMISSION_WEBHOOK))
        result = gate.execute(GateAction.HOLD, "app", "ns")
        assert result.success is True
        assert result.action == "hold"


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
# Engine Integration — approve() triggers actuator
# ============================================================

class TestEngineActuatorIntegration:
    def test_approve_without_actuator(self):
        """Without actuator config, approve() should not execute."""
        engine = RecommendEngine(RecommendConfig(
            service="api-gw",
            namespace="prod",
            confidence=ConfidenceConfig(
                action_threshold=0.1,
                coherence_threshold=0.1,
            ),
        ))
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        assert cycle.recommendation is not None

        rec = engine.approve(cycle.recommendation.id, by="test")
        assert rec is not None
        assert rec.execution_result is None

    def test_approve_with_dry_run_actuator(self):
        """With dry_run actuator, approve() should execute and record result."""
        engine = RecommendEngine(RecommendConfig(
            service="api-gw",
            namespace="prod",
            confidence=ConfidenceConfig(
                action_threshold=0.1,
                coherence_threshold=0.1,
            ),
            actuator=ActuatorConfig(mode=ActuatorMode.DRY_RUN),
        ))
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        assert cycle.recommendation is not None

        rec = engine.approve(cycle.recommendation.id, by="ops-team")
        assert rec is not None
        assert rec.execution_result is not None
        assert rec.execution_result.success is True
        assert rec.execution_result.mode == "dry_run"
        assert rec.execution_result.deployment == "api-gw"
        assert rec.execution_result.target_replicas == 7  # 5 + 2

    def test_approve_with_scale_patch_actuator(self):
        """With scale_patch actuator (mocked), approve triggers K8s API call."""
        engine = RecommendEngine(RecommendConfig(
            service="api-gw",
            namespace="prod",
            confidence=ConfidenceConfig(
                action_threshold=0.1,
                coherence_threshold=0.1,
            ),
            actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH),
        ))
        # Mock the K8s client
        mock_api = MagicMock()
        engine.actuator._apps_api = mock_api
        engine.actuator._initialized = True

        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        assert cycle.recommendation is not None

        rec = engine.approve(cycle.recommendation.id, by="ops-team")
        assert rec is not None
        assert rec.execution_result is not None
        assert rec.execution_result.success is True
        assert rec.execution_result.mode == "scale_patch"
        mock_api.patch_namespaced_deployment_scale.assert_called_once()

    def test_engine_reset_clears_actuator(self):
        """Engine reset should also reset actuator history and client state."""
        engine = RecommendEngine(RecommendConfig(
            service="api-gw",
            namespace="prod",
            confidence=ConfidenceConfig(
                action_threshold=0.1,
                coherence_threshold=0.1,
            ),
            actuator=ActuatorConfig(mode=ActuatorMode.DRY_RUN),
        ))
        # Execute a scaling action
        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        engine.approve(cycle.recommendation.id, by="test")
        assert len(engine.actuator.history) == 1

        # Reset should clear actuator history
        engine.reset()
        assert len(engine.actuator.history) == 0
        assert engine.actuator._initialized is False

    def test_engine_reset_without_actuator(self):
        """Engine reset should work fine when no actuator configured."""
        engine = RecommendEngine(RecommendConfig(service="svc"))
        engine.reset()  # Should not raise
        assert engine.actuator is None

    def test_approve_cooldown_regardless_of_execution(self):
        """Cooldown should start even if actuator execution fails."""
        engine = RecommendEngine(RecommendConfig(
            service="api-gw",
            namespace="prod",
            confidence=ConfidenceConfig(
                action_threshold=0.1,
                coherence_threshold=0.1,
            ),
            actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH),
        ))
        # Force actuator to fail
        engine.actuator._initialized = True
        engine.actuator._apps_api = None

        action = _make_action(delta=2, score=0.8, coherence=0.9)
        cycle = engine.evaluate(action, current_replicas=5)
        assert cycle.recommendation is not None

        rec = engine.approve(cycle.recommendation.id, by="ops-team")
        assert rec is not None
        assert rec.execution_result is not None
        assert rec.execution_result.success is False

        # Cooldown should still be active
        assert engine.safety.last_action_time is not None
