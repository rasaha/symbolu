"""Tests for the Production Orchestrator — full L0→L7 lifecycle."""

import time
import pytest
from unittest.mock import MagicMock, patch

from symbolu.cloud_controller.controller import Controller, ActionResult
from symbolu.cloud_controller.config import InfraControllerConfig
from symbolu.cloud_controller.orchestrator import (
    OrchestratorConfig,
    OrchestrationCycleResult,
    ProductionOrchestrator,
)
from symbolu.cloud_controller.signals.pipeline import PipelineConfig, CycleResult
from symbolu.cloud_controller.signals.normalizer import NormalizationResult
from symbolu.cloud_controller.recommend.engine import RecommendConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pipeline_result(controller: Controller, replicas: int = 5) -> CycleResult:
    """Build a fake CycleResult for testing orchestrator without Prometheus."""
    metrics = {"cpu": 0.7, "memory": 0.6, "latency_p99": 0.5, "error_rate": 0.01}
    action = controller.step(metrics=metrics, current_replicas=replicas)
    return CycleResult(
        timestamp=time.time(),
        raw_metrics={"cpu": 0.7, "memory": 0.6, "latency_p99": 0.5, "error_rate": 0.01},
        normalized_metrics=metrics,
        normalization_details={
            k: NormalizationResult(name=k, raw_value=v, normalized=v, method="ratio")
            for k, v in metrics.items()
        },
        k8s_state={"current_replicas": replicas, "desired_replicas": replicas},
        action=action,
        phase="normal",
        current_replicas=replicas,
        deploy_active=False,
        pod_restarts=0,
    )


# ---------------------------------------------------------------------------
# Basic construction
# ---------------------------------------------------------------------------

class TestOrchestratorConstruction:
    def test_default_construction(self):
        orch = ProductionOrchestrator()
        assert orch.cycle_count == 0
        assert orch.failed_cycles == 0
        assert orch.controller is not None
        assert orch.recommend_engine is not None
        assert orch.explainer is not None
        assert orch.exporter is not None

    def test_custom_config(self):
        config = OrchestratorConfig(
            auto_approve_threshold="high",
            status_interval_cycles=50,
        )
        orch = ProductionOrchestrator(config=config)
        assert orch.config.auto_approve_threshold == "high"
        assert orch.config.status_interval_cycles == 50

    def test_custom_controller(self):
        ctrl = Controller(InfraControllerConfig(G_base=2.0))
        orch = ProductionOrchestrator(controller=ctrl)
        assert orch.controller is ctrl
        assert orch.controller.config.G_base == 2.0


# ---------------------------------------------------------------------------
# Step with mocked pipeline
# ---------------------------------------------------------------------------

