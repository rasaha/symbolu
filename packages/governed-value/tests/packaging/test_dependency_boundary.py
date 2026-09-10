"""Dependency boundary: stdlib + exactly one Ugence contract leaf.

The kernel's boundary was asserted only inside
``verify_governed_value_distribution.py``, which builds a wheel and installs it
offline — a strong proof that ran nowhere in CI, so in practice nothing checked
the boundary on a pull request at all. The wheel proof stays (it establishes
things source cannot: that the *declared metadata* names no other dependency),
and this adds the cheap source-level half that a PR can run in a second.

The one arrow is ``ugence_governance_contracts`` (GV-DEP, for
``MetricObservation``). The kernel imports no capability, product, provider or
authority package, and no third party: all money and rate maths is
``decimal.Decimal``.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import governed_value

PKG_ROOT = pathlib.Path(governed_value.__file__).resolve().parent
SELF = "governed_value"
DEPS = {"ugence_governance_contracts"}
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

PROHIBITED = {
    "ugence_agent_value_readiness", "ugence_uvi_policy_contracts",
    "ugence_policy_authority", "ugence_benchmark_registry",
    "ugence_trusted_evidence_authority", "risk_authority",
    "governance_providers", "decision_governance", "actiongate_provider",
    "tap_provider", "ai_hiring", "ugence_console_api", "platform_freeze",
    "pydantic", "numpy", "torch", "pandas", "fastapi",
}


def _module_names(path: pathlib.Path) -> set[str]:
    """Every fully-qualified absolute module name imported by ``path``."""

    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module:
                names.add(node.module)
    return names


def _roots(path: pathlib.Path) -> set[str]:
    return {name.split(".")[0] for name in _module_names(path)}


def _sources(root: pathlib.Path = PKG_ROOT):
    return sorted(root.rglob("*.py"))


def test_no_prohibited_imports():
    offenders = {}
    for p in _sources():
        bad = _roots(p) & PROHIBITED
        if bad:
            offenders[str(p.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_only_stdlib_self_and_the_one_contract_leaf():
    allowed = _STDLIB | {SELF, "__future__"} | DEPS
    strays = {}
    for p in _sources():
        for r in _roots(p):
            if r not in allowed:
                strays.setdefault(str(p.relative_to(PKG_ROOT)), set()).add(r)
    assert not strays, strays


def test_the_contract_leaf_never_imports_this_package():
    """The arrow is one-way; a reverse dependency would be a cycle."""

    import ugence_governance_contracts

    root = pathlib.Path(ugence_governance_contracts.__file__).resolve().parent
    for p in sorted(root.rglob("*.py")):
        assert SELF not in _roots(p), p


def test_no_float_arithmetic_reaches_the_money_model():
    """Exact money: ``decimal``, never ``float``.

    A CFO audits these figures, so the guard is on the import rather than on any
    one call site — ``import math`` or a ``float(`` cast in a money module is the
    shape the drift would take.
    """

    for p in _sources():
        roots = _roots(p)
        assert "math" not in roots, p
        assert "statistics" not in roots, p


def test_the_declared_dependency_matches_what_is_imported():
    """pyproject declares exactly the arrows the source actually takes."""

    import re

    pyproject = (PKG_ROOT.parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", pyproject, re.S | re.M)
    assert block is not None, "no dependencies array in pyproject.toml"
    declared = set(re.findall(r"""["']([A-Za-z0-9_.-]+?)(?:[<>=!~].*?)?["']""", block.group(1)))
    assert declared == {"ugence-governance-contracts"}, declared

    imported = set()
    for p in _sources():
        imported |= _roots(p) & {d.replace("-", "_") for d in declared}
    assert imported == {"ugence_governance_contracts"}, imported
