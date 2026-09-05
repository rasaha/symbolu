"""Orchestrator containment (ADR_CLOUD_SCALING_OPERATIONS_ORCHESTRATOR_CONTAINMENT_SCOPING).

Before the ruling, ``ProductionOrchestrator.approve`` ran ``RecommendEngine.approve`` →
``K8sActuator.scale`` → ``patch_namespaced_deployment_scale`` with no
``ExecutionAuthorization``, and the actuator discovered kubeconfig or in-cluster
credentials itself. These tests measure each ruling: D-1 (the engine and the rollback
monitor refuse mutation at construction), D-2 (no credential discovery, no bearer
token, no non-dry-run gate mode), D-3 (approval records and executes nothing). Every
``pytest.raises`` here is a guard the gate-removal sweep scores.
"""

from __future__ import annotations

import argparse
import ast
import pathlib
from unittest.mock import MagicMock

import pytest

from ugence_cloud_scaling_controller.controller import Controller
from ugence_cloud_scaling_controller.recommend.confidence import ConfidenceConfig
from ugence_cloud_scaling_operations.action import gate_actuator as gate_module
from ugence_cloud_scaling_operations.action import k8s_actuator as actuator_module
from ugence_cloud_scaling_operations.action.gate_actuator import (
    GateAction, GateActuator, GateConfig, GateMode)
from ugence_cloud_scaling_operations.action.k8s_actuator import (
    ActuatorConfig, ActuatorMode, K8sActuator)
from ugence_cloud_scaling_operations.action.outcome import OutcomeConfig
from ugence_cloud_scaling_operations.action.policy import DeploymentPolicy, PolicyConfig
from ugence_cloud_scaling_operations.action.rollback import (
    MutatingRollbackRefused, RollbackConfig, RollbackMonitor)
from ugence_cloud_scaling_operations.orchestrator import (
    AutoApprovalRefused, OrchestratorConfig, ProductionOrchestrator)
from ugence_cloud_scaling_operations.recommend.engine import (
    MutatingActuatorRefused, RecommendConfig, RecommendEngine)


def _action(delta: int = 2):
    result = Controller().step(
        metrics={"cpu": 0.5, "memory": 0.5, "latency_p99": 0.5, "error_rate": 0.5},
        current_replicas=5)
    result.replica_delta = delta
    result.action_score = 0.8
    result.pressure = 0.6
    result.recommendation = "scale_out"
    if result.coherence is not None:
        result.coherence.coherence = 0.9
    return result


def _engine(**overrides) -> RecommendEngine:
    cfg = dict(service="api-gw", namespace="prod",
               confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1))
    cfg.update(overrides)
    return RecommendEngine(RecommendConfig(**cfg))


def _imports(module) -> set:
    tree = ast.parse(pathlib.Path(module.__file__).read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])
    return found


# --------------------------------------------------------------------------- D-1

@pytest.mark.parametrize("mode", [ActuatorMode.SCALE_PATCH, ActuatorMode.HPA_METRIC])
def test_the_engine_refuses_a_non_dry_run_actuator_at_construction(mode):
    with pytest.raises(MutatingActuatorRefused) as exc:
        RecommendEngine(RecommendConfig(actuator=ActuatorConfig(mode=mode)))
    assert mode.value in str(exc.value)


def test_the_engine_accepts_a_dry_run_actuator_and_no_actuator():
    assert RecommendEngine(RecommendConfig(actuator=ActuatorConfig())).actuator is not None
    assert RecommendEngine(RecommendConfig()).actuator is None


def test_a_manual_approval_loop_cannot_hold_a_mutating_actuator_either():
    # The pre-ruling gap: no auto-approve, a SCALE_PATCH actuator, a human approve().
    cfg = OrchestratorConfig(recommend=RecommendConfig(
        actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH)))
    with pytest.raises(MutatingActuatorRefused):
        ProductionOrchestrator(cfg)


def test_the_auto_approve_guard_still_answers_first_with_its_own_refusal():
    # The orchestrator's pre-ruling guard stays as a second line and speaks before the engine.
    cfg = OrchestratorConfig(auto_approve_threshold="high", recommend=RecommendConfig(
        actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH)))
    with pytest.raises(AutoApprovalRefused):
        ProductionOrchestrator(cfg)


@pytest.mark.parametrize("fn", [MagicMock(), lambda **kwargs: None,
                                K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH)).scale])
def test_the_rollback_monitor_refuses_a_rollback_function_not_declared_non_mutating(fn):
    with pytest.raises(MutatingRollbackRefused):
        RollbackMonitor(RollbackConfig(execute_rollback=True), rollback_fn=fn)


def test_the_rollback_monitor_accepts_a_dry_run_actuator_scale_and_none():
    RollbackMonitor(RollbackConfig(), rollback_fn=K8sActuator().scale)
    RollbackMonitor(RollbackConfig(), rollback_fn=None)


def test_an_engine_with_a_dry_run_actuator_wires_a_rollback_monitor():
    engine = _engine(actuator=ActuatorConfig(), rollback=RollbackConfig())
    assert engine.rollback is not None and engine.actuator.mutates is False


