"""Advisory-boundary enforcement: the packaged distribution contains no code capable
of applying scaling advice (no executor/actuator/approver/orchestrator/mutation),
and the advisory package never depends on the operations namespace.

These tests scan the PACKAGED source tree (``src/ugence_cloud_scaling_controller``),
which is exactly what the wheel ships.
"""

from __future__ import annotations

import ast
import pathlib
import re

import pytest

import ugence_cloud_scaling_controller

PKG_DIR = pathlib.Path(ugence_cloud_scaling_controller.__file__).parent
SRC_FILES = sorted(PKG_DIR.rglob("*.py"))

FORBIDDEN_MODULE_BASENAMES = {
    "k8s_actuator", "gate_actuator", "orchestrator", "main",
    "engine", "approval", "webhook", "metrics_server", "exporter",
    "otel_exporter", "runner", "live_efficiency",
}
FORBIDDEN_DIRS = {"action"}
FORBIDDEN_SYMBOLS = [
    "K8sActuator", "GateActuator", "ProductionOrchestrator", "ActuatorMode",
    "SCALE_PATCH", "ARGOCD_SYNC", "patch_namespaced_deployment_scale",
    "auto_approve_threshold", "trigger_sync", "argocd_token", "ExecutionResult",
    "RecommendEngine",
]
MUTATION_PATTERNS = [
    "patch_namespaced_deployment", "replace_namespaced", "create_namespaced",
    "delete_namespaced", "argocd", "ArgoCD",
]


def _all_text():
    return {p: p.read_text() for p in SRC_FILES}


def test_no_execution_modules_packaged():
    offenders = []
    for p in SRC_FILES:
        rel = p.relative_to(PKG_DIR)
        if set(rel.parts) & FORBIDDEN_DIRS:
            offenders.append(str(rel))
        if p.stem in FORBIDDEN_MODULE_BASENAMES:
            offenders.append(str(rel))
    assert not offenders, f"execution/operations modules present in package: {offenders}"


def test_no_forbidden_symbols_in_packaged_source():
    hits = {}
    for p, text in _all_text().items():
        for sym in FORBIDDEN_SYMBOLS:
            if re.search(r"\b" + re.escape(sym) + r"\b", text):
                hits.setdefault(sym, []).append(p.name)
    assert not hits, f"forbidden execution symbols present: {hits}"


def test_no_kubernetes_or_argocd_mutation_calls():
    hits = {}
    for p, text in _all_text().items():
        for pat in MUTATION_PATTERNS:
            if pat in text:
                hits.setdefault(pat, []).append(p.name)
    assert not hits, f"mutation/argocd patterns present: {hits}"


def test_no_kubernetes_sdk_import():
    # The read-only shadow adapter reads via the Prometheus client, not the K8s SDK.
    hits = []
    for p, text in _all_text().items():
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import) and any(a.name.split(".")[0] == "kubernetes" for a in node.names):
                hits.append(p.name)
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "kubernetes":
                hits.append(p.name)
    assert not hits, f"kubernetes SDK imported by packaged code: {hits}"


def test_no_concrete_executor():
    # ScalingExecutor is an inert Protocol; there must be no concrete apply() impl.
    for p, text in _all_text().items():
        if "def apply(self, recommendation" in text:
            assert "Protocol" in text and "..." in text, f"concrete executor in {p.name}"


def test_advisory_package_does_not_import_operations():
    # AST-based: docstring mentions are fine; actual imports are not.
    offenders = []
    for p, text in _all_text().items():
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import) and any(
                a.name.split(".")[0] == "cloud_scaling_operations" for a in node.names):
                offenders.append(p.name)
            if isinstance(node, ast.ImportFrom) and node.module and \
                    node.module.split(".")[0] == "cloud_scaling_operations":
                offenders.append(p.name)
    assert not offenders, f"advisory modules import operations namespace: {offenders}"


def test_facade_always_advisory_only():
    from ugence_cloud_scaling_controller import CloudScalingController, ScalingObservation
    ctrl = CloudScalingController()
    for cr in (1, 5, 50):
        rec = ctrl.recommend(ScalingObservation(
            metrics={"cpu": 0.99, "memory": 0.99, "latency_p99": 0.99,
                     "error_rate": 0.99, "queue_depth": 0.99},
            current_replicas=cr, phase="peak"))
        assert rec.advisory_only is True
        assert rec.actuation_performed is False


def test_cli_has_no_actuation_command():
    from ugence_cloud_scaling_controller import cli
    parser = cli.build_parser()
    # Enumerate subcommands; none may be an apply/actuate/execute/approve command.
    sub = [a for a in parser._subparsers._group_actions if hasattr(a, "choices")]
    names = set()
    for a in sub:
        names |= set(a.choices)
    assert names <= {"evaluate", "demo", "version"}, f"unexpected CLI commands: {names}"
    for banned in ("apply", "actuate", "execute", "approve", "scale", "rollback"):
        assert banned not in names


def test_scaling_executor_is_inert_protocol():
    from ugence_cloud_scaling_controller import ScalingExecutor
    import typing
    # It is a runtime-checkable Protocol; instantiating it is not allowed.
    with pytest.raises(TypeError):
        ScalingExecutor()  # type: ignore[abstract]


def test_operations_namespace_absent_or_one_directional(monkeypatch):
    # If the canonical operations package is importable, it MUST depend on the advisory
    # package (one-directional); the advisory package never imports it.
    import importlib.util
    spec = importlib.util.find_spec("ugence_cloud_scaling_operations")
    if spec is None:
        pytest.skip("operations package not on path (wheel-only environment)")
    ops_dir = pathlib.Path(spec.origin).parent
    imports_advisory = any(
        "ugence_cloud_scaling_controller" in p.read_text()
        for p in ops_dir.rglob("*.py")
    )
    assert imports_advisory, "operations namespace should import the advisory package"
