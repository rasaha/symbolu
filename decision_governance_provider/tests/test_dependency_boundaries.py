"""Phase 5F — provider-framework dependency rules (automatically enforced).

* the kernel never imports the provider framework;
* the provider framework never imports a consuming layer (domains / applications /
  ai_hiring);
* the provider framework touches the kernel only through its public API
  (``decision_governance.api``) — never an internal kernel module;
* the framework imports standalone, with no import cycles.
"""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
KERNEL = REPO / "decision_governance"
FRAMEWORK = REPO / "decision_governance_provider"


def _imports(root: pathlib.Path):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts or "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield path, node.lineno, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.lineno, node.module


def test_kernel_never_imports_the_provider_framework():
    bad = [f"{p.name}:{ln} -> {m}" for p, ln, m in _imports(KERNEL)
           if m.split(".")[0] == "decision_governance_provider"]
    assert not bad, bad


def test_framework_never_imports_a_consuming_layer():
    forbidden = {"ai_hiring", "domains", "applications"}
    bad = [f"{p.name}:{ln} -> {m}" for p, ln, m in _imports(FRAMEWORK)
           if m.split(".")[0] in forbidden]
    assert not bad, bad


def test_framework_uses_only_the_public_kernel_api():
    bad = []
    for p, ln, m in _imports(FRAMEWORK):
        if m == "decision_governance" or (
                m.startswith("decision_governance.") and not m.startswith("decision_governance.api")):
            bad.append(f"{p.name}:{ln} -> {m}")
    assert not bad, "framework must consume the kernel via decision_governance.api:\n" + "\n".join(bad)


def test_framework_imports_standalone_without_cycles():
    code = (
        "import decision_governance_provider, decision_governance_provider.adapters, "
        "decision_governance_provider.conformance, decision_governance_provider.mock, "
        "decision_governance_provider.resolution; print('ok')"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
