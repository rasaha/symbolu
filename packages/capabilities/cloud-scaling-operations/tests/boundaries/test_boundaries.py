"""Boundary + compatibility: dependency direction, identity, no advisory duplication."""

from __future__ import annotations

import ast
import pathlib

import pytest

import ugence_cloud_scaling_operations as OPS

PKG_DIR = pathlib.Path(OPS.__file__).parent


def test_operations_imports_advisory():
    # At least one packaged module depends on the advisory package (one-directional).
    assert any("ugence_cloud_scaling_controller" in p.read_text()
               for p in PKG_DIR.rglob("*.py"))


def test_no_advisory_source_duplicated():
    # The advisory algorithm sentinels must NOT be redefined inside operations.
    sentinels = ("class InfraControllerConfig", "class CloudScalingController",
                 "class CoherenceModel")
    for p in PKG_DIR.rglob("*.py"):
        text = p.read_text()
        for s in sentinels:
            assert not any(line.strip().startswith(s) for line in text.splitlines()), \
                f"{s} duplicated in {p.name}"


def test_advisory_does_not_import_operations():
    import ugence_cloud_scaling_controller as ADV
    adv_dir = pathlib.Path(ADV.__file__).parent
    for p in adv_dir.rglob("*.py"):
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.Import):
                assert all(a.name.split(".")[0] != "ugence_cloud_scaling_operations"
                           for a in node.names), p.name
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] != "ugence_cloud_scaling_operations", p.name


def test_canonical_and_legacy_object_identity():
    import importlib.util
    if importlib.util.find_spec("cloud_scaling_operations") is None:
        pytest.skip("legacy shim not on path (wheel-only env)")
    from cloud_scaling_operations.action.k8s_actuator import K8sActuator as L
    from ugence_cloud_scaling_operations.action.k8s_actuator import K8sActuator as C
    assert L is C
    import importlib
    if importlib.util.find_spec("cloud_controller") is not None:
        from cloud_controller.orchestrator import ProductionOrchestrator as LO
        from ugence_cloud_scaling_operations.orchestrator import ProductionOrchestrator as CO
        assert LO is CO


def test_auto_approval_cannot_drive_live_actuator():
    # Hard guard: auto_approve_threshold + a non-dry-run actuator is refused.
    from ugence_cloud_scaling_operations.orchestrator import (
        AutoApprovalRefused, ProductionOrchestrator, OrchestratorConfig)
    from ugence_cloud_scaling_operations.recommend.engine import RecommendConfig
    from ugence_cloud_scaling_operations.action.k8s_actuator import ActuatorConfig, ActuatorMode
    cfg = OrchestratorConfig(
        auto_approve_threshold="high",
        recommend=RecommendConfig(actuator=ActuatorConfig(mode=ActuatorMode.SCALE_PATCH)))
    # The orchestrator's own guard answers first; the engine's (containment D-1) stands behind it.
    with pytest.raises(AutoApprovalRefused):
        ProductionOrchestrator(cfg)


def test_auto_approval_allowed_only_with_dry_run_actuator():
    from ugence_cloud_scaling_operations.orchestrator import (
        ProductionOrchestrator, OrchestratorConfig)
    from ugence_cloud_scaling_operations.recommend.engine import RecommendConfig
    from ugence_cloud_scaling_operations.action.k8s_actuator import ActuatorConfig, ActuatorMode
    cfg = OrchestratorConfig(
        auto_approve_threshold="high",
        recommend=RecommendConfig(actuator=ActuatorConfig(mode=ActuatorMode.DRY_RUN)))
    ProductionOrchestrator(cfg)  # must not raise
