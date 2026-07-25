"""Pilot dependency rules + provider independence (Task 113)."""
from __future__ import annotations

import ast
import pathlib

from enterprise_validation_pilot.evaluators import check_independence, independence_passed

REPO = pathlib.Path(__file__).resolve().parents[2]
PILOT = REPO / "enterprise_validation_pilot"
FROZEN = ("decision_governance", "governance_providers", "tap_provider", "actiongate_provider")


def _imports(root):
    for path in root.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield path, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.module


def test_tap_and_actiongate_remain_peers():
    results = check_independence()
    assert independence_passed(results), [r for r in results if not r.passed]


def test_pilot_uses_only_kernel_public_api():
    bad = []
    for path, mod in _imports(PILOT):
        if mod.split(".")[0] == "decision_governance" and not (
                mod == "decision_governance"          # bare pkg (public __version__)
                or mod.startswith("decision_governance.api")
                or mod.startswith("decision_governance.errors")):
            bad.append(f"{path.name}->{mod}")
    assert not bad, bad


def test_pilot_owns_no_frozen_source():
    for name in FROZEN:
        assert not (PILOT / name).exists(), f"pilot must not vendor {name}"


def test_pilot_composition_may_import_both_providers():
    mods = {m for _p, m in _imports(PILOT)}
    roots = {m.split(".")[0] for m in mods}
    assert "tap_provider" in roots and "actiongate_provider" in roots


def test_pilot_imports_standalone():
    import subprocess
    import sys
    code = ("import enterprise_validation_pilot.pilot, enterprise_validation_pilot.run, "
            "enterprise_validation_pilot.composition, enterprise_validation_pilot.evaluators; "
            "print('ok')")
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout
