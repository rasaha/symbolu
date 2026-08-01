"""C5 — the contracts package is a leaf: stdlib + self only.

AST-scans every module in ``ugence_governance_contracts`` and asserts it imports
no capability, product, platform, console, provider-framework, or research
package, and no third-party runtime dependency.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_governance_contracts

PKG_ROOT = pathlib.Path(ugence_governance_contracts.__file__).resolve().parent
SELF = "ugence_governance_contracts"
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

PROHIBITED = {
    "governance_providers", "decision_governance", "actiongate_provider",
    "tap_provider", "baseline_action_provider", "baseline_assertion_provider",
    "ai_hiring", "domains", "applications", "ugence_console_api",
    "enterprise_validation_pilot", "comparative_governance_benchmark",
    "provider_heterogeneity_validation", "cer_v0_1", "cer_v0_2", "cer_v0_3",
    "agentic", "agent_runtime_migration", "symbolu_robotics", "experiments",
    "platform_freeze", "pydantic", "numpy", "torch", "pandas", "fastapi",
}


def _roots(path: pathlib.Path):
    tree = ast.parse(path.read_text(), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                roots.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_no_prohibited_imports():
    offenders = {}
    for p in PKG_ROOT.rglob("*.py"):
        bad = _roots(p) & PROHIBITED
        if bad:
            offenders[str(p.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_only_stdlib_and_self():
    allowed = _STDLIB | {SELF, "__future__"}
    strays = {}
    for p in PKG_ROOT.rglob("*.py"):
        for r in _roots(p):
            if r not in allowed:
                strays.setdefault(str(p.relative_to(PKG_ROOT)), set()).add(r)
    assert not strays, strays
