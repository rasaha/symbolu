"""The curated public API matches the frozen artifact."""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys

import ugence_policy_workflow_compiler.api as api

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ARTIFACT = _ROOT / "artifacts" / "public_api.json"


def _snapshot():
    from importlib import import_module

    mod = import_module("scripts.public_api_snapshot") if False else None  # noqa
    # run the script as a module in-process
    script = _ROOT / "scripts" / "public_api_snapshot.py"
    result = subprocess.run(
        [sys.executable, str(script)], capture_output=True, text=True, cwd=str(_ROOT),
        env={"PYTHONPATH": str(_ROOT / "src")},
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_public_api_matches_frozen_artifact():
    frozen = json.loads(_ARTIFACT.read_text())
    live = _snapshot()
    assert live == frozen, "ugence_policy_workflow_compiler.api drifted from artifacts/public_api.json"


def test_all_exports_importable():
    for name in api.__all__:
        assert hasattr(api, name), name


def test_no_private_names_exported():
    for name in api.__all__:
        assert not name.startswith("_")


def test_required_names_present():
    required = {
        "PolicyPack", "PolicyPackStatus", "PolicyPackValidator", "ValidationReport",
        "ValidationDiagnostic", "CapabilityRegistry", "CapabilityDefinition",
        "WorkflowIR", "WorkflowNode", "WorkflowEdge", "GovernedWorkflowCompiler",
        "CompilationResult", "AssuranceManifest", "CoverageMatrix", "AuditSchema",
        "HumanApprovalRecord", "PolicyPackDiff", "CompiledReleasePackage",
        "compile_policy_pack", "validate_policy_pack", "diff_policy_packs",
        "verify_compiled_package", "version_info",
    }
    assert required.issubset(set(api.__all__))
