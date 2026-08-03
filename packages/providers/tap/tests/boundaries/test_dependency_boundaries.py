"""Static dependency-boundary guards for the canonical TAP package.

Enforced against the ``ugence_tap_provider`` source tree:

* the core (``core/``, ``client/``) imports neither the framework nor the kernel;
* the package never imports ActionGate (peer isolation);
* the package never imports AI Hiring, applications, domains, or research trees;
* only the framework's public ``.api`` surface is consumed.
"""
from __future__ import annotations

import ast
import pathlib

CANON = pathlib.Path(__file__).resolve().parents[2] / "src" / "ugence_tap_provider"

_FORBIDDEN_ROOTS = {
    "actiongate_provider", "ugence_actiongate_provider",
    "ai_hiring", "ugence_ai_hiring",
    "applications", "domains", "symbolu", "agentic",
    "cloud_controller", "hybrid_llm_vnext_lab", "experiments", "platform_freeze",
    "decision_governance",  # kernel reached only lazily through the framework adapter
}
_CORE_FORBIDDEN = _FORBIDDEN_ROOTS | {
    "ugence_governance_provider_framework", "governance_providers",
    "ugence_governance_contracts", "ugence_decision_authority",
}


def _imports(root: pathlib.Path):
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        for node in ast.walk(ast.parse(p.read_text(), filename=str(p))):
            if isinstance(node, ast.Import):
                for a in node.names:
                    yield p, node.lineno, a.name
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                yield p, node.lineno, node.module


def test_package_never_imports_forbidden_roots():
    bad = [f"{p.relative_to(CANON)}:{ln}->{m}" for p, ln, m in _imports(CANON)
           if m.split(".")[0] in _FORBIDDEN_ROOTS]
    assert not bad, bad


def test_core_and_client_are_pure():
    bad = []
    for sub in ("core", "client"):
        bad += [f"{p.relative_to(CANON)}:{ln}->{m}"
                for p, ln, m in _imports(CANON / sub)
                if m.split(".")[0] in _CORE_FORBIDDEN]
    assert not bad, bad


def test_consumes_only_framework_public_api():
    bad = [f"{p.relative_to(CANON)}:{ln}->{m}" for p, ln, m in _imports(CANON)
           if m.startswith("ugence_governance_provider_framework.")
           and not m.startswith("ugence_governance_provider_framework.api")]
    assert not bad, bad
