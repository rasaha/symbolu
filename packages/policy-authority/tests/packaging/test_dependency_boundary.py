"""Dependency boundary and reverse-dependency scan (ADR §10.4, §19).

The authority imports **no** engine: not readiness, not governed-value, not
Risk/Decision Authority internals, not Agent Runtime, Runtime Assurance,
forecasting, or the benchmark-value service. That is the reverse-dependency
direction, and it is absolute.

The forward direction is the ratified one: engines **consume** the authority.
ADR §10.4 states it exactly — "UVI engines consume exact resolved policy
artifacts; they do **not** import authority internals." A consumer may therefore
name ``ugence_policy_authority`` or ``ugence_policy_authority.api``, and may
name nothing else: every ``…core`` / ``…adapters`` module stays internal, and
the scan below enforces that repository-wide.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_policy_authority

PKG_ROOT = pathlib.Path(ugence_policy_authority.__file__).resolve().parent
DIST_ROOT = PKG_ROOT.parents[1]
REPO_ROOT = DIST_ROOT.parents[1]
SELF = "ugence_policy_authority"

#: Only the UVI adapter has a cross-package dependency, and only on the UVI
#: policy contracts. ``governance-contracts`` is NOT a direct dependency: the
#: authority never imports it (it arrives transitively through the contracts).
DEPS = {"ugence_uvi_policy_contracts"}
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

PROHIBITED = {
    "ugence_agent_value_readiness",
    "agent_value_readiness",
    "governed_value",
    "ugence_governed_value",
    "risk_authority",
    "ugence_risk_authority",
    "ugence_decision_authority",
    "decision_governance",
    "agent_runtime",
    "ugence_agent_runtime",
    "runtime_assurance",
    "governance_providers",
    "governance_provider_framework",
    "actiongate_provider",
    "tap_provider",
    "forecasting",
    "value_forecasting",
    "benchmark_registry",
    "benchmark_value",
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
            roots.update(a.name.split(".")[0] for a in node.names)
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


def test_only_stdlib_self_and_the_uvi_contracts_leaf():
    allowed = _STDLIB | {SELF, "__future__"} | DEPS
    strays: dict[str, set[str]] = {}
    for path in PKG_ROOT.rglob("*.py"):
        for root in _roots(path):
            if root not in allowed:
                strays.setdefault(str(path.relative_to(PKG_ROOT)), set()).add(root)
    assert not strays, strays


def test_governance_contracts_is_not_a_direct_dependency():
    """It was declared but never imported; the declaration is removed."""

    importers = {
        str(p.relative_to(PKG_ROOT))
        for p in PKG_ROOT.rglob("*.py")
        if "ugence_governance_contracts" in _roots(p)
    }
    assert importers == set(), importers

    # Check the declaration itself, not the prose explaining its absence.
    assert "ugence-governance-contracts" not in _declared_dependencies()


def _declared_dependencies() -> set[str]:
    import re

    pyproject = (DIST_ROOT / "pyproject.toml").read_text()
    block = re.search(r"^dependencies\s*=\s*\[(.*?)\]", pyproject, re.S | re.M)
    assert block, "no dependencies declaration found"
    return set(re.findall(r'"([^"<>=!]+)', block.group(1)))


def test_the_declared_distribution_dependencies_match_the_imports():
    assert _declared_dependencies() == {"ugence-uvi-policy-contracts"}


def test_the_distribution_and_namespace_are_the_canonical_shared_names():
    pyproject = (DIST_ROOT / "pyproject.toml").read_text()
    assert 'name = "ugence-policy-authority"' in pyproject
    assert "ugence_policy_authority" in pyproject
    assert "ugence-uvi-policy-authority" not in pyproject
    assert "ugence_uvi_policy_authority" not in pyproject
    assert DIST_ROOT.name == "policy-authority"


#: The only modules of this authority a consumer may name. Everything else is
#: an internal, whatever its import form.
PUBLIC_MODULES = {SELF, f"{SELF}.api"}


def test_no_package_anywhere_imports_an_authority_internal():
    """Consumers may use the public surface; internals stay internal."""

    offenders = {}
    for path in (REPO_ROOT / "packages").rglob("*.py"):
        if str(path).startswith(str(DIST_ROOT)):
            continue
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except (OSError, UnicodeDecodeError, SyntaxError):  # pragma: no cover
            continue
        for node in ast.walk(tree):
            names = set()
            if isinstance(node, ast.Import):
                names = {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
                names = {node.module}
            for name in names:
                if name.split(".")[0] != SELF:
                    continue
                if name not in PUBLIC_MODULES:
                    offenders.setdefault(str(path.relative_to(REPO_ROOT)), set()).add(name)
    assert not offenders, offenders


def test_the_superseded_uvi_specific_authority_name_appears_nowhere():
    """``ugence_uvi_policy_authority`` was prohibited by name (ADR §8)."""

    offenders = []
    for path in (REPO_ROOT / "packages").rglob("*.py"):
        if str(path).startswith(str(DIST_ROOT)):
            continue
        try:
            source = path.read_text()
        except (OSError, UnicodeDecodeError):  # pragma: no cover
            continue
        if "ugence_uvi_policy_authority" in source:
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, offenders


def test_no_consumer_is_imported_back_by_this_authority():
    """The reverse direction stays empty — a cycle would be a second system."""

    for path in sorted(PKG_ROOT.rglob("*.py")):
        assert not (_roots(path) & PROHIBITED), path


def test_the_ed25519_convention_is_reproduced_not_imported():
    source = (PKG_ROOT / "core" / "ed25519.py").read_text()
    assert "risk_authority" not in _roots(PKG_ROOT / "core" / "ed25519.py")
    assert "risk_authority/crypto/signing.py" in source
