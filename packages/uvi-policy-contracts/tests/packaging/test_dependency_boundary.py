"""Dependency boundary: this package depends only on stdlib + governance-contracts.

AST-scans every module in ``ugence_uvi_policy_contracts`` and asserts it imports
no capability, product, platform, console, provider-framework, downstream-leaf,
or third-party package. The single permitted cross-package dependency is the
neutral ``ugence_governance_contracts`` leaf (ADR §21 — the arrow points at a
neutral-contract package only, never at a downstream leaf such as
``governed-value`` or ``agent-value-readiness``).
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_uvi_policy_contracts

PKG_ROOT = pathlib.Path(ugence_uvi_policy_contracts.__file__).resolve().parent
SELF = "ugence_uvi_policy_contracts"
DEPENDENCY = "ugence_governance_contracts"
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

PROHIBITED = {
    # downstream leaves this package must NEVER import (would invert the arrow)
    "governed_value", "ugence_governed_value", "agent_value_readiness",
    # provider framework / capabilities / products / platform
    "governance_providers", "decision_governance", "actiongate_provider",
    "tap_provider", "ai_hiring", "domains", "applications", "ugence_console_api",
    "risk_authority", "platform_freeze",
    # third-party
    "pydantic", "numpy", "torch", "pandas", "fastapi",
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


def test_only_stdlib_self_and_governance_contracts():
    allowed = _STDLIB | {SELF, DEPENDENCY, "__future__"}
    strays = {}
    for p in PKG_ROOT.rglob("*.py"):
        for r in _roots(p):
            if r not in allowed:
                strays.setdefault(str(p.relative_to(PKG_ROOT)), set()).add(r)
    assert not strays, strays
