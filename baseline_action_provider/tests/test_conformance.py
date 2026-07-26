"""Baseline action — shared + specific conformance, honesty, isolation."""
from __future__ import annotations

import ast
import pathlib

from governance_providers.api import ActionGovernanceProvider, ProviderKind
from governance_providers.conformance import run_action_provider_conformance
from baseline_action_provider.configuration import build_baseline_action_provider
from baseline_action_provider.conformance import run_baseline_action_conformance
from baseline_action_provider.provider import CAPABILITIES

PKG = pathlib.Path(__file__).resolve().parents[1]


def test_passes_shared_conformance():
    assert run_action_provider_conformance(lambda: build_baseline_action_provider()).passed


def test_passes_specific_conformance():
    rep = run_baseline_action_conformance()
    assert rep.passed, rep.failures


def test_is_action_provider():
    assert isinstance(build_baseline_action_provider(), ActionGovernanceProvider)


def test_descriptor_honesty():
    d = build_baseline_action_provider().descriptor()
    assert d.kind is ProviderKind.ACTION_GOVERNANCE
    for rich in ("required_approval", "single_use", "expiry", "region_limits",
                 "resource_scope_limits"):
        assert rich not in d.capabilities.features
    assert "allow_deny" in CAPABILITIES and "amount_limits" in CAPABILITIES


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


def test_core_is_pure_and_no_other_provider_imported():
    core = PKG / "core.py"
    bad = [m for _p, m in _imports(PKG) if _p == core
           and m.split(".")[0] in ("decision_governance", "governance_providers")]
    assert not bad, bad
    others = ("tap_provider", "actiongate_provider", "baseline_assertion_provider")
    leaked = [m for _p, m in _imports(PKG) if m.split(".")[0] in others]
    assert not leaked, leaked
