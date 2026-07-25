"""Phase 5G — ActionGate dependency rules (enforced)."""

from __future__ import annotations

import ast
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
KERNEL = REPO / "decision_governance"
FRAMEWORK = REPO / "governance_providers"
ACTIONGATE = REPO / "actiongate_provider"


def _imports(root: pathlib.Path, *, only_file: pathlib.Path | None = None):
    files = [only_file] if only_file else [
        p for p in root.rglob("*.py")
        if "__pycache__" not in p.parts and "tests" not in p.parts]
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield path, node.lineno, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.lineno, node.module


def test_kernel_never_imports_actiongate():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(KERNEL)
           if m.split(".")[0] == "actiongate_provider"]
    assert not bad, bad


def test_framework_never_imports_actiongate():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports(FRAMEWORK)
           if m.split(".")[0] == "actiongate_provider"]
    assert not bad, bad


def test_actiongate_imports_only_public_apis():
    bad = []
    for p, ln, m in _imports(ACTIONGATE):
        root = m.split(".")[0]
        if root == "decision_governance" and not m.startswith("decision_governance.api") \
                and not m.startswith("decision_governance.errors"):
            bad.append(f"{p.name}:{ln}->{m}")
        if root == "governance_providers" and not (
                m.startswith("governance_providers.api")
                or m.startswith("governance_providers.conformance")):
            bad.append(f"{p.name}:{ln}->{m}")
    assert not bad, "ActionGate must consume only public APIs:\n" + "\n".join(bad)


def test_actiongate_core_imports_neither_dgm_nor_framework():
    """The vendor core (core.py) is pure."""
    core = ACTIONGATE / "core.py"
    bad = [f"{ln}->{m}" for _p, ln, m in _imports(ACTIONGATE, only_file=core)
           if m.split(".")[0] in ("decision_governance", "governance_providers")]
    assert not bad, bad
    # the client seam is core-only too
    client = ACTIONGATE / "client" / "__init__.py"
    bad_client = [f"{ln}->{m}" for _p, ln, m in _imports(ACTIONGATE, only_file=client)
                  if m.split(".")[0] in ("decision_governance", "governance_providers")]
    assert not bad_client, bad_client


def test_actiongate_imports_standalone_without_cycles():
    code = ("import actiongate_provider.api, actiongate_provider.conformance, "
            "actiongate_provider.configuration; print('ok')")
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout
