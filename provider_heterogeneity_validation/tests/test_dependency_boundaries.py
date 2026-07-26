"""Dependency enforcement (Task 18)."""
from __future__ import annotations

import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]
PKG = REPO / "provider_heterogeneity_validation"
PROVIDERS = ("tap_provider", "actiongate_provider", "baseline_assertion_provider",
             "baseline_action_provider")
FROZEN = ("decision_governance", "governance_providers", "enterprise_validation_pilot",
          "comparative_governance_benchmark") + PROVIDERS


def _imports(root):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts or "tests" in p.parts:
            continue
        for node in ast.walk(ast.parse(p.read_text())):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield p, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield p, node.module


def test_frozen_and_providers_never_import_benchmark_or_validation():
    for name in FROZEN:
        bad = [f"{p.name}->{m}" for p, m in _imports(REPO / name)
               if m.split(".")[0] in ("provider_heterogeneity_validation",)]
        assert not bad, (name, bad)


def test_same_family_providers_do_not_import_one_another():
    tap = {m for _p, m in _imports(REPO / "tap_provider")}
    ba = {m for _p, m in _imports(REPO / "baseline_assertion_provider")}
    ag = {m for _p, m in _imports(REPO / "actiongate_provider")}
    bac = {m for _p, m in _imports(REPO / "baseline_action_provider")}
    assert "baseline_assertion_provider" not in {m.split(".")[0] for m in tap}
    assert "tap_provider" not in {m.split(".")[0] for m in ba}
    assert "baseline_action_provider" not in {m.split(".")[0] for m in ag}
    assert "actiongate_provider" not in {m.split(".")[0] for m in bac}


def test_assertion_providers_never_import_action_providers():
    for a_pkg in ("tap_provider", "baseline_assertion_provider"):
        roots = {m.split(".")[0] for _p, m in _imports(REPO / a_pkg)}
        assert not ({"actiongate_provider", "baseline_action_provider"} & roots)


def test_action_providers_never_import_assertion_providers():
    for a_pkg in ("actiongate_provider", "baseline_action_provider"):
        roots = {m.split(".")[0] for _p, m in _imports(REPO / a_pkg)}
        assert not ({"tap_provider", "baseline_assertion_provider"} & roots)


def test_only_composition_modules_import_providers():
    # provider imports allowed only in runners/composition.py and runners/workflow.py
    allowed = {"composition.py", "workflow.py"}
    bad = []
    for p, m in _imports(PKG):
        if m.split(".")[0] in PROVIDERS and p.name not in allowed:
            bad.append(f"{p.name}->{m}")
    assert not bad, bad


def test_selection_is_provider_neutral():
    roots = {m.split(".")[0] for _p, m in _imports(PKG / "selection")}
    assert not (set(PROVIDERS) & roots)


def test_baseline_providers_use_only_public_apis():
    for pkg in ("baseline_assertion_provider", "baseline_action_provider"):
        bad = [f"{p.name}->{m}" for p, m in _imports(REPO / pkg)
               if m.split(".")[0] == "decision_governance"
               and not (m == "decision_governance" or m.startswith("decision_governance.api")
                        or m.startswith("decision_governance.errors"))]
        assert not bad, bad