class TestOrchestratorStep:
    def test_step_with_mocked_pipeline(self):
        orch = ProductionOrchestrator()
        controller = orch.controller

        # Mock pipeline.poll_once to return a valid CycleResult
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        result = orch.step()
        assert isinstance(result, OrchestrationCycleResult)
        assert result.success
        assert result.pipeline is cycle_result
        assert result.cycle_number == 1
        assert result.cycle_duration > 0

    def test_step_increments_cycle_count(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        orch.step()
        orch.step()
        orch.step()
        assert orch.cycle_count == 3

    def test_step_pipeline_failure(self):
        orch = ProductionOrchestrator()
        orch.pipeline.poll_once = MagicMock(return_value=None)

        result = orch.step()
        assert not result.success
        assert result.pipeline is None
        assert orch.failed_cycles == 1

    def test_step_has_explanation(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        result = orch.step()
        assert result.explanation is not None
        assert result.explanation.summary != ""
        assert result.explanation.action_score == cycle_result.action.action_score

    def test_step_has_decision_log(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        result = orch.step()
        assert result.decision_log is not None

    def test_step_has_recommend_result(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        result = orch.step()
        assert result.recommend is not None

    def test_step_exports_metrics(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        orch.step()
        text = orch.get_metrics()
        assert "ncc_action_score" in text
        assert "ncc_cycles_total 1.0" in text


# ---------------------------------------------------------------------------
# Auto-approve
# ---------------------------------------------------------------------------

class TestAutoApprove:
    def test_no_auto_approve_by_default(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        result = orch.step()
        assert not result.auto_approved

    def test_auto_approve_threshold_set(self):
        config = OrchestratorConfig(auto_approve_threshold="low")
        orch = ProductionOrchestrator(config=config)
        assert orch.config.auto_approve_threshold == "low"


# ---------------------------------------------------------------------------
# Approve / Dismiss
# ---------------------------------------------------------------------------

class TestApproveAndDismiss:
    def test_approve_nonexistent_returns_none(self):
        orch = ProductionOrchestrator()
        result = orch.approve("nonexistent-id", by="test")
        assert result is None

    def test_dismiss_nonexistent_returns_none(self):
        orch = ProductionOrchestrator()
        result = orch.dismiss("nonexistent-id", by="test")
        assert result is None

    def test_pending_recommendations_empty_initially(self):
        orch = ProductionOrchestrator()
        assert orch.pending_recommendations == []


# ---------------------------------------------------------------------------
# Run loop
# ---------------------------------------------------------------------------

class TestRunLoop:
    def test_run_with_max_cycles(self):
        orch = ProductionOrchestrator(OrchestratorConfig(bootstrap_on_start=False))
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        results = []
        orch.run(callback=results.append, max_cycles=3)
        assert len(results) == 3
        assert orch.cycle_count == 3

    def test_run_async_and_stop(self):
        orch = ProductionOrchestrator(OrchestratorConfig(bootstrap_on_start=False))
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        thread = orch.run_async(max_cycles=5)
        thread.join(timeout=10)
        assert orch.cycle_count >= 1

    def test_run_async_raises_if_already_running(self):
        orch = ProductionOrchestrator(OrchestratorConfig(bootstrap_on_start=False))
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        thread = orch.run_async(max_cycles=100)
        time.sleep(0.05)
        # Should raise if we try to start again while running
        if orch._running:
            with pytest.raises(RuntimeError):
                orch.run_async()
        orch.stop()
        thread.join(timeout=5)


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_state(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        orch.step()
        orch.step()
        assert orch.cycle_count == 2

        orch.reset()
        assert orch.cycle_count == 0
        assert orch.failed_cycles == 0


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class TestContextManager:
    def test_context_manager(self):
        with ProductionOrchestrator() as orch:
            assert orch is not None
        # Should not raise after exit


# ---------------------------------------------------------------------------
# Get metrics
# ---------------------------------------------------------------------------

class TestGetMetrics:
    def test_get_metrics_before_any_cycle(self):
        orch = ProductionOrchestrator()
        text = orch.get_metrics()
        # Should still produce valid exposition with zero values
        assert "ncc_action_score" in text
        assert "ncc_cycles_total 0.0" in text

    def test_get_metrics_after_cycles(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        orch.step()
        orch.step()
        text = orch.get_metrics()
        assert "ncc_cycles_total 2.0" in text


# ---------------------------------------------------------------------------
# Feedback integration
# ---------------------------------------------------------------------------

class TestFeedbackIntegration:
    def test_feedback_result_none_when_not_configured(self):
        """Without feedback config, feedback_result should be None."""
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        result = orch.step()
        assert result.feedback_result is None

    def test_rollback_verdicts_empty_when_not_configured(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        result = orch.step()
        assert result.rollback_verdicts == []

    def test_outcome_verdicts_empty_when_not_configured(self):
        orch = ProductionOrchestrator()
        controller = orch.controller
        cycle_result = _make_pipeline_result(controller)
        orch.pipeline.poll_once = MagicMock(return_value=cycle_result)

        result = orch.step()
        assert result.outcome_verdicts == []
