"""Packaging metadata + public API + manifest agreement."""

from __future__ import annotations

import json
import pathlib

import ugence_cloud_scaling_operations as OPS
from ugence_cloud_scaling_operations.version import __version__

PKG_ROOT = pathlib.Path(OPS.__file__).parents[2]  # .../cloud-scaling-operations


def test_version_matches_manifest():
    manifest = json.loads((PKG_ROOT / "module_manifest.json").read_text())
    assert __version__ == "0.1.0"
    assert manifest["version"] == __version__


def test_manifest_declares_controlled_execution_honestly():
    m = json.loads((PKG_ROOT / "module_manifest.json").read_text())
    assert m["authority_class"] == "CONTROLLED_EXECUTION"
    assert m["execution_capability"] == "INFRASTRUCTURE_MUTATION"
    assert m["advisory_only"] is False
    assert m["contains_concrete_executor"] is True
    assert m["requires_external_authorization"] is True
    assert m["live_execution_enabled_by_default"] is False


def test_py_typed_shipped():
    assert (pathlib.Path(OPS.__file__).parent / "py.typed").exists()


def test_public_api_exports():
    expected = {
        "ExecutionAuthorization", "ExecutionRequest", "ExecutionResult", "ExecutionReceipt",
        "ExecutionDenied", "ExecutionIntegrityError", "ExecutionMode",
        "ControlledScalingExecutor", "KubernetesScalingExecutor", "GateExecutor",
        "RollbackCoordinator", "ReadinessEvaluator", "OutcomeRecorder",
        "OperationsConfig", "TargetPolicy", "AuthorityVerifier", "IdempotencyStore",
        "AuditSink", "__version__",
    }
    assert expected.issubset(set(OPS.__all__))
    for name in expected:
        assert hasattr(OPS, name)


def test_advisory_dependency_range_declared():
    text = (PKG_ROOT / "pyproject.toml").read_text()
    assert "ugence-cloud-scaling-controller>=0.1.1,<0.2" in text
