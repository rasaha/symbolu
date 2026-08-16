"""Dependency boundary: stdlib + the two neutral contract leaves only (§3).

AST-scans every module and asserts the authority leaf never imports
``governed-value``, ``agent-value-readiness``, Risk/Decision Authority
internals, Agent Runtime, Runtime Assurance, forecasting, a benchmark-value
service, or any third-party runtime dependency.

The Ed25519 signing convention is *reproduced* from ``risk_authority``, not
imported: reusing another authority's internals would create exactly the
reverse dependency ADR §21 forbids.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_uvi_policy_authority

PKG_ROOT = pathlib.Path(ugence_uvi_policy_authority.__file__).resolve().parent
SELF = "ugence_uvi_policy_authority"
DEPS = {"ugence_governance_contracts", "ugence_uvi_policy_contracts"}
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

PROHIBITED = {
    # Readiness and financial value
    "ugence_agent_value_readiness",
    "agent_value_readiness",
    "governed_value",
    "ugence_governed_value",
    # Other authorities' internals
    "risk_authority",
    "ugence_risk_authority",
    "ugence_decision_authority",
    "decision_governance",
    # Runtime / assurance / providers
    "agent_runtime",
    "ugence_agent_runtime",
    "runtime_assurance",
    "governance_providers",
    "governance_provider_framework",
    "actiongate_provider",
    "tap_provider",
    # Forecasting and benchmark-value services
    "forecasting",
    "value_forecasting",
    "benchmark_registry",
    "benchmark_value",
    # Products and third-party
    "ai_hiring",
    "procurement",
    "ugence_console_api",
    "platform_freeze",
    "pydantic",
    "numpy",
    "torch",
    "pandas",
    "fastapi",
    "cryptography",
    "nacl",
}


def _roots(path: pathlib.Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def test_no_prohibited_imports():
    offenders = {}
    for path in PKG_ROOT.rglob("*.py"):
        bad = _roots(path) & PROHIBITED
        if bad:
            offenders[str(path.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_only_stdlib_self_and_contract_leaves():
    allowed = _STDLIB | {SELF, "__future__"} | DEPS
    strays: dict[str, set[str]] = {}
    for path in PKG_ROOT.rglob("*.py"):
        for root in _roots(path):
            if root not in allowed:
                strays.setdefault(str(path.relative_to(PKG_ROOT)), set()).add(root)
    assert not strays, strays


def test_no_reverse_dependency_on_another_authority():
    """The Ed25519 convention is reproduced, never imported."""

    source = (PKG_ROOT / "ed25519.py").read_text()
    assert "risk_authority" not in _roots(PKG_ROOT / "ed25519.py")
    # It does cite its provenance in prose, which is the point.
    assert "risk_authority/crypto/signing.py" in source


def test_the_declared_distribution_dependencies_match_the_imports():
    import re

    pyproject = (PKG_ROOT.parents[1] / "pyproject.toml").read_text()
    declared = set(re.findall(r'"(ugence-[a-z-]+)>=', pyproject))
    assert declared == {"ugence-governance-contracts", "ugence-uvi-policy-contracts"}
