"""Dependency direction: pydantic, the standard library, and nothing else.

AST-scans every module in ``ugence_agent_constitution`` and asserts it imports no
other ``ugence_*`` package, no legacy monorepo top-level package, and no
third-party distribution except pydantic.

This is the gate that keeps the package a leaf. A contract package that imports a
tooling package, an authority, or a runtime stops being safely importable by
everything else — and the first such import is always the cheap one that looked
harmless. Stated as a property of the whole module tree rather than a list of
today's imports, so a new module cannot quietly widen the surface.

Dynamic imports are checked too: an ``importlib.import_module`` call naming a
``ugence_*`` package would satisfy a static scan and still be a dependency.
"""

from __future__ import annotations

import ast
import pathlib
import sys

import ugence_agent_constitution

PKG_ROOT = pathlib.Path(ugence_agent_constitution.__file__).resolve().parent
SELF = "ugence_agent_constitution"
_STDLIB = set(getattr(sys, "stdlib_module_names", set()))

#: The only third-party distribution AC-0 depends on.
ALLOWED_THIRD_PARTY = {"pydantic"}

#: Never importable from here. Not exhaustive by design — the positive allowlist
#: in :func:`test_only_the_standard_library_pydantic_and_itself_are_imported` is
#: the real gate. This list exists so that the most tempting wrong imports fail
#: with a message naming why.
PROHIBITED = {
    # sibling Ugence contract, tooling and authority distributions
    "ugence_policy_workflow_compiler",
    "ugence_governance_contracts",
    "ugence_uvi_policy_contracts",
    "ugence_capabilities",
    "ugence_policy_authority",
    "ugence_risk_authority",
    "ugence_trusted_evidence_authority",
    "ugence_benchmark_registry",
    "ugence_governed_value",
    "ugence_agent_value_readiness",
    "ugence_governance_provider_framework",
    "ugence_procurement",
    "ugence_console_api",
    # legacy monorepo top-level packages
    "governance_providers", "decision_governance", "risk_authority",
    "policy_authority", "agent_runtime", "agent_runtime_migration",
    "cloud_controller", "cloud_scaling_operations", "actiongate_provider",
    "tap_provider", "truth_assurance_pipeline", "governed_value",
    "domains", "applications", "ai_hiring", "symbolu", "agentic",
    "platform_freeze", "benchmark_registry",
    # third-party surfaces a contract package has no business reaching for
    "numpy", "torch", "pandas", "fastapi", "flask", "django", "requests",
    "httpx", "boto3", "google", "azure", "sqlalchemy", "redis",
    "openai", "anthropic", "mistralai",
    "cryptography", "nacl", "jwt", "jose",  # AC-0 fingerprints; it does not sign
}


def _sources():
    return sorted(p for p in PKG_ROOT.rglob("*.py") if "__pycache__" not in p.parts)


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


def _dynamic_import_targets(path: pathlib.Path) -> set:
    """String literals passed to any ``import_module``-named call."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = (
            func.attr
            if isinstance(func, ast.Attribute)
            else func.id
            if isinstance(func, ast.Name)
            else ""
        )
        if name in ("import_module", "__import__"):
            for arg in node.args[:1]:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    targets.add(arg.value.split(".")[0])
    return targets


def test_the_package_has_modules_to_scan():
    """A scan over an empty tree passes vacuously; make that impossible."""
    assert len(_sources()) >= 10


def test_no_prohibited_import_anywhere():
    offenders = {}
    for path in _sources():
        bad = _roots(path) & PROHIBITED
        if bad:
            offenders[str(path.relative_to(PKG_ROOT))] = sorted(bad)
    assert not offenders, offenders


def test_no_other_ugence_package_is_imported():
    """The rule stated directly, so it holds for a sibling that does not exist yet."""
    offenders = {}
    for path in _sources():
        strays = {
            root
            for root in _roots(path)
            if root.startswith("ugence_") and root != SELF
        }
        if strays:
            offenders[str(path.relative_to(PKG_ROOT))] = sorted(strays)
    assert not offenders, offenders


def test_only_the_standard_library_pydantic_and_itself_are_imported():
    allowed = _STDLIB | {SELF, "__future__"} | ALLOWED_THIRD_PARTY
    strays = {}
    for path in _sources():
        for root in _roots(path):
            if root not in allowed:
                strays.setdefault(str(path.relative_to(PKG_ROOT)), set()).add(root)
    assert not strays, {k: sorted(v) for k, v in strays.items()}


def test_no_dynamic_import_reaches_another_ugence_package():
    offenders = {}
    for path in _sources():
        strays = {
            target
            for target in _dynamic_import_targets(path)
            if target.startswith("ugence_") and target != SELF
        }
        if strays:
            offenders[str(path.relative_to(PKG_ROOT))] = sorted(strays)
    assert not offenders, offenders


def test_the_third_party_allowlist_is_exactly_the_ratified_set():
    """A boundary whose exception list can be widened silently is not a boundary."""
    assert ALLOWED_THIRD_PARTY == {"pydantic"}


def test_the_declared_distribution_dependencies_match_the_allowlist():
    """The pyproject and the import scan must agree; a dependency declared but not
    imported is dead weight, and one imported but not declared is a broken wheel."""
    pyproject = PKG_ROOT.parents[1] / "pyproject.toml"
    if not pyproject.is_file():
        return  # installed wheel; nothing to cross-check
    text = pyproject.read_text(encoding="utf-8")
    body = text.split("dependencies = [", 1)[1].split("]", 1)[0]
    declared = {
        line.strip().strip('",').split(">")[0].split("=")[0].split("[")[0].strip()
        for line in body.splitlines()
        if line.strip().startswith('"')
    }
    assert declared == ALLOWED_THIRD_PARTY, declared


def test_importing_the_package_does_not_pull_in_another_ugence_package():
    """The static scan proves the source is clean; this proves the import actually is."""
    import importlib

    importlib.reload(ugence_agent_constitution)
    loaded = {
        name.split(".")[0]
        for name in sys.modules
        if name.startswith("ugence_") and not name.startswith(SELF)
    }
    assert not loaded, sorted(loaded)
