"""Dependency + peer boundaries on the CANONICAL source tree.

    ugence_actiongate_provider       must not import TAP / AI Hiring / apps / cloud / hybrid
    ugence_actiongate_provider core  must import neither the framework nor the kernel
    ugence_actiongate_provider       must consume only the framework public ``.api``
    (no direct kernel import in the core path)
"""
from __future__ import annotations

import ast
import pathlib

import ugence_actiongate_provider

PKG = pathlib.Path(ugence_actiongate_provider.__file__).resolve().parent

_FORBIDDEN_ROOTS = {
    "tap_provider", "ugence_tap_provider",
    "ai_hiring", "ugence_ai_hiring",
    "domains", "applications", "symbolu", "agentic", "cloud_controller",
    "hybrid_llm_vnext_lab", "experiments",
}
_FRAMEWORK_KERNEL_ROOTS = {
    "ugence_governance_provider_framework", "governance_providers",
    "decision_governance", "ugence_decision_authority", "ugence_governance_contracts",
}


def _imports(*, only_file=None):
    files = [only_file] if only_file else [
        p for p in PKG.rglob("*.py") if "__pycache__" not in p.parts]
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield path, node.lineno, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield path, node.lineno, node.module


def test_no_forbidden_imports():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports()
           if m.split(".")[0] in _FORBIDDEN_ROOTS]
    assert not bad, "\n".join(bad)


def test_no_tap_import_anywhere():
    bad = [f"{p.name}:{ln}->{m}" for p, ln, m in _imports()
           if m.split(".")[0] in ("tap_provider", "ugence_tap_provider")]
    assert not bad, "ActionGate and TAP are independent peers:\n" + "\n".join(bad)


def test_core_and_client_are_pure():
    for rel in ("core.py", "client/__init__.py"):
        bad = [f"{rel}:{ln}->{m}" for _p, ln, m in _imports(only_file=PKG / rel)
               if m.split(".")[0] in _FRAMEWORK_KERNEL_ROOTS | _FORBIDDEN_ROOTS]
        assert not bad, bad


def test_only_framework_public_api_and_no_direct_kernel():
    bad = []
    for p, ln, m in _imports():
        if m.startswith("ugence_governance_provider_framework.") \
                and not m.startswith("ugence_governance_provider_framework.api"):
            bad.append(f"{p.name}:{ln}->{m}")
        if m.split(".")[0] in ("decision_governance", "ugence_decision_authority"):
            bad.append(f"{p.name}:{ln}->{m}")
    assert not bad, "\n".join(bad)