# --------------------------------------------------------------------------- D-2

def test_the_actuator_config_has_no_credential_discovery_fields():
    for field in ("kubeconfig_path", "context"):
        with pytest.raises(TypeError):
            ActuatorConfig(**{field: "anything"})


def test_the_actuator_module_imports_no_kubernetes_sdk_and_the_gate_module_no_http():
    assert "kubernetes" not in _imports(actuator_module)
    assert not ({"urllib", "http", "requests", "ssl", "socket"} & _imports(gate_module))
    for name in ("load_kube_config", "load_incluster_config", "kube_config"):
        assert name not in pathlib.Path(actuator_module.__file__).read_text(encoding="utf-8")


def test_a_scale_patch_actuator_without_an_injected_client_fails_closed():
    actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH))
    assert actuator.has_client is False
    result = actuator.scale("api-gw", "prod", 5, 7)
    assert result.success is False and "injected" in result.error


def test_a_scale_patch_actuator_reaches_only_the_client_it_was_handed():
    client = MagicMock()
    actuator = K8sActuator(ActuatorConfig(mode=ActuatorMode.SCALE_PATCH), apps_api=client)
    assert actuator.mutates is True
    result = actuator.scale("api-gw", "prod", 5, 7)
    assert result.success is True
    client.patch_namespaced_deployment_scale.assert_called_once()
    actuator.reset()
    assert actuator.has_client is True and actuator.history == []


def test_the_gate_actuator_has_one_mode_no_token_and_transmits_nothing():
    assert set(GateMode) == {GateMode.DRY_RUN}
    for field in ("argocd_token", "argocd_url", "argocd_insecure"):
        with pytest.raises(TypeError):
            GateConfig(**{field: "anything"})
    gate = GateActuator()
    assert gate.mutates is False
    result = gate.execute(GateAction.SYNC, "app", "prod", recommendation_id="rec-1")
    assert result.success is True and result.mode == "dry_run" and result.action == "sync"
    assert gate.history[0].recommendation_id == "rec-1"


# --------------------------------------------------------------------------- D-3

def test_approval_records_the_decision_and_executes_nothing_with_every_component_wired():
    engine = _engine(
        actuator=ActuatorConfig(),
        policy=PolicyConfig(default_policy=DeploymentPolicy(max_replicas=20)),
        rollback=RollbackConfig(watch_window_seconds=180, grace_period_seconds=5),
        outcome=OutcomeConfig(evaluation_window_seconds=300),
    )
    cycle = engine.evaluate(_action(delta=2), current_replicas=5)
    assert cycle.recommendation is not None

    rec = engine.approve(cycle.recommendation.id, by="ops", metrics_snapshot={"latency_p99": 0.3})
    assert rec is not None
    assert rec.execution_result is None
    assert engine.actuator.history == []
    assert engine.rollback.active_count == 0
    assert engine.outcome.pending_count == 0
    assert engine.safety.last_action_time is not None
    assert engine.pending_count == 0


def test_approval_of_a_policy_violating_target_still_records_and_still_executes_nothing():
    engine = _engine(policy=PolicyConfig(default_policy=DeploymentPolicy(max_replicas=6)))
    cycle = engine.evaluate(_action(delta=2), current_replicas=5)
    rec = engine.approve(cycle.recommendation.id, by="ops")
    assert rec is not None and rec.execution_result is None


def test_the_orchestrator_approve_returns_the_recommendation_with_no_execution_result():
    orch = ProductionOrchestrator(OrchestratorConfig(recommend=RecommendConfig(
        service="api-gw", namespace="prod",
        confidence=ConfidenceConfig(action_threshold=0.1, coherence_threshold=0.1),
        actuator=ActuatorConfig())))
    cycle = orch.recommend_engine.evaluate(_action(delta=2), current_replicas=5)
    rec = orch.approve(cycle.recommendation.id, by="ops")
    assert rec is not None and rec.execution_result is None
    assert orch.recommend_engine.actuator.history == []


# ------------------------------------------------------------------ entrypoint

def _args() -> argparse.Namespace:
    return argparse.Namespace(prometheus_url=None, namespace=None, deployment=None, metrics_port=0)


@pytest.mark.parametrize("mode", ["scale_patch", "hpa_metric", "anything-else"])
def test_the_service_entrypoint_refuses_a_mutating_actuator_mode(mode):
    from ugence_cloud_scaling_operations.main import _build_orchestrator_config
    with pytest.raises(ValueError):
        _build_orchestrator_config({"actuator": {"mode": mode}}, _args())


def test_the_service_entrypoint_builds_only_a_dry_run_actuator():
    from ugence_cloud_scaling_operations.main import _build_orchestrator_config
    for raw in ({}, {"actuator": {"mode": "dry_run"}}):
        cfg = _build_orchestrator_config(raw, _args())
        assert cfg.recommend.actuator.mode is ActuatorMode.DRY_RUN
