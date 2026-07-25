"""Baseline assertion — shared + specific conformance, honesty, isolation."""
from __future__ import annotations

import ast
import pathlib

from governance_providers.api import AssertionGovernanceProvider, ProviderKind
from governance_providers.conformance import run_assertion_provider_conformance
from baseline_assertion_provider.configuration import build_baseline_assertion_provider
from baseline_assertion_provider.conformance import run_baseline_assertion_conformance
from baseline_assertion_provider.provider import CAPABILITIES

PKG = pathlib.Path(__file__).resolve().parents[1]


def test_passes_shared_conformance():
    assert run_assertion_provider_conformance(lambda: build_baseline_assertion_provider()).passed


def test_passes_specific_conformance():
    rep = run_baseline_assertion_conformance()
    assert rep.passed, rep.failures


def test_is_assertion_provider():
    assert isinstance(build_baseline_assertion_provider(), AssertionGovernanceProvider)


def test_descriptor_honesty():
    d = build_baseline_assertion_provider().descriptor()
    assert d.kind is ProviderKind.ASSERTION_GOVERNANCE
    # honestly declares NO rich capabilities
    for rich in ("qualifier_detection", "scope_analysis", "component_decomposition",
                 "provenance_analysis"):
        assert rich not in d.capabilities.features
    assert "exact_evidence_matching" in CAPABILITIES


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
    others = ("tap_provider", "actiongate_provider", "baseline_action_provider")
    leaked = [m for _p, m in _imports(PKG) if m.split(".")[0] in others]
    assert not leaked, leaked
