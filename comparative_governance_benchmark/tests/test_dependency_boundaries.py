"""Dependency rules (Task 18)."""
from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
PKG = REPO / "comparative_governance_benchmark"
FROZEN = ("decision_governance", "governance_providers", "tap_provider",
          "actiongate_provider", "enterprise_validation_pilot")


def _imports(root):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield path, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.module


def test_frozen_packages_never_import_benchmark():
    for name in FROZEN:
        root = REPO / name
        bad = [f"{p.name}->{m}" for p, m in _imports(root)
               if m.split(".")[0] == "comparative_governance_benchmark"]
        assert not bad, (name, bad)


def test_benchmark_owns_no_frozen_source():
    for name in FROZEN:
        assert not (PKG / name).exists()


def test_benchmark_uses_only_kernel_public_api():
    bad = []
    for p, m in _imports(PKG):
        if m.split(".")[0] == "decision_governance" and not (
                m == "decision_governance" or m.startswith("decision_governance.api")
                or m.startswith("decision_governance.errors")):
            bad.append(f"{p.name}->{m}")
    assert not bad, bad


def test_benchmark_imports_standalone():
    import subprocess
    import sys
    code = ("import comparative_governance_benchmark.benchmark, "
            "comparative_governance_benchmark.run; print('ok')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout
