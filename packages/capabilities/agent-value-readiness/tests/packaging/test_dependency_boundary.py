"""Dependency boundary: stdlib + governance-contracts + uvi-policy-contracts only.

AST-scans every module and asserts the readiness leaf never imports
``governed-value``, any other capability/product/authority package, or a
third-party runtime dependency. Its only permitted cross-package imports are the
two neutral contract leaves (ADR §21).
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_agent_value_readiness

PKG_ROOT = pathlib.Path(ugence_agent_value_readiness.__file__).resolve().parent
SELF = "ugence_agent_value_readiness"
DEPS = {"ugence_governance_contracts", "ugence_uvi_policy_contracts"}
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

PROHIBITED = {
    "governed_value", "ugence_governed_value",
    "governance_providers", "decision_governance", "actiongate_provider",
    "tap_provider", "ai_hiring", "ugence_console_api", "risk_authority",
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


def test_only_stdlib_self_and_contract_leaves():
    allowed = _STDLIB | {SELF, "__future__"} | DEPS
    strays = {}
    for p in PKG_ROOT.rglob("*.py"):
        for r in _roots(p):
            if r not in allowed:
                strays.setdefault(str(p.relative_to(PKG_ROOT)), set()).add(r)
    assert not strays, strays
