"""Dependency direction: this package is a zero-dependency stdlib leaf.

AST-scans every module in ``ugence_trusted_evidence_authority`` and asserts it
imports nothing but the standard library and itself. ADR §23 permits TAP to
depend on ``governance-contracts``; TEV-1 takes the narrower zero-dependency
option (DD-2 is blocked on the shapes TEV-1 produces, so importing that leaf now
would decide DD-2 by implementation).

The reverse direction is asserted too: no package in the monorepo imports this
one. TEV-1 authorizes no consumer integration (ADR §30 — UVI-EV-1 is DEFERRED),
so an import from a consumer would be scope expansion, not convenience.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_trusted_evidence_authority

PKG_ROOT = pathlib.Path(ugence_trusted_evidence_authority.__file__).resolve().parent
SELF = "ugence_trusted_evidence_authority"
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

#: Nothing here may ever be imported by this package. Importing any of them
#: would invert an ADR §23 arrow or put TAP on a runtime authorization path.
PROHIBITED = {
    # authorities and engines (ADR §23: "TAP ... must never import" these)
    "risk_authority", "ugence_risk_authority",
    "ugence_policy_authority", "policy_authority",
    "ugence_decision_authority", "decision_governance",
    "agent_value_readiness", "ugence_agent_value_readiness",
    "governed_value", "ugence_governed_value",
    "actiongate_provider", "ugence_actiongate_provider",
    "ugence_benchmark_registry", "benchmark_registry",
    "ugence_tap_provider", "tap_provider",
    "truth_assurance_pipeline",
    # agent runtime / cloud scaling / provider framework / products / platform
    "agent_runtime", "agent_runtime_migration", "cloud_scaling_operations",
    "cloud_controller", "governance_providers",
    "ugence_governance_provider_framework",
    "ai_hiring", "domains", "applications", "ugence_console_api", "platform_freeze",
    # even the neutral leaf: TEV-1 declares no dependency at all
    "ugence_governance_contracts",
    "ugence_uvi_policy_contracts",
    # third-party
    "pydantic", "numpy", "torch", "pandas", "fastapi", "cryptography", "nacl",
}


def _roots(path: pathlib.Path) -> set:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative import within this package
            if node.module:
                roots.add(node.module.split(".")[0])
    return roots


def _sources():
    return sorted(PKG_ROOT.rglob("*.py"))


def test_no_prohibited_import_anywhere():
    offenders = {}
    for path in _sources():
        bad = _roots(path) & PROHIBITED
        if bad:
            offenders[str(path.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_only_the_standard_library_and_this_package_are_imported():
    allowed = _STDLIB | {SELF, "__future__"}
    strays = {}
    for path in _sources():
        for root in _roots(path):
            if root not in allowed:
                strays.setdefault(str(path.relative_to(PKG_ROOT)), set()).add(root)
    assert not strays, strays


def test_the_distribution_declares_zero_runtime_dependencies():
    import tomllib

    pyproject = PKG_ROOT.parents[1] / "pyproject.toml"
    if not pyproject.is_file():  # running from an installed wheel
        import importlib.metadata as md

        requires = md.requires("ugence-trusted-evidence-authority") or []
        runtime = [r for r in requires if "extra ==" not in r]
        assert runtime == [], runtime
        return
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    assert data["project"]["dependencies"] == []


def test_no_module_defines_a_competing_assessed_system_binding():
    """ADR §14.1 — Governance Contracts owns it, defined exactly once."""

    for path in _sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                assert node.name != "AssessedSystemBinding", path
                assert node.name != "SystemManifest", path  # DD-11 stays open
                assert node.name != "SubjectContext", path


# --------------------------------------------------------------------------- #
# Reverse dependency: nothing in the monorepo imports TEV-1
# --------------------------------------------------------------------------- #

def _repo_root():
    # packages/trusted-evidence-authority/tests/packaging -> repo root
    here = pathlib.Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packages").is_dir() and (parent / "platform_freeze").is_dir():
            return parent
    return None


def test_no_consumer_imports_this_package():
    repo = _repo_root()
    if repo is None:
        return  # running outside the monorepo (installed wheel); nothing to scan
    own_tree = (repo / "packages" / "trusted-evidence-authority").resolve()
    importers = []
    for path in repo.glob("packages/**/*.py"):
        resolved = path.resolve()
        if str(resolved).startswith(str(own_tree)):
            continue
        if "__pycache__" in resolved.parts or "build" in resolved.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if SELF in text:
            importers.append(str(path.relative_to(repo)))
    assert not importers, (
        "TEV-1 authorizes no consumer integration (ADR §30: UVI-EV-1 DEFERRED); "
        f"unexpected references: {importers}"
    )
